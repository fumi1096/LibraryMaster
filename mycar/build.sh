#!/bin/bash
# ============================================================================
# mycar 工作空间构建脚本
# ============================================================================
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

source /opt/tros/humble/setup.bash

echo "=========================================="
echo "  mycar workspace build"
echo "=========================================="

colcon build "$@"

echo ""
echo "✅ Build complete!"
echo "   source install/setup.bash"
