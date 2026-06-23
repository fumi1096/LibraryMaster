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

# TROS 兼容: 复制 bin/ 可执行文件到 lib/<pkg>/ (colcon 查找路径)
for pkg_dir in install/*/; do
    pkg=$(basename "$pkg_dir")
    if [ -d "install/$pkg/bin" ] && [ ! -d "install/$pkg/lib/$pkg" ]; then
        mkdir -p "install/$pkg/lib/$pkg"
        cp "install/$pkg/bin/"* "install/$pkg/lib/$pkg/"
        echo "  ↳ TROS fix: copied bin/ → lib/$pkg/ for $pkg"
    fi
done

echo ""
echo "✅ Build complete!"
echo "   source install/setup.bash"
