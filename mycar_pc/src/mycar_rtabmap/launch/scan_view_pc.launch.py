"""
scan_view_pc.launch.py — PC 端轻量 LaserScan 监看（无 SLAM）

仅启动:
  - robot_state_publisher (本地 URDF, RViz RobotModel 后备)
  - RViz2 (预配置: LaserScan + TF + RobotModel, Fixed Frame=odom)

小车端需先启动 bringup:
  cd mycar && ./start_mycar.sh mapping_distributed

用法:
  ros2 launch mycar_rtabmap scan_view_pc.launch.py
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import Command


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_rtabmap')
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
    # RViz2 (预配置: LaserScan + TF + RobotModel + Odometry)
    # ============================================
    rviz_config = os.path.join(pkg_dir, 'config', 'scan_view_pc.rviz')

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
