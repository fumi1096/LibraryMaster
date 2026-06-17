#!/bin/bash
# ============================================================================
# mycar 小车启动脚本 (v1.0)
# 四驱普通轮子 + 差速转向 + 双目深度相机
#
# 模式:
#   driver    — 仅驱动 + 里程计（调试用）
#   embedded  — 全栈启动：驱动 + 里程计 + IMU + 相机 + EKF
#   mapping   — 建图模式：embedded + slam_toolbox + RViz2
#   navigate  — 自主导航（需预先保存地图，Phase 6 实现）
#   mapping_distributed  — 分布式 2D 建图（小车端：仅驱动+相机+EKF，SLAM 在 PC）
#   mapping3d_distributed — 分布式 3D 建图（小车端：驱动+相机+EKF+体素滤波，RTAB-Map 在 PC）
#
# 用法:
#   ./start_mycar.sh driver
#   ./start_mycar.sh embedded
#   ./start_mycar.sh mapping
#
# 依赖:
#   - 串口设备 /dev/ttyUSB0 已连接驱动板
#   - hobot_stereonet 已安装
# ============================================================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

# ============================================
# 环境设置 (必须先 source ROS 才能使用 ros2 命令)
# ============================================
source /opt/tros/humble/setup.bash

# 不清理 ROS 进程，避免误杀 daemon 或其他节点

# ============================================
# 网络配置 (ROS 2 默认 DDS 通信)
# ============================================
# 域 ID: 与 PC 端保持一致 (42)
export ROS_DOMAIN_ID=42

# Fast-DDS 配置: 禁用共享内存 (跨机器/VPN 必须走 UDP)
export FASTRTPS_DEFAULT_PROFILES_FILE="$SCRIPT_DIR/config/fastdds.xml"

echo "🌐 ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "🌐 Fast-DDS config: $FASTRTPS_DEFAULT_PROFILES_FILE"

# ============================================
# 加载 mycar 工作空间
# ============================================
source ./install/setup.bash


MODE=${1:-embedded}
SERIAL=${2:-/dev/ttyUSB0}

log() { echo "[$(date '+%H:%M:%S')] $*"; }
banner() {
    echo ""
    echo "============================================"
    echo "  $*"
    echo "============================================"
    echo ""
}

# ============================================
# 启动
# ============================================
case "$MODE" in
    driver)
        banner "mycar — 仅驱动节点"
        log "串口: $SERIAL"
        ros2 launch mycar_driver driver.launch.py serial_port:="$SERIAL"
        ;;

    embedded)
        banner "mycar — 全栈启动 (embedded)"
        log "节点: 驱动 + 里程计 + IMU滤波 + EKF + 双目相机 + LaserScan"
        log "串口: $SERIAL"
        ros2 launch mycar_driver bringup.launch.py \
            serial_port:="$SERIAL" \
            use_ekf:=true \
            use_camera:=true \
            use_rviz:=false
        ;;

    mapping)
        banner "mycar — 建图模式"
        log "嵌入式核心后台启动..."
        log "串口: $SERIAL"
        ros2 launch mycar_driver bringup.launch.py \
            serial_port:="$SERIAL" \
            use_ekf:=true \
            use_camera:=true \
            use_rviz:=false &
        EMBEDDED_PID=$!
        sleep 5

        # 验证核心话题
        log "验证核心话题..."
        if ros2 topic list 2>/dev/null | grep -q "/scan"; then
            log "✅ /scan 就绪"
        else
            log "⚠️  /scan 未检测到，继续..."
        fi

        log "启动 slam_toolbox + RViz2..."
        ros2 launch mycar_slam slam.launch.py &
        SLAM_PID=$!
        sleep 3

        log ""
        log "============================================"
        log "  建图已启动！请在 RViz2 中配置显示项："
        log "    Add → By topic → /map (Map)"
        log "    Add → By topic → /scan (LaserScan)"
        log "    Add → TF"
        log "    Add → RobotModel"
        log ""
        log "  键盘遥控: 按 i 前进, , 后退, j/l 转向"
        log "  保存地图: ros2 run nav2_map_server map_saver_cli -f ~/mycar_map"
        log "============================================"
        log ""

        ros2 run mycar_driver keyboard_control

        # 清理
        kill $SLAM_PID 2>/dev/null
        kill $EMBEDDED_PID 2>/dev/null
        wait $EMBEDDED_PID 2>/dev/null
        ;;

    mapping3d)
        banner "mycar — RTAB-Map 3D 建图"
        log "嵌入式核心后台启动（无 laser scan 管线）..."
        log "串口: $SERIAL"
        ros2 launch mycar_driver bringup.launch.py \
            serial_port:="$SERIAL" \
            use_ekf:=true \
            use_camera:=true \
            use_rviz:=false &
        EMBEDDED_PID=$!
        sleep 5

        log "启动 RTAB-Map 3D 建图..."
        ros2 launch mycar_rtabmap rtabmap_mapping.launch.py &
        RTAB_PID=$!
        sleep 3

        log ""
        log "============================================"
        log "  RTAB-Map 3D 建图已启动！"
        log "  RViz 中 Add:"
        log "    MapCloud → /rtabmap/cloud_map"
        log "    MapGraph → /rtabmap/mapGraph"
        log "    Grid → /rtabmap/grid_map"
        log "    RobotModel + TF + PointCloud2"
        log ""
        log "  键盘遥控: i 前进, , 后退, j/l 转向"
        log "  保存数据库: ros2 service call /rtabmap/save_database ..."
        log "============================================"
        log ""

        ros2 run mycar_driver keyboard_control

        kill $RTAB_PID 2>/dev/null
        kill $EMBEDDED_PID 2>/dev/null
        wait $EMBEDDED_PID 2>/dev/null
        ;;

    mapping_distributed)
        banner "mycar — 分布式 2D 建图 (小车端)"
        log "节点: 驱动 + 里程计 + IMU滤波 + EKF + 双目相机 + LaserScan"
        log "所有数据处理 + 遥控 + 可视化均在 PC 端"
        log "串口: $SERIAL"
        log ""
        log "============================================"
        log "  PC 端操作:"
        log "    cd mycar_pc && ./start_pc.sh mapping2d"
        log "============================================"
        log ""

        ros2 launch mycar_driver bringup.launch.py \
            serial_port:="$SERIAL" \
            use_ekf:=true \
            use_camera:=true \
            use_rviz:=false &
        EMBEDDED_PID=$!

        log "小车端已启动，按 Ctrl+C 停止"
        wait $EMBEDDED_PID
        ;;

    mapping3d_distributed)
        banner "mycar — 分布式 3D 建图 (小车端, RGB-D 模式)"
        log "节点: 驱动 + 里程计 + IMU滤波 + EKF + 双目相机 + LaserScan"
        log "图像修正 (image_republisher): 时间戳 + 编码转换 → PC 端 RTAB-Map RGB-D"
        log "点云直接透传 → PC 端 (ICP 备用)"
        log "串口: $SERIAL"
        log ""
        log "============================================"
        log "  PC 端操作:"
        log "    cd mycar_pc && ./start_pc.sh mapping3d_rgbd"
        log "============================================"
        log ""

        ros2 launch mycar_driver bringup.launch.py \
            serial_port:="$SERIAL" \
            use_ekf:=true \
            use_camera:=true \
            use_rviz:=false &
        EMBEDDED_PID=$!
        sleep 5

        log "启动图像修正节点 (时间戳 + 编码转换)..."
        ros2 launch mycar_driver image_republish.launch.py &
        IMAGE_PID=$!

        log "小车端已启动，按 Ctrl+C 停止"
        wait $EMBEDDED_PID
        kill $IMAGE_PID 2>/dev/null
        ;;

    *)
        echo "用法: $0 [driver|embedded|mapping|mapping3d|mapping_distributed|mapping3d_distributed] [串口路径]"
        echo ""
        echo "  driver                  — 仅驱动 + 里程计（调试用）"
        echo "  embedded                — 全栈启动（驱动 + IMU + EKF + 相机）"
        echo "  mapping                 — 2D 建图（slam_toolbox，本地）"
        echo "  mapping3d               — 3D 建图（RTAB-Map，本地）"
        echo "  mapping_distributed     — 分布式 2D 建图（小车端，SLAM 在 PC）"
        echo "  mapping3d_distributed   — 分布式 3D 建图（小车端，RTAB-Map 在 PC）"
        echo ""
        echo "示例:"
        echo "  $0 embedded              /dev/ttyUSB0"
        echo "  $0 mapping_distributed   /dev/ttyUSB0"
        echo "  $0 mapping3d_distributed /dev/ttyUSB0"
        exit 1
        ;;
esac
