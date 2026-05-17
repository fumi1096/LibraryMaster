"""
mycar00 SLAM 建图启动文件 — PC 端运行

依赖：
- 嵌入式端已启动核心节点（start_mycar00.sh embedded）
- 嵌入式端已在发布 /scan、/odom、TF

启动：
  ros2 launch mycar_slam slam_pc.launch.py

地图保存：
  建图完成后在 PC 端另开终端：
  ros2 run nav2_map_server map_saver_cli -f ~/mycar_map
"""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import os


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_slam')
    slam_config = os.path.join(pkg_dir, 'config', 'slam_toolbox_mapping.yaml')

    # === 参数 ===
    slam_params_arg = DeclareLaunchArgument(
        'slam_params_file', default_value=slam_config,
        description='slam_toolbox 参数文件路径'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='是否使用仿真时间'
    )

    # === slam_toolbox (online async) ===
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            LaunchConfiguration('slam_params_file'),
            {'use_sim_time': LaunchConfiguration('use_sim_time')},
        ],
    )

    # === RViz2 ===
    rviz_config = os.path.join(pkg_dir, '..', '..', 'yahboomcar_description',
                               'rviz', 'yahboomcar.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
    )

    return LaunchDescription([
        slam_params_arg,
        use_sim_time_arg,
        slam_toolbox_node,
        rviz_node,
    ])
