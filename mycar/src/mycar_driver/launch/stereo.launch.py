"""
stereo.launch.py — 双目深度相机启动

基于 hobot_stereonet + mipi_cam，针对 mycar_f 适配:
  - 相机倒置安装 → mipi_rotation = 0.1
  - 点云 frame_id = camera_Link (与 URDF 一致)

依赖:
  - hobot_stereonet 包 (来自 TROS)
  - mipi_cam 包

用法:
  ros2 launch mycar_driver stereo.launch.py
  ros2 launch mycar_driver stereo.launch.py mipi_rotation:=0.0
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    # === 参数 ===
    mipi_rotation_arg = DeclareLaunchArgument(
        'mipi_rotation', default_value='0.1',
        description='MIPI 相机旋转角 (度)，倒置安装用 0.1')

    stereonet_frame_id_arg = DeclareLaunchArgument(
        'stereonet_frame_id', default_value='camera_Link',
        description='点云发布时的 frame_id (与 URDF camera_Link 一致)')

    publish_rectify_bgr_arg = DeclareLaunchArgument(
        'publish_rectify_bgr', default_value='True',
        description='发布 bgr8 矫正左图 (RTAB-Map RGB-D 模式需要)')

    publish_origin_enable_arg = DeclareLaunchArgument(
        'publish_origin_enable', default_value='False',
        description='发布原始图像 (调试用，默认关闭节省带宽)')

    publish_visual_enabled_arg = DeclareLaunchArgument(
        'publish_visual_enabled', default_value='False',
        description='发布可视化渲染图 (调试用，默认关闭)')

    publish_pcd_enabled_arg = DeclareLaunchArgument(
        'publish_pcd_enabled', default_value='0',
        description='发布点云 (0=关闭节省带宽, 1=开启)')

    pcd_downsample_arg = DeclareLaunchArgument(
        'pointcloud_downsample_step', default_value='8',
        description='点云降采样步长 (越大点数越少)，8=约7000点')

    # === hobot_stereonet 双目深度节点 ===
    # 复用 TROS 官方 launch 文件，只覆盖关键参数
    stereonet_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            get_package_share_directory('hobot_stereonet'),
            '/launch/stereonet_model_web_visual_v2.4_int16.launch.py'
        ]),
        launch_arguments={
            'stereonet_frame_id': LaunchConfiguration('stereonet_frame_id'),
            'mipi_rotation': LaunchConfiguration('mipi_rotation'),
            'mipi_image_width': '640',
            'mipi_image_height': '352',
            'mipi_image_framerate': '30.0',
            'mipi_gdc_enable': 'True',
            'mipi_lpwm_enable': 'True',
            'mipi_channel': '2',
            'mipi_channel2': '0',
            'mipi_cal_rotation': '0.0',
            'use_mipi_cam': 'True',
            'render_type': 'distance',
            'pointcloud_height_min': '-5.0',
            'pointcloud_height_max': '5.0',
            'pointcloud_depth_max': '5.0',
            'infer_thread_num': '2',
            'publish_rectify_bgr': LaunchConfiguration('publish_rectify_bgr'),
            'publish_origin_enable': LaunchConfiguration('publish_origin_enable'),
            'publish_visual_enabled': LaunchConfiguration('publish_visual_enabled'),
            'publish_pcd_enabled': LaunchConfiguration('publish_pcd_enabled'),
            'pointcloud_downsample_step': LaunchConfiguration('pointcloud_downsample_step'),
        }.items(),
    )

    return LaunchDescription([
        mipi_rotation_arg,
        stereonet_frame_id_arg,
        publish_rectify_bgr_arg,
        publish_origin_enable_arg,
        publish_visual_enabled_arg,
        publish_pcd_enabled_arg,
        pcd_downsample_arg,
        stereonet_launch,
    ])
