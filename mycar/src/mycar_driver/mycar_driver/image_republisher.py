#!/usr/bin/env python3
"""
image_republisher.py — 修正 stereonet 图像时间戳 + 格式转换

hobot_stereonet 的输出:
  - rectify_left_image: mono16 (V2.4_int16 模型输出 16 位灰度)
  - stereonet_depth:    16UC1 (毫米)
  - 时间戳: realtime (系统启动秒数), 与 ROS Unix epoch 不兼容

本节点:
  1. 将 rectify_left_image 从 mono16 转为 mono8 (RTAB-Map 需要)
  2. 用当前 ROS 时间替换所有 header.stamp
  3. 透传 camera_info

用法:
  ros2 run mycar_driver image_republisher
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
import numpy as np


class ImageRepublisher(Node):
    def __init__(self):
        super().__init__('image_republisher')

        # 发布修正时间戳后的图像
        self._pub_rgb = self.create_publisher(Image, '~/rgb_fixed', 10)
        self._pub_depth = self.create_publisher(Image, '~/depth_fixed', 10)
        self._pub_rgb_info = self.create_publisher(CameraInfo, '~/rgb_camera_info_fixed', 10)

        # 订阅原始话题
        self._sub_rgb = self.create_subscription(
            Image, '/StereoNetNode/rectify_left_image', self._rgb_callback, 10)
        self._sub_depth = self.create_subscription(
            Image, '/StereoNetNode/stereonet_depth', self._depth_callback, 10)
        self._sub_rgb_info = self.create_subscription(
            CameraInfo, '/StereoNetNode/rectify_left_image/camera_info',
            self._rgb_info_callback, 10)

        self._rgb_encoding_logged = False
        self._depth_encoding_logged = False
        self.get_logger().info('图像时间戳修正+格式转换已启动')

    def _rgb_callback(self, msg: Image):
        """修正时间戳 + 必要时格式转换 (bgr8/mono8 直接透传)"""
        now = self.get_clock().now().to_msg()

        if not self._rgb_encoding_logged:
            self.get_logger().info(f'RGB 输入编码: {msg.encoding}, {msg.width}x{msg.height}, step={msg.step}')
            self._rgb_encoding_logged = True

        # bgr8/mono8: RTAB-Map 原生支持, 直接透传, 只改时间戳
        if msg.encoding in ('bgr8', 'rgb8', 'mono8'):
            msg.header.stamp = now
            self._pub_rgb.publish(msg)
            return

        # 16-bit 灰度 → mono8
        if msg.encoding in ('mono16', '16UC1', '16SC1'):
            data = np.frombuffer(msg.data, dtype=np.uint16)
            data8 = (data >> 8).astype(np.uint8)
        else:
            self.get_logger().warn(f'未知 RGB 编码 {msg.encoding}, 按 16-bit 处理', throttle_duration_sec=5.0)
            data = np.frombuffer(msg.data, dtype=np.uint16)
            data8 = (data >> 8).astype(np.uint8)

        out = Image()
        out.header.stamp = now
        out.header.frame_id = msg.header.frame_id
        out.height = msg.height
        out.width = msg.width
        out.encoding = 'mono8'
        out.is_bigendian = False
        out.step = msg.width
        out.data = data8.tobytes()
        self._pub_rgb.publish(out)

    def _depth_callback(self, msg: Image):
        """深度图: 修正时间戳 + 修正编码 (mono16 → 16UC1, RTAB-Map 需要)"""
        now = self.get_clock().now().to_msg()
        if not self._depth_encoding_logged:
            self.get_logger().info(f'深度输入编码: {msg.encoding}, {msg.width}x{msg.height}, step={msg.step}')
            self._depth_encoding_logged = True
        msg.header.stamp = now
        # RTAB-Map 只认 16UC1(mm) 和 32FC1(m), mono16 不识别
        if msg.encoding == 'mono16':
            msg.encoding = '16UC1'
        # 诊断深度值范围 (仅首次)
        if not getattr(self, '_depth_val_logged', False):
            self._depth_val_logged = True
            data = np.frombuffer(msg.data, dtype=np.uint16)
            nonzero = data[data > 0]
            if len(nonzero) > 0:
                self.get_logger().info(
                    f'深度值范围: min={np.min(nonzero)}, max={np.max(nonzero)}, '
                    f'median={np.median(nonzero):.0f}, nonzero={len(nonzero)}/{len(data)}')
            else:
                self.get_logger().error('深度图全为零！')
        self._pub_depth.publish(msg)

    def _rgb_info_callback(self, msg: CameraInfo):
        """camera_info: 时间戳修正, 填充 P 矩阵, 保证 depth→3D 投影正确"""
        now = self.get_clock().now().to_msg()
        msg.header.stamp = now

        # 诊断: 输出 K 和 P 矩阵 (仅首次)
        if not getattr(self, '_info_logged', False):
            self._info_logged = True
            self.get_logger().info(
                f'K=[{msg.k[0]:.2f},0,{msg.k[2]:.2f}, 0,{msg.k[4]:.2f},{msg.k[5]:.2f}, 0,0,1] '
                f'P=[{msg.p[0]:.2f},{msg.p[1]:.2f},{msg.p[2]:.2f},{msg.p[3]:.2f}, '
                f'{msg.p[4]:.2f},{msg.p[5]:.2f},{msg.p[6]:.2f},{msg.p[7]:.2f}, '
                f'{msg.p[8]:.2f},{msg.p[9]:.2f},{msg.p[10]:.2f},{msg.p[11]:.2f}]')

        # 确保 P 矩阵有效 (若 K 有值但 P[0]==0, 从 K 复制)
        if msg.k[0] != 0.0 and msg.p[0] == 0.0:
            msg.p[0] = msg.k[0]   # fx
            msg.p[2] = msg.k[2]   # cx
            msg.p[5] = msg.k[4]   # fy
            msg.p[6] = msg.k[5]   # cy
            msg.p[10] = 1.0
            self.get_logger().info('P 矩阵已从 K 填充', throttle_duration_sec=5.0)

        self._pub_rgb_info.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(ImageRepublisher())
    rclpy.shutdown()
