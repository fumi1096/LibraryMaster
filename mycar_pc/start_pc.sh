#!/bin/bash
# ============================================================================
# mycar_pc PC 端启动脚本 (v4.0 — 2D + 3D 建图)
# 分布式部署 — slam_toolbox 2D / RTAB-Map RGB-D 3D 建图 + RViz2 可视化
#
# 前提:
#   - 小车端已启动 mapping_distributed (2D) 或 mapping3d_distributed (3D)
#   - 网络互通 (VPN, ROS_DOMAIN_ID=42)
#
# 用法:
#   ./start_pc.sh mapping2d          # 2D slam_toolbox 建图
#   ./start_pc.sh mapping3d_rgbd     # 3D RTAB-Map 建图
# ============================================================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

# ============================================
# 环境设置
# ============================================
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
elif [ -f /opt/tros/humble/setup.bash ]; then
    source /opt/tros/humble/setup.bash
else
    echo "错误: 找不到 ROS2 Humble 环境"
    exit 1
fi

source ./install/setup.bash 2>/dev/null || {
    echo "⚠️  未找到 install/setup.bash，请先运行 ./build.sh"
    exit 1
}

# ============================================
# 中间件配置
# ============================================
export ROS_DOMAIN_ID=42
export FASTRTPS_DEFAULT_PROFILES_FILE="$SCRIPT_DIR/config/fastdds.xml"

echo "🌐 ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "🌐 Fast-DDS config: $FASTRTPS_DEFAULT_PROFILES_FILE"
echo "🔄 使用 ROS 2 默认中间件 (Fast DDS)"

MODE=${1:-mapping2d}

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
    mapping2d)
        banner "PC 端 — slam_toolbox 2D 建图 (分布式)"

        log "小车端应已启动:"
        log "  cd mycar && ./start_mycar.sh mapping_distributed"
        log ""
        log "启动 slam_toolbox + RViz2..."
        log "等待小车端数据 (约 5-10 秒)..."
        ros2 launch mycar_rtabmap slam2d_pc.launch.py &
        SLAM_PID=$!
        sleep 5

        log ""
        log "============================================"
        log "  2D 建图已启动！RViz2 显示项:"
        log "    /map (Map)"
        log "    /scan (LaserScan)"
        log "    TF"
        log "    RobotModel"
        log ""
        log "  键盘遥控: i 前进, , 后退, j/l 转向, k 停止"
        log "============================================"
        log ""

        log "启动键盘遥控..."
        ros2 run mycar_rtabmap keyboard_control

        kill $SLAM_PID 2>/dev/null
        wait $SLAM_PID 2>/dev/null

        log ""
        log "============================================"
        log "  2D 建图完成！"
        log ""
        log "  保存地图:"
        log "    ros2 run nav2_map_server map_saver_cli -f ~/mycar_map"
        log "============================================"
        ;;

    mapping3d_rgbd)
        banner "PC 端 — RTAB-Map RGB-D 3D 建图"

        # 清理旧数据库，从原点开始
        DB_PATH="$HOME/.ros/rtabmap.db"
        rm -f "$DB_PATH"
        log "已清理数据库: $DB_PATH"

        log "启动 RTAB-Map RGB-D + RViz2..."
        log "等待小车端数据 (约 5-10 秒)..."
        ros2 launch mycar_rtabmap rtabmap_rgbd_pc.launch.py "database_path:=$DB_PATH" &
        RTAB_PID=$!
        sleep 5

        log "启动键盘遥控 (i 前进, , 后退, j/l 转向, k 停止)..."
        ros2 run mycar_rtabmap keyboard_control

        kill $RTAB_PID 2>/dev/null
        wait $RTAB_PID 2>/dev/null

        log ""
        log "============================================"
        log "  3D RGB-D 建图完成！"
        log ""
        log "  数据库已保存: $DB_PATH"
        log ""
        log "  查看 3D 地图:"
        log "    rtabmap-databaseViewer $DB_PATH"
        log ""
        log "  导出 2D 栅格地图 (Nav2 导航用):"
        log "    ros2 run nav2_map_server map_saver_cli -f ~/mycar_map"
        log "============================================"
        ;;

    *)
        echo "用法: $0 [mapping2d|mapping3d_rgbd]"
        echo ""
        echo "  mapping2d          — slam_toolbox 2D 建图"
        echo "                       小车端: ./start_mycar.sh mapping_distributed"
        echo "  mapping3d_rgbd     — RTAB-Map RGB-D 3D 建图"
        echo "                       小车端: ./start_mycar.sh mapping3d_distributed"
        echo "                       (ORB视觉特征 + 深度投影 + 词袋回环)"
        echo ""
        echo "键盘遥控: i 前进, , 后退, j/l 转向, k 停止"
        echo ""
        echo "前提:"
        echo "  1. 两端 ROS_DOMAIN_ID 一致 (当前: 42)"
        echo "  2. 网络互通 (VPN 已连接)"
        echo "  3. 小车端已启动对应分布式模式"
        exit 1
        ;;
esac
