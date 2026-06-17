"""
rtabmap_rgbd_pc.launch.py — RTAB-Map RGB-D 分布式建图 (PC 端)

管线:
  小车端:
    hobot_stereonet  → /StereoNetNode/rectify_left_image (bgr8, realtime ts)
                     → /StereoNetNode/stereonet_depth     (mono16, realtime ts)
    image_republisher → /image_republisher/rgb_fixed       (bgr8, epoch)
                      → /image_republisher/rgb_fixed/compressed (JPEG, ~50KB/帧)
                      → /image_republisher/depth_fixed     (16UC1, epoch)
                      → /image_republisher/depth_fixed/compressedDepth (PNG 无损)
                      → /image_republisher/rgb_camera_info_fixed
    EKF              → /odom

  PC 端:
    RTAB-Map RGB-D 模式 (compressed RGB + compressedDepth, VPN 带宽友好)
    robot_state_publisher (本地 URDF, 确保 TF 可用)

输出:
  /rtabmap/cloud_map    — 3D 点云地图
  /rtabmap/grid_map     — 2D 占据栅格地图
  /rtabmap/mapGraph     — 位姿图
  ~/.ros/rtabmap.db     — 数据库

用法:
  ros2 launch mycar_rtabmap rtabmap_rgbd_pc.launch.py
  ros2 launch mycar_rtabmap rtabmap_rgbd_pc.launch.py use_rviz:=false
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

    # === 参数 ===
    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        choices=['true', 'false'],
        description='启动 RViz2 可视化')

    database_path_arg = DeclareLaunchArgument(
        'database_path', default_value='~/.ros/rtabmap.db',
        description='RTAB-Map 数据库路径 (默认 ~/.ros/rtabmap.db)')

    # === robot_state_publisher (本地 URDF, 确保 camera_Link→base_footprint TF 可用) ===
    model_path = os.path.join(pkg_mycar_f, 'urdf', 'mycar_f.urdf')
    robot_description = ParameterValue(
        Command(['cat ', model_path]), value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': robot_description,
            'publish_robot_description': True,  # 发布 /robot_description 供 RViz 显示模型
        }],
    )

    # === 图像中继: VPN 压缩 → 本地 raw (解决 VPN RELIABLE QoS 丢帧) ===
    image_relay = Node(
        package='mycar_rtabmap',
        executable='image_relay',
        name='image_relay',
        output='screen',
    )

    # === RTAB-Map RGB-D 节点 ===
    rtabmap_config = os.path.join(pkg_dir, 'config', 'rtabmap_rgbd.yaml')
    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        parameters=[rtabmap_config, {
            'database_path': LaunchConfiguration('database_path'),
        }],
        remappings=[
            # RGB + Depth → 来自本地中继 (已解压)
            ('rgb/image',        '/image_relay/rgb_raw'),
            ('rgb/camera_info',  '/image_relay/camera_info_raw'),
            ('depth/image',      '/image_relay/depth_raw'),
            ('depth/camera_info','/image_relay/camera_info_raw'),
            # 里程计 → 直接来自车端 (小话题, VPN 可靠)
            ('odom',             '/odom'),
        ],
    )

    # === RViz2 ===
    rviz_config = os.path.join(pkg_dir, 'config', 'rtabmap_mapping.rviz')
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
        database_path_arg,
        robot_state_publisher,
        image_relay,
        rtabmap_node,
        rviz_node,
    ])
