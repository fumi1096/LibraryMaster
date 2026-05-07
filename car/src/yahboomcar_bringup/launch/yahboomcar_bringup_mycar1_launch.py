"""
mycar1 小车启动文件
适用车型：四轮独立驱动、差速转向的普通轮小车

启动的节点：
1. FourWD_driver    - 四驱驱动节点（硬件通信、传感器采集）
2. base_node_fourwd - 里程计节点（速度积分、位姿估计、TF发布）
3. robot_state_publisher - URDF模型发布
4. joint_state_publisher - 关节状态发布
5. imu_filter_madgwick   - IMU滤波器（可选）
6. robot_localization/ekf - EKF融合定位（可选）
"""

from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import os
from ament_index_python.packages import get_package_share_directory
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

print("--------------------- robot_type = mycar1 (FourWD) ---------------------")


def generate_launch_description():
    # 获取 mycar1 模型的 URDF 路径（使用绝对路径）
    mycar1_urdf_path = os.path.join(
        get_package_share_path('yahboomcar_description'),
        '../../mycar1/urdf/mycar1.urdf'
    )
    # 如果需要在 ROS2 包中查找，使用以下方式（需将 mycar1 注册为 ROS2 包）
    # from ament_index_python.packages import get_package_share_path
    # mycar1_urdf_path = get_package_share_path('mycar1') / 'urdf/mycar1.urdf'

    default_rviz_config_path = os.path.join(
        get_package_share_directory('yahboomcar_description'),
        'rviz', 'yahboomcar.rviz'
    )

    # === 启动参数 ===
    gui_arg = DeclareLaunchArgument(
        name='gui', default_value='false',
        choices=['true', 'false'],
        description='是否启用 joint_state_publisher_gui'
    )
    model_arg = DeclareLaunchArgument(
        name='model', default_value=str(mycar1_urdf_path),
        description='机器人 URDF 文件路径'
    )
    rviz_arg = DeclareLaunchArgument(
        name='rvizconfig', default_value=str(default_rviz_config_path),
        description='RViz 配置文件路径'
    )
    pub_odom_tf_arg = DeclareLaunchArgument(
        'pub_odom_tf', default_value='true',
        description='是否由里程计节点发布 odom → base_footprint TF（使用EKF时设为false）'
    )

    # URDF 加载
    robot_description = ParameterValue(
        Command(['cat ', LaunchConfiguration('model')]),
        value_type=str
    )

    # === 节点定义 ===

    # 机器人状态发布器（发布URDF模型到TF）
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description}]
    )

    # 关节状态发布器
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        condition=UnlessCondition(LaunchConfiguration('gui'))
    )

    joint_state_publisher_gui_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        condition=IfCondition(LaunchConfiguration('gui'))
    )

    # RViz2 可视化（默认注释掉，需要时取消注释）
    # rviz_node = Node(
    #     package='rviz2',
    #     executable='rviz2',
    #     name='rviz2',
    #     output='screen',
    #     arguments=['-d', LaunchConfiguration('rvizconfig')],
    # )

    # 四驱驱动节点（与驱动板通信、采集传感器数据）
    driver_node = Node(
        package='yahboomcar_bringup',
        executable='FourWD_driver',
    )

    # 里程计节点（根据 vel_raw 积分计算里程计）
    base_node = Node(
        package='yahboomcar_base_node',
        executable='base_node_fourwd',
        parameters=[{'pub_odom_tf': LaunchConfiguration('pub_odom_tf')}]
    )

    # IMU 滤波器（可选，需要安装 imu_filter_madgwick 包）
    imu_filter_config = os.path.join(
        get_package_share_directory('yahboomcar_bringup'),
        'param',
        'imu_filter_param.yaml'
    )
    imu_filter_node = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        parameters=[imu_filter_config]
    )

    # EKF 融合定位（可选，需要安装 robot_localization 包）
    # ekf_node = IncludeLaunchDescription(
    #     PythonLaunchDescriptionSource([os.path.join(
    #         get_package_share_directory('robot_localization'), 'launch'),
    #         '/ekf_x1_x3_launch.py'])
    # )

    return LaunchDescription([
        gui_arg,
        model_arg,
        rviz_arg,
        pub_odom_tf_arg,
        joint_state_publisher_node,
        joint_state_publisher_gui_node,
        robot_state_publisher_node,
        # rviz_node,
        driver_node,
        base_node,
        imu_filter_node,
        # ekf_node,
    ])
