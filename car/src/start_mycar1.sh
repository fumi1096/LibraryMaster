#!/bin/bash
# mycar1 小车启动脚本
# 四驱普通轮子 + 差速转向
#
# 使用方法：
#   ./start_mycar1.sh              # 仅启动驱动节点
#   ./start_mycar1.sh launch       # 使用 launch 文件启动完整系统
#   ./start_mycar1.sh rviz         # 启动驱动 + RViz 可视化

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

source /opt/tros/humble/setup.bash
source ./install/setup.bash

MODE=${1:-driver}

case "$MODE" in
    driver)
        echo "=== 启动 mycar1 四驱驱动节点 ==="
        ros2 run yahboomcar_bringup FourWD_driver
        ;;
    launch)
        echo "=== 启动 mycar1 完整系统（launch）==="
        ros2 launch yahboomcar_bringup yahboomcar_bringup_mycar1_launch.py
        ;;
    rviz)
        echo "=== 启动 mycar1 + RViz 可视化 ==="
        # 先启动驱动节点（后台）
        ros2 run yahboomcar_bringup FourWD_driver &
        sleep 2
        # 启动 robot_state_publisher
        ros2 run robot_state_publisher robot_state_publisher \
            --ros-args -p robot_description:="$(xacro mycar1/urdf/mycar1.urdf)" &
        sleep 1
        # 启动 RViz
        ros2 run rviz2 rviz2 -d src/yahboomcar_description/rviz/yahboomcar.rviz
        ;;
    *)
        echo "用法: $0 [driver|launch|rviz]"
        echo "  driver  - 仅启动驱动节点（默认）"
        echo "  launch  - 启动完整系统"
        echo "  rviz    - 启动驱动 + RViz 可视化"
        exit 1
        ;;
esac
