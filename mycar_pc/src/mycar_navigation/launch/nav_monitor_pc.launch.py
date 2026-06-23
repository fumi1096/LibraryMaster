"""
nav_monitor_pc.launch.py — PC 端 Nav2 导航监看

仅启动:
  - robot_state_publisher (本地 URDF, RViz RobotModel 后备)
  - RViz2 (预配置: Map + LaserScan + TF + RobotModel + Costmaps + Plans)

通过 DDS 跨网络接收所有导航话题:
  - /map, /scan, /odom, TF (来自小车端)
  - /plan, /local_plan, /global_costmap/costmap, /local_costmap/costmap

用户可在 RViz 中:
  - "2D Pose Estimate" → /initialpose → 设定 AMCL 初始位姿
  - "2D Nav Goal" → /goal_pose → 发送导航目标到 bt_navigator

小车端需先启动导航:
  cd mycar && ./start_mycar.sh navigate_distributed

用法:
  ros2 launch mycar_navigation nav_monitor_pc.launch.py
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import Command


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_navigation')
    pkg_mycar_f = get_package_share_directory('mycar_f')

    # ============================================
    # robot_state_publisher (本地 URDF)
    # ============================================
    model_path = os.path.join(pkg_mycar_f, 'urdf', 'mycar_f.urdf')
    robot_description = ParameterValue(
        Command(['cat ', model_path]), value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': robot_description,
            'publish_robot_description': True,
        }],
    )

    # ============================================
    # RViz2 (预配置导航显示)
    # ============================================
    rviz_config = os.path.join(pkg_dir, 'config', 'nav_monitor_pc.rviz')

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
    )

    return LaunchDescription([
        robot_state_publisher,
        rviz_node,
    ])
