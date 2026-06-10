#!/bin/bash
# ============================================================================
# mycar_pc PC 端启动脚本 (v1.0)
# 分布式部署 — 负责计算密集型节点 + 可视化
#
# 前提:
#   - Fast DDS Discovery Server 已启动
#   - 小车端已启动 mapping_distributed / mapping3d_distributed
#   - 网络互通 (ROS_DISCOVERY_SERVER 已配置)
#
# 模式:
#   mapping2d — 2D 建图 (slam_toolbox + RViz2)
#   mapping3d — 3D 建图 (RTAB-Map + RViz2)
#
# 用法:
#   ./start_pc.sh mapping2d
#   ./start_pc.sh mapping3d
# ============================================================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

# ============================================
# 环境设置
# ============================================
# PC 端使用标准 ROS2 Humble
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
        banner "PC 端 — 2D 建图 (slam_toolbox)"
        log "等待小车端话题: /scan, /odom, TF..."
        log ""

        # 验证话题
        log "检查 /scan 话题..."
        for i in $(seq 1 15); do
            if ros2 topic list 2>/dev/null | grep -q "/scan"; then
                log "✅ /scan 已检测到"
                break
            fi
            sleep 1
        done

        log "启动 slam_toolbox + RViz2..."
        ros2 launch mycar_slam slam.launch.py

        log ""
        log "建图完成。保存地图:"
        log "  ros2 run nav2_map_server map_saver_cli -f ~/mycar_map"
        ;;

    mapping3d)
        banner "PC 端 — 3D 建图 (RTAB-Map)"
        log "等待小车端话题: /scan_cloud, /odom, TF..."
        log ""

        # 验证体素滤波后的点云
        log "检查 /scan_cloud 话题..."
        for i in $(seq 1 15); do
            if ros2 topic list 2>/dev/null | grep -q "/scan_cloud"; then
                log "✅ /scan_cloud 已检测到"
                break
            fi
            sleep 1
        done

        log "启动 RTAB-Map + RViz2..."
        ros2 launch mycar_rtabmap rtabmap_mapping_pc.launch.py

        log ""
        log "3D 建图完成。保存数据库:"
        log "  ros2 service call /rtabmap/save_database rtabmap_msgs/srv/SaveDatabase"
        ;;

    *)
        echo "用法: $0 [mapping2d|mapping3d]"
        echo ""
        echo "  mapping2d  — 2D 建图 (slam_toolbox + RViz2)"
        echo "  mapping3d  — 3D 建图 (RTAB-Map + RViz2)"
        echo ""
        echo "前提:"
        echo "  1. Fast DDS Discovery Server 已启动"
        echo "  2. 小车端已启动:"
        echo "     ./start_mycar.sh mapping_distributed      (2D)"
        echo "     ./start_mycar.sh mapping3d_distributed    (3D)"
        echo "  3. 两端均已配置 ROS_DISCOVERY_SERVER"
        exit 1
        ;;
esac
