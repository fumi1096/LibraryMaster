#!/usr/bin/env python3
"""
image_republisher.py — 修正 stereonet 图像时间戳 + 格式转换 + JPEG 压缩

hobot_stereonet 的输出:
  - rectify_left_image: bgr8/mono16
  - stereonet_depth:    16UC1 (毫米)
  - 时间戳: realtime (系统启动秒数), 与 ROS Unix epoch 不兼容

本节点:
  1. 将 rectify_left_image 从 mono16 转为 mono8
  2. 用当前 ROS 时间替换所有 header.stamp
  3. 透传 camera_info, 填充 P 矩阵
  4. 发布 JPEG 压缩 RGB (大幅降低 VPN 带宽, 900KB→50KB)
  5. 发布 PNG 压缩深度 (无损, 600KB→200KB)

用法:
  ros2 run mycar_driver image_republisher
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, CompressedImage
import numpy as np

# cv2 可能未安装 (RDK X5 默认不含 opencv-python)
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class ImageRepublisher(Node):
    def __init__(self):
        super().__init__('image_republisher')

        # === 发布者: raw (本地调试用) ===
        self._pub_rgb = self.create_publisher(Image, '~/rgb_fixed', 10)
        self._pub_depth = self.create_publisher(Image, '~/depth_fixed', 10)
        self._pub_rgb_info = self.create_publisher(CameraInfo, '~/rgb_camera_info_fixed', 10)

        # === 发布者: compressed (VPN 传输用, 大幅节省带宽) ===
        if HAS_CV2:
            self._pub_rgb_compressed = self.create_publisher(
                CompressedImage, '~/rgb_fixed/compressed', 10)
            self._pub_depth_compressed = self.create_publisher(
                CompressedImage, '~/depth_fixed/compressedDepth', 10)
            self._jpeg_quality = 70
            self.get_logger().info(
                '图像修正+压缩已启动 (RGB JPEG q=%d, Depth PNG)' % self._jpeg_quality)
        else:
            self.get_logger().warn(
                '⚠️  cv2 (opencv-python) 未安装，压缩功能禁用！'
                ' 安装: pip3 install opencv-python')
            self.get_logger().info('图像修正已启动 (仅 raw 传输)')

        # === 订阅原始话题 ===
        self._sub_rgb = self.create_subscription(
            Image, '/StereoNetNode/rectify_left_image', self._rgb_callback, 10)
        self._sub_depth = self.create_subscription(
            Image, '/StereoNetNode/stereonet_depth', self._depth_callback, 10)
        self._sub_rgb_info = self.create_subscription(
            CameraInfo, '/StereoNetNode/rectify_left_image/camera_info',
            self._rgb_info_callback, 10)

        self._rgb_encoding_logged = False
        self._depth_encoding_logged = False
        self._last_camera_info = None  # 缓存 camera_info, 随每帧 RGB 重发

    def _rgb_callback(self, msg: Image):
        """修正时间戳 + 发布 raw + JPEG 压缩"""
        now = self.get_clock().now().to_msg()

        if not self._rgb_encoding_logged:
            self.get_logger().info(
                f'RGB 输入: {msg.encoding}, {msg.width}x{msg.height}, step={msg.step}')
            self._rgb_encoding_logged = True

        # --- 发布 raw ---
        if msg.encoding in ('bgr8', 'rgb8', 'mono8'):
            msg.header.stamp = now
            msg.header.frame_id = 'camera_optical_frame'
            self._pub_rgb.publish(msg)
            raw_data = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                msg.height, msg.width, -1)
        else:
            data = np.frombuffer(msg.data, dtype=np.uint16)
            data8 = (data >> 8).astype(np.uint8)
            raw_data = data8.reshape(msg.height, msg.width)

            out = Image()
            out.header.stamp = now
            out.header.frame_id = 'camera_optical_frame'
            out.height = msg.height
            out.width = msg.width
            out.encoding = 'mono8'
            out.is_bigendian = False
            out.step = msg.width
            out.data = data8.tobytes()
            self._pub_rgb.publish(out)

        # --- 随 RGB 帧重发 camera_info (保持时间戳与 RGB 一致) ---
        if self._last_camera_info is not None:
            self._last_camera_info.header.stamp = now
            self._pub_rgb_info.publish(self._last_camera_info)

        # --- 发布 JPEG 压缩 ---
        if HAS_CV2:
            try:
                compressed_msg = CompressedImage()
                compressed_msg.header.stamp = now
                compressed_msg.header.frame_id = 'camera_optical_frame'
                compressed_msg.format = 'jpeg'
                # cv2.imencode 需要 bgr 格式
                if raw_data.ndim == 2:
                    encode_data = cv2.cvtColor(raw_data, cv2.COLOR_GRAY2BGR)
                elif raw_data.shape[2] == 3:
                    encode_data = raw_data  # 假设已是 BGR
                else:
                    encode_data = raw_data
                _, buf = cv2.imencode(
                    '.jpg', encode_data, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality])
                compressed_msg.data = buf.flatten().tolist()
                self._pub_rgb_compressed.publish(compressed_msg)
            except Exception as e:
                self.get_logger().error(f'JPEG 压缩失败: {e}', throttle_duration_sec=5.0)

    def _depth_callback(self, msg: Image):
        """深度图: 修正时间戳 + 发布 raw + PNG 无损压缩"""
        now = self.get_clock().now().to_msg()
        if not self._depth_encoding_logged:
            self.get_logger().info(
                f'深度输入: {msg.encoding}, {msg.width}x{msg.height}, step={msg.step}')
            self._depth_encoding_logged = True
        msg.header.stamp = now
        msg.header.frame_id = 'camera_optical_frame'
        if msg.encoding == 'mono16':
            msg.encoding = '16UC1'

        # 诊断深度值范围
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

        # --- 发布 PNG 压缩深度 (无损) ---
        if HAS_CV2:
            try:
                compressed_msg = CompressedImage()
                compressed_msg.header.stamp = now
                compressed_msg.header.frame_id = 'camera_optical_frame'
                compressed_msg.format = 'png'
                depth_data = np.frombuffer(msg.data, dtype=np.uint16).reshape(
                    msg.height, msg.width)
                _, buf = cv2.imencode(
                    '.png', depth_data, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                compressed_msg.data = buf.flatten().tolist()
                self._pub_depth_compressed.publish(compressed_msg)
            except Exception as e:
                self.get_logger().error(
                    f'PNG 深度压缩失败: {e}', throttle_duration_sec=5.0)

    def _rgb_info_callback(self, msg: CameraInfo):
        """camera_info: 时间戳+frame_id修正, 填充 P 矩阵"""
        now = self.get_clock().now().to_msg()
        msg.header.stamp = now
        msg.header.frame_id = 'camera_optical_frame'

        if not getattr(self, '_info_logged', False):
            self._info_logged = True
            self.get_logger().info(
                f'K=[{msg.k[0]:.2f},0,{msg.k[2]:.2f}, 0,{msg.k[4]:.2f},{msg.k[5]:.2f}, 0,0,1] '
                f'P=[{msg.p[0]:.2f},{msg.p[1]:.2f},{msg.p[2]:.2f},{msg.p[3]:.2f}, '
                f'{msg.p[4]:.2f},{msg.p[5]:.2f},{msg.p[6]:.2f},{msg.p[7]:.2f}, '
                f'{msg.p[8]:.2f},{msg.p[9]:.2f},{msg.p[10]:.2f},{msg.p[11]:.2f}]')

        if msg.k[0] != 0.0 and msg.p[0] == 0.0:
            msg.p[0] = msg.k[0]
            msg.p[2] = msg.k[2]
            msg.p[5] = msg.k[4]
            msg.p[6] = msg.k[5]
            msg.p[10] = 1.0
            self.get_logger().info('P 矩阵已从 K 填充', throttle_duration_sec=5.0)

        # 缓存修正后的 camera_info（随每帧 RGB 重发以保持时间戳同步）
        self._last_camera_info = msg
        self._pub_rgb_info.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(ImageRepublisher())
    rclpy.shutdown()

