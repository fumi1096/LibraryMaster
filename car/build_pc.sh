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

# ---- 2. 检查依赖 ----
echo "[2/4] 检查依赖..."
MISSING=""
for pkg in slam_toolbox nav2_map_server rviz2; do
    if ! ros2 pkg prefix "$pkg" &>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done
if [ -n "$MISSING" ]; then
    echo "缺少依赖包:$MISSING"
    echo "请运行: sudo apt install -y ros-humble-slam-toolbox ros-humble-navigation2 ros-humble-rviz2"
    exit 1
fi
echo "  ✓ 依赖检查通过"

# ---- 3. 编译 ----
echo "[3/4] 编译 PC 端包..."

# PC 端不需要编译硬件驱动包（yahboomcar_bringup, yahboomcar_base_node）
# 只需要：URDF 模型 + 可视化 + 遥控 + SLAM
PACKAGES=(
    yahboomcar_description    # URDF 资源 + RViz 配置
    mycar00                   # 机器人模型（URDF + meshes）
    yahboomcar_ctrl           # 键盘/手柄遥控
    mycar_slam                # SLAM 建图
)

colcon build --packages-select "${PACKAGES[@]}"

# ---- 4. 加载新环境 ----
echo "[4/4] 加载编译产物..."
source install/setup.bash

echo ""
echo "============================================"
echo "  PC 端编译完成！"
echo "============================================"
echo ""
echo "下一步（建图流程）："
echo "  1. 嵌入式:  ./start_mycar00.sh mapping"
echo "  2. PC:      ros2 launch mycar_slam slam_pc.launch.py"
echo "  3. PC(另开): ros2 run yahboomcar_ctrl yahboom_keyboard"
echo ""
echo "地图保存："
echo "  ros2 run nav2_map_server map_saver_cli -f ~/mycar_map"
