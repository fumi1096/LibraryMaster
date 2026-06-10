"""
mycar_f URDF 可视化启动文件
用法: ros2 launch mycar_f display.launch.py
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_f')
    urdf_path = os.path.join(pkg_dir, 'urdf', 'mycar_f.urdf')

    model_arg = DeclareLaunchArgument(
        'model', default_value=str(urdf_path),
        description='URDF 文件路径')

    robot_description = ParameterValue(
        Command(['cat ', LaunchConfiguration('model')]),
        value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description}],
    )

    joint_state_publisher_gui = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
    )

    rviz_config = os.path.join(pkg_dir, '..', '..', '..', '..',
                               'car', 'src', 'yahboomcar_description',
                               'rviz', 'yahboomcar.rviz')
    rviz2 = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config] if os.path.exists(rviz_config) else [],
    )

    return LaunchDescription([
        model_arg,
        robot_state_publisher,
        joint_state_publisher_gui,
        rviz2,
    ])
