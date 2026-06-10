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
# 环境设置
# ============================================
source /opt/tros/humble/setup.bash
source ./install/setup.bash

# 日志目录权限 (防止 TROS 日志写入失败)
if [ ! -w /userdata/.roslog ]; then
    sudo mkdir -p /userdata/.roslog 2>/dev/null || true
    sudo chmod 777 /userdata/.roslog 2>/dev/null || true
fi

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

    *)
        echo "用法: $0 [driver|embedded|mapping|mapping3d] [串口路径]"
        echo ""
        echo "  driver     — 仅驱动 + 里程计（调试用）"
        echo "  embedded   — 全栈启动（驱动 + IMU + EKF + 相机）"
        echo "  mapping    — 2D 建图（slam_toolbox）"
        echo "  mapping3d  — 3D 建图（RTAB-Map + 点云下采样）"
        echo ""
        echo "示例:"
        echo "  $0 embedded  /dev/ttyUSB0"
        echo "  $0 mapping   /dev/ttyUSB0"
        echo "  $0 mapping3d /dev/ttyUSB0"
        exit 1
        ;;
esac
