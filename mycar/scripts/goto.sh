#!/bin/bash
# goto.sh — 导航到指定航点
# 用法: ./scripts/goto.sh <航点名>
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR/.."
source install/setup.bash
ros2 topic pub /goto_waypoint std_msgs/String "data: '$1'" --once
