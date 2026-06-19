#!/bin/bash
# ============================================================================
# calibrate_odom.sh — 里程计一键标定脚本
#
# 用法:
#   ./calibrate_odom.sh                # 默认串口 /dev/ttyUSB0
#   ./calibrate_odom.sh /dev/ttyUSB1   # 指定串口
#
# 流程:
#   1. 编译 mycar_driver
#   2. 后台启动 driver + odom (ros2 launch)
#   3. 前台启动标定节点 (ros2 run，保证交互式 stdin 可用)
#   4. Ctrl+C 退出后自动清理后台进程
# ============================================================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

SERIAL=${1:-/dev/ttyUSB0}

# 环境
source /opt/tros/humble/setup.bash
export ROS_DOMAIN_ID=42
export FASTRTPS_DEFAULT_PROFILES_FILE="$SCRIPT_DIR/config/fastdds.xml"

# 编译
echo "🔨 编译 mycar_driver..."
colcon build --packages-select mycar_driver

# 加载
source ./install/setup.bash

# ============================================================
# 清理可能残留的旧节点（避免多个 odom_node 同时发布）
# ============================================================
echo "🧹 清理可能残留的旧节点..."
pkill -f "mycar_driver/driver_node" 2>/dev/null || true
pkill -f "mycar_driver/odom_node" 2>/dev/null || true
pkill -f "mycar_driver/calibrate_odom" 2>/dev/null || true
sleep 1

# 后台启动 driver + odom（用 setsid 创建新进程组，确保 cleanup 能彻底清理）
echo "🔧 后台启动 driver + odom (串口: $SERIAL)..."
setsid ros2 launch mycar_driver calibrate.launch.py serial_port:="$SERIAL" &
LAUNCH_PID=$!

# 等待 driver 和 odom 就绪
echo "⏳ 等待节点就绪..."
sleep 3

# 清理函数 — kill 整个进程组，确保子节点也被终止
cleanup() {
    echo ""
    echo "🛑 正在停止所有节点..."
    # 杀死进程组（负 PID = 整个进程组）
    kill -TERM -- -$LAUNCH_PID 2>/dev/null || true
    sleep 1
    # 兜底：按名称清理
    pkill -f "mycar_driver/driver_node" 2>/dev/null || true
    pkill -f "mycar_driver/odom_node" 2>/dev/null || true
    pkill -f "mycar_driver/calibrate_odom" 2>/dev/null || true
    wait $LAUNCH_PID 2>/dev/null || true
    echo "已退出。"
}
trap cleanup EXIT INT TERM

# 前台运行标定（保证 stdin 交互可用）
# workspace_dir 指向源目录，确保标定结果写入源文件（colcon build 后不丢失）
echo "🚀 启动标定工具 (前台交互模式)..."
echo ""
ros2 run mycar_driver calibrate_odom --ros-args -p workspace_dir:="$SCRIPT_DIR"
