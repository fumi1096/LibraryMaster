#!/bin/bash
#==============================================================================
# mycar00 小车启动脚本 (v2.0)
# 四驱普通轮子 + 差速转向 + 双目摄像头
#
# 模式：
#   embedded  - 嵌入式全栈：驱动 + 里程计 + IMU + 相机 + TF + EKF
#   mapping   - 建图模式：embedded + 键盘遥控（PC 端另起 slam_toolbox + RViz）
#   navigate  - 自主导航：embedded + Nav2（需预先保存地图）
#   driver    - 仅驱动（调试用）
#
# 用法：
#   ./start_mycar00.sh embedded   # 嵌入式启动核心节点
#   ./start_mycar00.sh mapping    # 建图模式（含键盘遥控）
#   ./start_mycar00.sh navigate   # 自主导航模式
#   ./start_mycar00.sh driver     # 仅启动驱动节点
#==============================================================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

# 指定 CycloneDDS 使用 usb0 网卡（与 RDK X5 通信）
export CYCLONEDDS_URI=file://$SCRIPT_DIR/cyclonedds_config.xml

source /opt/tros/humble/setup.bash
source ./install/setup.bash

# 修复 TROS 日志目录权限（防止节点崩溃）
if [ ! -w /userdata/.roslog ]; then
    sudo mkdir -p /userdata/.roslog 2>/dev/null
    sudo chmod 777 /userdata/.roslog 2>/dev/null
fi

MODE=${1:-embedded}

log() { echo "[$(date '+%H:%M:%S')] $*"; }
banner() {
    echo ""
    echo "============================================"
    echo "  $*"
    echo "============================================"
    echo ""
}

case "$MODE" in
    driver)
        banner "mycar00 — 仅驱动节点"
        ros2 run yahboomcar_bringup FourWD_driver
        ;;

    embedded)
        banner "mycar00 — 嵌入式全栈启动"
        log "节点：驱动 + 里程计 + IMU + 相机 + URDF TF + EKF"
        ros2 launch yahboomcar_bringup yahboomcar_bringup_mycar00_launch.py \
            use_ekf:=true use_camera:=true use_rviz:=false
        ;;

    mapping)
        banner "mycar00 — 建图模式"
        log "嵌入式核心后台启动..."
        log "PC 端（另开终端执行）："
        log "  ros2 launch mycar_slam slam_pc.launch.py"
        echo ""
        ros2 launch yahboomcar_bringup yahboomcar_bringup_mycar00_launch.py \
            use_ekf:=true use_camera:=true use_rviz:=false &
        EMBEDDED_PID=$!
        sleep 3
        log "启动键盘遥控（ctrl+c 退出）"
        ros2 run yahboomcar_ctrl yahboom_keyboard
        kill $EMBEDDED_PID 2>/dev/null
        wait $EMBEDDED_PID 2>/dev/null
        ;;

    navigate)
        banner "mycar00 — 自主导航模式"
        MAP_FILE="${2:-$SCRIPT_DIR/mycar_navigation/maps/mycar_map.yaml}"
        if [ ! -f "$MAP_FILE" ]; then
            log "错误：地图文件不存在: $MAP_FILE"
            log "请先将建图得到的地图复制到该路径"
            exit 1
        fi
        log "地图：$MAP_FILE"
        ros2 launch yahboomcar_bringup yahboomcar_bringup_mycar00_launch.py \
            use_ekf:=true use_camera:=true use_rviz:=false &
        EMBEDDED_PID=$!
        sleep 4
        log "启动 Nav2 自主导航..."
        ros2 launch mycar_navigation navigation_embedded.launch.py map:="$MAP_FILE"
        kill $EMBEDDED_PID 2>/dev/null
        wait $EMBEDDED_PID 2>/dev/null
        ;;

    *)
        echo "用法: $0 [embedded|mapping|navigate|driver]"
        echo ""
        echo "  embedded  - 嵌入式全栈（驱动+里程计+IMU+相机+TF+EKF）"
        echo "  mapping   - 建图模式（embedded + 键盘遥控）"
        echo "  navigate  - 自主导航（需预先保存地图）"
        echo "  driver    - 仅启动四驱驱动节点"
        exit 1
        ;;
esac
