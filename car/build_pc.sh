#!/bin/bash
#==============================================================================
# build_pc.sh — PC (笔记本) 编译脚本
#
# 编译目标：SLAM 建图 + RViz 可视化 + 键盘遥控
# 环境：标准 ROS2 Humble (/opt/ros/humble)
#
# 用法：
#   cd ~/project/LibraryMaster/car
#   ./build_pc.sh
#
# 前置条件：
#   sudo apt install -y ros-humble-slam-toolbox ros-humble-rviz2
#==============================================================================
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
BUILD_DIR="$SCRIPT_DIR/src"

cd "$BUILD_DIR"

echo "============================================"
echo "  mycar00 PC 端编译"
echo "============================================"

# ---- 1. 加载 ROS2 环境 ----
echo "[1/4] 加载 ROS2 Humble 环境..."
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
elif [ -f /opt/tros/humble/setup.bash ]; then
    # 兼容：如果 PC 也装了 TROS
    source /opt/tros/humble/setup.bash
else
    echo "错误：找不到 ROS2 环境，请先 source 后再运行"
    exit 1
fi

# ---- 2. 安装缺失的系统依赖 ----
echo "[2/5] 检查系统依赖..."
MISSING_DEPS=""
for dep in ros-humble-slam-toolbox ros-humble-navigation2 ros-humble-rviz2 \
           ros-humble-joint-state-publisher ros-humble-joint-state-publisher-gui; do
    if ! dpkg -l "$dep" 2>/dev/null | grep -q '^ii'; then
        MISSING_DEPS="$MISSING_DEPS $dep"
    fi
done
if [ -n "$MISSING_DEPS" ]; then
    echo "  安装缺失依赖:$MISSING_DEPS"
    sudo apt install -y $MISSING_DEPS
else
    echo "  ✓ 系统依赖完整"
fi

# ---- 3. 清理旧编译缓存 ----
echo "[3/5] 清理旧编译缓存..."
rm -rf build/yahboomcar_description install/yahboomcar_description
rm -rf build/mycar00 install/mycar00
rm -rf build/yahboomcar_ctrl install/yahboomcar_ctrl
rm -rf build/mycar_slam install/mycar_slam

# ---- 4. 编译 ----
echo "[4/5] 编译 PC 端包..."

PACKAGES=(
    yahboomcar_description
    mycar00
    yahboomcar_ctrl
    mycar_slam
)

colcon build --packages-select "${PACKAGES[@]}"

# ---- 5. 加载 ----
echo "[5/5] 加载编译产物..."
source install/setup.bash

echo ""
echo "============================================"
echo "  PC 端编译完成！"
echo "============================================"
echo ""
echo "建图流程："
echo "  1. 嵌入式: ./start_mycar00.sh mapping"
echo "  2. PC:     ros2 launch mycar_slam slam_pc.launch.py"
echo "  3. PC(另开): ros2 run yahboomcar_ctrl yahboom_keyboard"
echo ""
echo "地图保存："
echo "  ros2 run nav2_map_server map_saver_cli -f ~/mycar_map"
