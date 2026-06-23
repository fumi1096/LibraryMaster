#!/bin/bash
# save_waypoint.sh — 保存当前位置为航点
# 用法: ./scripts/save_waypoint.sh <航点名>
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR/.."
source install/setup.bash
ros2 topic pub /save_waypoint std_msgs/String "data: '$1'" --once
