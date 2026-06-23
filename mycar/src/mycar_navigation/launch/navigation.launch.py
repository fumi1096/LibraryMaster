"""
navigation.launch.py — mycar Nav2 自主导航启动文件

启动:
  1. bringup (驱动 + EKF + 双目相机 + LaserScan)
  2. map_server (加载预建地图)
  3. AMCL (自适应蒙特卡洛定位)
  4. planner_server (SmacPlanner2D 全局规划)
  5. controller_server (DWB 局部跟随 → /cmd_vel)
  6. velocity_smoother (速度平滑)
  7. behavior_server (恢复行为: spin, backup, wait)
  8. bt_navigator (行为树协调)
  9. lifecycle_manager (自动激活/管理所有节点)
 10. map_keepalive (每秒重发 /map, 确保 PC 端收到)
 11. waypoint_saver (航点保存与导航)
 12. [可选] RViz2

依赖话题:
  /scan (LaserScan, 10Hz, 双目深度→LaserScan)
  /odom (EKF 融合里程计)
  TF 树 (odom→base_footprint, 来自 robot_state_publisher + EKF)

输出:
  /cmd_vel → driver_node (MCU 电机控制)

参数:
  map          — 地图文件路径 (默认: 包内 maps/mycar_map.yaml)
  use_rviz     — 是否启动 RViz2 (默认 false)
  use_sim_time — 仿真时间 (默认 false)

用法:
  # 全本地导航
  ros2 launch mycar_navigation navigation.launch.py

  # 指定地图
  ros2 launch mycar_navigation navigation.launch.py map:=/path/to/map.yaml

  # 本地 + RViz
  ros2 launch mycar_navigation navigation.launch.py use_rviz:=true
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, Command
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_nav = get_package_share_directory('mycar_navigation')
    pkg_driver = get_package_share_directory('mycar_driver')

    # ============================================
    # 参数
    # ============================================
    default_map = os.path.join(pkg_nav, 'maps', 'mycar_map.yaml')

    map_arg = DeclareLaunchArgument(
        'map', default_value=default_map,
        description='地图文件 (.yaml) 路径')

    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='false',
        choices=['true', 'false'],
        description='启动 RViz2')

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        choices=['true', 'false'],
        description='使用仿真时间')

    serial_port_arg = DeclareLaunchArgument(
        'serial_port', default_value='/dev/ttyUSB0',
        description='串口设备路径')

    # ============================================
    # Nav2 参数文件
    # ============================================
    nav2_params = os.path.join(pkg_nav, 'config', 'nav2_params.yaml')

    # ============================================
    # 1. bringup (复用 mycar_driver)
    # ============================================
    bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_driver, 'launch', 'bringup.launch.py')
        ]),
        launch_arguments={
            'serial_port': LaunchConfiguration('serial_port'),
            'use_ekf': 'true',
            'use_camera': 'true',
            'use_rviz': 'false',
        }.items(),
    )

    # ============================================
    # 1.5 静态 TF: map→odom (回退用, AMCL 激活后会覆盖)
    #     确保 RViz 在 AMCL 收到 /initialpose 前就能渲染地图
    # ============================================
    static_map_to_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_map_to_odom',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}],
    )

    # ============================================
    # 2. map_server
    # ============================================
    map_server_node = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[nav2_params, {
            'yaml_filename': LaunchConfiguration('map'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ============================================
    # 3. AMCL
    # ============================================
    amcl_node = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[nav2_params, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ============================================
    # 4. planner_server
    # ============================================
    planner_server_node = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='screen',
        parameters=[nav2_params, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ============================================
    # 5. controller_server
    # ============================================
    controller_server_node = Node(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        output='screen',
        parameters=[nav2_params, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
        # DWB 输出 /cmd_vel → velocity_smoother → /cmd_vel (驱动节点订阅)
    )

    # ============================================
    # 6. velocity_smoother
    #    平滑 /cmd_vel 输出, 防止急加速
    # ============================================
    velocity_smoother_node = Node(
        package='nav2_velocity_smoother',
        executable='velocity_smoother',
        name='velocity_smoother',
        output='screen',
        parameters=[nav2_params, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
        remappings=[
            ('cmd_vel', '/cmd_vel_nav'),          # 输入: 来自 controller_server
            ('cmd_vel_smoothed', '/cmd_vel'),     # 输出: 驱动节点订阅
        ],
    )

    # ============================================
    # 7. behavior_server
    # ============================================
    behavior_server_node = Node(
        package='nav2_behaviors',
        executable='behavior_server',
        name='behavior_server',
        output='screen',
        parameters=[nav2_params, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ============================================
    # 8. bt_navigator
    # ============================================
    bt_navigator_node = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[nav2_params, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ============================================
    # 9. lifecycle_manager (自动激活所有节点)
    # ============================================
    lifecycle_manager_node = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager',
        output='screen',
        parameters=[nav2_params, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    map_keepalive_cmd = ExecuteProcess(
        cmd=['python3', '-u', '-c', r'''
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from nav_msgs.msg import OccupancyGrid

class MapKeepalive(Node):
    def __init__(self):
        super().__init__("map_keepalive")
        qos = QoSProfile(depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._map = None
        self._sub = self.create_subscription(
            OccupancyGrid, "/map", self._cb, qos)
        self._pub = self.create_publisher(OccupancyGrid, "/map", 10)
        self._timer = self.create_timer(1.0, self._publish)
        self.get_logger().info("map_keepalive started, waiting for /map ...")

    def _cb(self, msg):
        if self._map is None:
            self.get_logger().info("map_keepalive: received /map")
        self._map = msg

    def _publish(self):
        if self._map is not None:
            self._map.header.stamp = self.get_clock().now().to_msg()
            self._pub.publish(self._map)

rclpy.init()
rclpy.spin(MapKeepalive())
'''],
        name='map_keepalive',
        output='screen',
    )

    # ============================================
    # 11. waypoint_saver — 航点保存与导航
    #     /save_waypoint → 保存当前位置  /goto_waypoint → 发布 /goal_pose
    #     /set_waypoint_name + RViz Publish Point → 点地图标点
    # ============================================
    waypoint_saver_node = Node(
        package='mycar_navigation',
        executable='waypoint_saver',
        name='waypoint_saver',
        output='screen',
        parameters=[{
            'map_path': LaunchConfiguration('map'),
        }],
    )

    # ============================================
    # 12. [可选] RViz2
    # ============================================
    rviz_config = os.path.join(pkg_nav, 'config', 'navigation.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    return LaunchDescription([
        map_arg,
        use_rviz_arg,
        use_sim_time_arg,
        serial_port_arg,
        bringup,
        static_map_to_odom,
        map_server_node,
        amcl_node,
        planner_server_node,
        controller_server_node,
        velocity_smoother_node,
        behavior_server_node,
        bt_navigator_node,
        lifecycle_manager_node,
        map_keepalive_cmd,
        waypoint_saver_node,
        rviz_node,
    ])
