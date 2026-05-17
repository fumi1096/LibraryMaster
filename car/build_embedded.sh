#!/bin/bash
#==============================================================================
# build_embedded.sh — 嵌入式 (RDK X5) 编译脚本
#
# 编译目标：所有硬件驱动 + 导航栈
# 环境：TROS Humble (/opt/tros/humble)
#
# 用法：
#   cd ~/project/LibraryMaster/car
#   ./build_embedded.sh
#==============================================================================
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
BUILD_DIR="$SCRIPT_DIR/src"

cd "$BUILD_DIR"

echo "============================================"
echo "  mycar00 嵌入式 (RDK X5) 编译"
echo "============================================"

# ---- 1. 加载 TROS 环境 ----
echo "[1/3] 加载 TROS Humble 环境..."
source /opt/tros/humble/setup.bash

# ---- 2. 清理旧编译缓存 ----
echo "[2/4] 清理旧编译缓存..."
rm -rf build/yahboomcar_description install/yahboomcar_description
rm -rf build/mycar00 install/mycar00
rm -rf build/yahboomcar_base_node install/yahboomcar_base_node
rm -rf build/yahboomcar_bringup install/yahboomcar_bringup
rm -rf build/yahboomcar_ctrl install/yahboomcar_ctrl
rm -rf build/mycar_navigation install/mycar_navigation

# ---- 3. 编译 ----
echo "[3/4] 编译嵌入式包..."
PACKAGES=(
    yahboomcar_description    # URDF 资源
    mycar00                   # 机器人模型（URDF + meshes）
    yahboomcar_base_node      # 里程计 (C++)
    yahboomcar_bringup        # 驱动 + IMU 滤波 + EKF + launch
    yahboomcar_ctrl           # 键盘/手柄遥控
    mycar_navigation          # Nav2 自主导航栈
)

colcon build --packages-select "${PACKAGES[@]}"

# ---- 4. 加载新环境 ----
echo "[4/4] 加载编译产物..."
source install/setup.bash

echo ""
echo "============================================"
echo "  嵌入式编译完成！"
echo "============================================"
echo ""
echo "下一步："
echo "  ./start_mycar00.sh embedded   # 启动核心节点"
echo "  ./start_mycar00.sh mapping    # 建图模式"
echo "  ./start_mycar00.sh navigate   # 自主导航"
