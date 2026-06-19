"""
slam2d_pc.launch.py — 分布式 2D 建图 PC 端

管线:
  小车端 (mycar):
    bringup (driver + EKF + 双目相机 + LaserScan)
    → /scan (LaserScan)
    → /odom (EKF 融合里程计)
    → TF 树 (odom→base_footprint)
    → /robot_description (RobotModel)

  PC 端 (mycar_pc):
    slam_toolbox (online_async) → /map
    robot_state_publisher  → 本地 /robot_description (RViz RobotModel 后备)
    RViz2  → 可视化 /map + /scan + TF + RobotModel

用法:
  # 先启动小车端:
  #   cd mycar && ./start_mycar.sh mapping_distributed
  # 再启动 PC 端:
  #   cd mycar_pc && ./start_pc.sh mapping2d

建图完成后保存地图:
  ros2 run nav2_map_server map_saver_cli -f ~/mycar_map
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_rtabmap')
    pkg_mycar_f = get_package_share_directory('mycar_f')

    # ============================================
    # 参数
    # ============================================
    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        choices=['true', 'false'],
        description='启动 RViz2 可视化')

    # ============================================
    # slam_toolbox (online async)
    # 接收 /scan + /odom (来自小车端, DDS 跨网络)
    # 发布 /map + map→odom TF
    # ============================================
    slam_config = os.path.join(pkg_dir, 'config', 'slam_toolbox_mapping.yaml')

    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_config],
    )

    # ============================================
    # robot_state_publisher (本地 URDF, 确保 RViz RobotModel 可靠显示)
    # 小车端也发布了 /robot_description, 但跨网络可能不可靠
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
    # RViz2 (预配置: Map + LaserScan + TF + RobotModel, Fixed Frame=map)
    # ============================================
    rviz_config = os.path.join(pkg_dir, 'config', 'slam_mapping_pc.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    return LaunchDescription([
        use_rviz_arg,
        slam_toolbox_node,
        robot_state_publisher,
        rviz_node,
    ])
