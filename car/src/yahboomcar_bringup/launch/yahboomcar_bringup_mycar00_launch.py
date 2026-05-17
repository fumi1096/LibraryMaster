"""
mycar00 小车启动文件（v2.0 - 分布式架构）
适用车型：四轮独立驱动、差速转向的普通轮小车（带摄像头绑定）

启动的节点：
1. FourWD_driver       - 四驱驱动节点（硬件通信、传感器采集）
2. base_node_fourwd    - 里程计节点（速度积分、位姿估计）
3. robot_state_publisher   - URDF 模型 TF 发布
4. joint_state_publisher   - 关节状态发布
5. imu_filter_madgwick     - IMU 滤波
6. robot_localization/ekf  - EKF 融合定位（默认启用）
7. [可选] camera_scan 管线 - 双目点云→LaserScan
8. [可选] RViz2            - 可视化（PC 端使用）

分布式部署模式：
- embedded：驱动 + 里程计 + IMU + 相机管线 + URDF TF + EKF（嵌入式全栈）
- PC：嵌入式提供数据，PC 运行 SLAM + RViz + 键盘遥控
"""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import os

print("=" * 60)
print("mycar00 (FourWD + Camera) — 分布式 ROS2 启动")
print("=" * 60)


def generate_launch_description():
    pkg_bringup = get_package_share_directory('yahboomcar_bringup')
    pkg_desc = get_package_share_directory('yahboomcar_description')
    pkg_mycar00 = get_package_share_directory('mycar00')

    # mycar00 URDF 路径
    mycar00_urdf_path = os.path.join(pkg_mycar00, 'urdf', 'mycar00.urdf')

    # ============================================
    # 启动参数
    # ============================================
    model_arg = DeclareLaunchArgument(
        'model', default_value=str(mycar00_urdf_path),
        description='URDF 文件路径'
    )
    gui_arg = DeclareLaunchArgument(
        'gui', default_value='false',
        choices=['true', 'false'],
        description='启用 joint_state_publisher_gui'
    )
    pub_odom_tf_arg = DeclareLaunchArgument(
        'pub_odom_tf', default_value='false',
        description='base_node 是否发布 odom→base_footprint TF（EKF 启用时须为 false）'
    )
    use_ekf_arg = DeclareLaunchArgument(
        'use_ekf', default_value='true',
        choices=['true', 'false'],
        description='是否启用 EKF 融合定位（建图/导航必须启用）'
    )
    use_camera_arg = DeclareLaunchArgument(
        'use_camera', default_value='true',
        choices=['true', 'false'],
        description='是否启动双目相机 + LaserScan 管线'
    )
    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='false',
        choices=['true', 'false'],
        description='是否启动 RViz2（嵌入式默认关闭，PC 端手动开）'
    )

    # ============================================
    # URDF
    # ============================================
    robot_description = ParameterValue(
        Command(['cat ', LaunchConfiguration('model')]),
        value_type=str
    )

    # ============================================
    # 核心节点（始终启动）
    # ============================================

    # ---- 机器人状态发布器 ----
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description}],
    )

    # ---- 关节状态发布器 ----
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        condition=UnlessCondition(LaunchConfiguration('gui')),
    )
    joint_state_publisher_gui_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        condition=IfCondition(LaunchConfiguration('gui')),
    )

    # ---- 四驱驱动节点 ----
    driver_node = Node(
        package='yahboomcar_bringup',
        executable='FourWD_driver',
    )

    # ---- 里程计节点 ----
    base_node = Node(
        package='yahboomcar_base_node',
        executable='base_node_fourwd',
        parameters=[{'pub_odom_tf': LaunchConfiguration('pub_odom_tf')}],
    )

    # ---- IMU 滤波 ----
    imu_filter_config = os.path.join(pkg_bringup, 'param', 'imu_filter_param.yaml')
    imu_filter_node = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        parameters=[imu_filter_config],
    )

    # ============================================
    # EKF 融合定位（默认启用）
    # ============================================
    ekf_config_path = os.path.join(pkg_bringup, 'param', 'ekf_mycar00.yaml')
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_se_odom',
        output='screen',
        parameters=[ekf_config_path],
        condition=IfCondition(LaunchConfiguration('use_ekf')),
    )

    # ============================================
    # 相机管线（默认启用）
    # ============================================
    # camera_scan.launch.py 已纳入 yahboomcar_bringup 包
    camera_scan_launch_path = os.path.join(pkg_bringup, 'launch', 'camera_scan.launch.py')
    camera_scan_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(camera_scan_launch_path),
        condition=IfCondition(LaunchConfiguration('use_camera')),
    )

    # ============================================
    # RViz2（默认关闭，PC 端手动开启）
    # ============================================
    rviz_config = os.path.join(pkg_desc, 'rviz', 'yahboomcar.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    # ============================================
    # LaunchDescription
    # ============================================
    return LaunchDescription([
        # 参数
        model_arg, gui_arg, pub_odom_tf_arg,
        use_ekf_arg, use_camera_arg, use_rviz_arg,
        # 核心节点
        robot_state_publisher_node,
        joint_state_publisher_node,
        joint_state_publisher_gui_node,
        driver_node,
        base_node,
        imu_filter_node,
        # 可选节点
        ekf_node,
        camera_scan_launch,
        rviz_node,
    ])
