#!/usr/bin/env python3
"""
image_relay.py — PC 端压缩图像中继节点

VPN 传输压缩图像，本节点在 PC 本地解压为 raw Image，
供 RTAB-Map 本地订阅（避免 RELIABLE QoS 在 VPN 上丢帧）。

管线:
  车端 (VPN) → CompressedImage ─→ 本节点 ─→ 本地 Image → RTAB-Map
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, CompressedImage
import numpy as np
import cv2


class ImageRelay(Node):
    def __init__(self):
        super().__init__('image_relay')

        # --- 发布 raw (本地, RTAB-Map 订阅) ---
        self._pub_rgb = self.create_publisher(Image, '~/rgb_raw', 10)
        self._pub_depth = self.create_publisher(Image, '~/depth_raw', 10)
        self._pub_info = self.create_publisher(CameraInfo, '~/camera_info_raw', 10)

        # --- 订阅 compressed (来自车端 VPN) ---
        self._sub_rgb = self.create_subscription(
            CompressedImage, '/image_republisher/rgb_fixed/compressed',
            self._rgb_callback, 10)
        self._sub_depth = self.create_subscription(
            CompressedImage, '/image_republisher/depth_fixed/compressedDepth',
            self._depth_callback, 10)
        self._sub_info = self.create_subscription(
            CameraInfo, '/image_republisher/rgb_camera_info_fixed',
            self._info_callback, 10)

        self.get_logger().info('图像中继已启动 (compressed → raw)')

    def _rgb_callback(self, msg: CompressedImage):
        try:
            data = np.frombuffer(msg.data, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is None:
                self.get_logger().error('JPEG 解码失败', throttle_duration_sec=5.0)
                return

            out = Image()
            out.header = msg.header
            img = cv2.flip(img, -1)
            out.height, out.width = img.shape[:2]
            out.encoding = 'bgr8'
            out.is_bigendian = False
            out.step = out.width * 3
            out.data = img.tobytes()
            self._pub_rgb.publish(out)
        except Exception as e:
            self.get_logger().error(f'RGB 解码异常: {e}', throttle_duration_sec=5.0)

    def _depth_callback(self, msg: CompressedImage):
        try:
            data = np.frombuffer(msg.data, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
            if img is None:
                self.get_logger().error('PNG 深度解码失败', throttle_duration_sec=5.0)
                return

            out = Image()
            out.header = msg.header
            img = cv2.flip(img, -1)
            out.height, out.width = img.shape[:2]
            out.encoding = '16UC1'
            out.is_bigendian = False
            out.step = out.width * 2
            out.data = img.tobytes()
            self._pub_depth.publish(out)
        except Exception as e:
            self.get_logger().error(f'深度解码异常: {e}', throttle_duration_sec=5.0)

    def _info_callback(self, msg: CameraInfo):
        self._pub_info.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(ImageRelay())
    rclpy.shutdown()
