#!/bin/bash
# ============================================================================
# mycar_pc PC 端工作空间构建脚本
# ============================================================================
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

# 环境设置
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
elif [ -f /opt/tros/humble/setup.bash ]; then
    source /opt/tros/humble/setup.bash
else
    echo "错误: 找不到 ROS2 Humble 环境"
    exit 1
fi

echo "=========================================="
echo "  mycar_pc workspace build"
echo "=========================================="

colcon build "$@"

echo ""
echo "✅ Build complete!"
echo "   source install/setup.bash"
