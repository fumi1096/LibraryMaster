"""
image_republish.launch.py — 图像时间戳 + 编码修正 (RGB-D 模式)

启动 image_republisher 节点:
  1. /StereoNetNode/rectify_left_image → ~/rgb_fixed (bgr8, epoch时间戳)
  2. /StereoNetNode/stereonet_depth     → ~/depth_fixed (mono16→16UC1, epoch时间戳)
  3. /StereoNetNode/rectify_left_image/camera_info → ~/rgb_camera_info_fixed

用于 RTAB-Map RGB-D 模式，解决:
  - 时间戳不兼容 (realtime → epoch)
  - 深度图编码不兼容 (mono16 → 16UC1)
  - P 矩阵为空 (从 K 填充)

用法:
  ros2 launch mycar_driver image_republish.launch.py
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    image_republish_node = Node(
        package='mycar_driver',
        executable='image_republish',
        name='image_republisher',
        output='screen',
    )

    return LaunchDescription([
        image_republish_node,
    ])
