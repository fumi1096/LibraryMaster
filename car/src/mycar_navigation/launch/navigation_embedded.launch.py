"""
mycar00 自主导航启动文件 — 嵌入式端运行

依赖：
- 嵌入式端已启动核心节点（start_mycar00.sh embedded）
- /scan、/odom、TF 已正常发布
- 地图文件已预先保存到 mycar_navigation/maps/

启动：
  ros2 launch mycar_navigation navigation_embedded.launch.py

或通过 start_mycar00.sh 启动：
  ./start_mycar00.sh navigate /path/to/map.yaml
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LoadComposableNodes, Node, PushRosNamespace
from launch_ros.descriptions import ComposableNode
import yaml


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_navigation')
    nav2_params = os.path.join(pkg_dir, 'config', 'nav2_params.yaml')

    # === 参数 ===
    map_arg = DeclareLaunchArgument(
        'map', default_value=os.path.join(pkg_dir, 'maps', 'mycar_map.yaml'),
        description='地图 YAML 文件路径'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='使用仿真时间'
    )
    autostart_arg = DeclareLaunchArgument(
        'autostart', default_value='true',
        description='自动激活 Nav2 生命周期节点'
    )

    # === Map Server ===
    map_server_node = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[
            nav2_params,
            {'yaml_filename': LaunchConfiguration('map')},
        ],
    )

    # === AMCL 定位 ===
    amcl_node = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[nav2_params],
    )

    # === 规划器 (Planner) ===
    planner_node = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='screen',
        parameters=[nav2_params],
    )

    # === 控制器 (Controller — DWB) ===
    controller_node = Node(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        output='screen',
        parameters=[nav2_params],
    )

    # === 行为服务器 (Behavior) ===
    behavior_node = Node(
        package='nav2_behaviors',
        executable='behavior_server',
        name='behavior_server',
        output='screen',
        parameters=[nav2_params],
    )

    # === BT Navigator ===
    bt_node = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[nav2_params],
    )

    # === Lifecycle Manager (管理以上节点的生命周期) ===
    lifecycle_node = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[
            {'use_sim_time': LaunchConfiguration('use_sim_time')},
            {'autostart': LaunchConfiguration('autostart')},
            {'node_names': [
                'map_server',
                'amcl',
                'planner_server',
                'controller_server',
                'behavior_server',
                'bt_navigator',
            ]},
        ],
    )

    # === Costmap 节点 ===
    # global_costmap + local_costmap 已在 nav2_params.yaml 中配置
    # 使用独立节点加载 costmap（避免 lifecycle 问题）

    return LaunchDescription([
        map_arg,
        use_sim_time_arg,
        autostart_arg,
        map_server_node,
        amcl_node,
        planner_node,
        controller_node,
        behavior_node,
        bt_node,
        lifecycle_node,
    ])
