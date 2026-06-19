#!/bin/bash
# ============================================================================
# verify_odom.sh — 里程计验证脚本
#
# 用法:
#   ./verify_odom.sh               # 默认串口 /dev/ttyUSB0
#   ./verify_odom.sh /dev/ttyUSB1  # 指定串口
# ============================================================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"
SERIAL=${1:-/dev/ttyUSB0}

source /opt/tros/humble/setup.bash
export ROS_DOMAIN_ID=42
export FASTRTPS_DEFAULT_PROFILES_FILE="$SCRIPT_DIR/config/fastdds.xml"

# 编译
echo "🔨 编译 mycar_driver..."
colcon build --packages-select mycar_driver
source ./install/setup.bash

# 清理残留
pkill -f "mycar_driver/driver_node" 2>/dev/null || true
pkill -f "mycar_driver/odom_node" 2>/dev/null || true
pkill -f "mycar_driver/verify_odom" 2>/dev/null || true
sleep 1

# 后台启动 driver + odom
echo "🔧 后台启动 driver + odom (串口: $SERIAL)..."
setsid ros2 launch mycar_driver driver.launch.py serial_port:="$SERIAL" &
LAUNCH_PID=$!
echo "⏳ 等待节点就绪..."
sleep 3

cleanup() {
    echo ""
    echo "🛑 停止所有节点..."
    kill -TERM -- -$LAUNCH_PID 2>/dev/null || true
    sleep 1
    pkill -f "mycar_driver/driver_node" 2>/dev/null || true
    pkill -f "mycar_driver/odom_node" 2>/dev/null || true
    pkill -f "mycar_driver/verify_odom" 2>/dev/null || true
    wait $LAUNCH_PID 2>/dev/null || true
    echo "已退出。"
}
trap cleanup EXIT INT TERM

# 前台运行验证
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  里程计标定验证                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  ⚠ 请确保小车有足够空间移动（前进+后退 ~2m，旋转 360°）"
echo ""

ros2 run mycar_driver verify_odom
