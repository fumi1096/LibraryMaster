"""
bringup.launch.py — mycar_f 全栈启动入口 (全本地模式)

启动节点:
  1. robot_state_publisher   — URDF TF 发布
  2. driver_node             — 驱动节点 (串口通信 + 传感器 + 运动控制)
  3. odom_node               — 里程计节点 (速度积分 → /odom_raw)
  4. imu_filter_madgwick     — IMU 姿态滤波 (/imu/data_raw → /imu/data)
  5. ekf_node                — EKF 融合定位 (/odom_raw + /imu/data → /odom + TF)
  6. [可选] stereo.launch    — 双目深度相机
  7. [可选] laserscan.launch — 点云→LaserScan (/scan)
  8. [可选] RViz2            — 可视化

参数控制:
  use_ekf     — 是否启用 EKF (建图/导航必须)
  use_camera  — 是否启用双目相机管线
  use_rviz    — 是否启动 RViz2

用法:
  # 完整启动 (驱动 + EKF + 相机)
  ros2 launch mycar_driver bringup.launch.py

  # 无相机模式
  ros2 launch mycar_driver bringup.launch.py use_camera:=false

  # 调试模式 (仅驱动 + 里程计)
  ros2 launch mycar_driver bringup.launch.py use_ekf:=false use_camera:=false
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, Command
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_driver = get_package_share_directory('mycar_driver')
    pkg_mycar_f = get_package_share_directory('mycar_f')

    # ============================================
    # 参数
    # ============================================
    model_path = os.path.join(pkg_mycar_f, 'urdf', 'mycar_f.urdf')

    model_arg = DeclareLaunchArgument(
        'model', default_value=str(model_path),
        description='URDF 文件路径')

    serial_port_arg = DeclareLaunchArgument(
        'serial_port', default_value='/dev/ttyUSB0',
        description='串口设备路径')

    use_ekf_arg = DeclareLaunchArgument(
        'use_ekf', default_value='true',
        choices=['true', 'false'],
        description='启用 EKF 融合定位')

    use_camera_arg = DeclareLaunchArgument(
        'use_camera', default_value='true',
        choices=['true', 'false'],
        description='启用双目相机 + LaserScan 管线')

    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='false',
        choices=['true', 'false'],
        description='启动 RViz2')

    # ============================================
    # URDF → robot_description
    # ============================================
    robot_description = ParameterValue(
        Command(['cat ', LaunchConfiguration('model')]),
        value_type=str)

    # ============================================
    # 核心节点 (始终启动)
    # ============================================

    # 1. robot_state_publisher — URDF TF 树
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description}],
    )

    # 2. 驱动节点 — 串口 + 传感器 + 运动控制
    driver_params = os.path.join(pkg_driver, 'config', 'driver_params.yaml')
    driver_node = Node(
        package='mycar_driver',
        executable='driver_node',
        name='driver_node',
        output='screen',
        parameters=[driver_params, {
            'serial_port': LaunchConfiguration('serial_port'),
        }],
    )

    # 3. 里程计节点 — 速度积分
    odom_node = Node(
        package='mycar_driver',
        executable='odom_node',
        name='odom_node',
        output='screen',
        parameters=[{
            'pub_odom_tf': False,  # EKF 负责发布 TF
            'linear_scale': 1.0,
            'angular_scale': 1.0,
        }],
    )

    # 4. IMU 滤波 — /imu/data_raw → /imu/data
    imu_filter_config = os.path.join(pkg_driver, 'config', 'imu_filter.yaml')
    imu_filter_node = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        name='imu_filter',
        parameters=[imu_filter_config],
    )

    # ============================================
    # 可选: EKF 融合定位
    # ============================================
    ekf_config = os.path.join(pkg_driver, 'config', 'ekf_mycar.yaml')
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_se_odom',
        output='screen',
        parameters=[ekf_config],
        remappings=[('odometry/filtered', 'odom')],  # EKF默认输出话题→slam_toolbox期望的/odom
        condition=IfCondition(LaunchConfiguration('use_ekf')),
    )

    # ============================================
    # 可选: 双目相机 + LaserScan
    # ============================================
    stereo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_driver, 'launch', 'stereo.launch.py')
        ]),
        condition=IfCondition(LaunchConfiguration('use_camera')),
    )

    laserscan_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_driver, 'launch', 'laserscan.launch.py')
        ]),
        condition=IfCondition(LaunchConfiguration('use_camera')),
    )

    # ============================================
    # 可选: RViz2
    # ============================================
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    # ============================================
    # LaunchDescription
    # ============================================
    return LaunchDescription([
        model_arg,
        serial_port_arg,
        use_ekf_arg,
        use_camera_arg,
        use_rviz_arg,
        robot_state_publisher,
        driver_node,
        odom_node,
        imu_filter_node,
        ekf_node,
        stereo_launch,
        laserscan_launch,
        rviz_node,
    ])
