#!/usr/bin/env python3
"""
scan_publisher.py — 合并点云修正 + LaserScan 投影（单节点，零中间话题）

将 pointcloud_republisher + pointcloud_to_laserscan 合并为一个节点：
  1. 订阅原始点云 /StereoNetNode/stereonet_pointcloud2
  2. 绕 X 轴旋转 180°（修正倒置安装）
  3. 时间戳 realtime → epoch
  4. 高度切片投影 → LaserScan
  5. 发布 /scan

消除中间大点云话题的 DDS 传输，大幅降低延迟。
"""
import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from sensor_msgs.msg import PointCloud2, LaserScan
import numpy as np
import math


class ScanPublisher(Node):
    def __init__(self):
        super().__init__('scan_publisher')

        # === 参数 ===
        self.declare_parameter('target_frame', 'base_footprint')
        self.declare_parameter('min_height', 0.05)
        self.declare_parameter('max_height', 0.8)
        self.declare_parameter('angle_min', -1.57)
        self.declare_parameter('angle_max', 1.57)
        self.declare_parameter('angle_increment', 0.0087)
        self.declare_parameter('range_min', 0.1)
        self.declare_parameter('range_max', 5.0)
        self.declare_parameter('scan_time', 0.1)

        # === 发布 /scan ===
        self._pub = self.create_publisher(LaserScan, '/scan', 10)
        self._last_pub_time = self.get_clock().now()

        # === 订阅原始点云 ===
        self._sub = self.create_subscription(
            PointCloud2,
            '/StereoNetNode/stereonet_pointcloud2',
            self._callback,
            10)

        self._init_logged = False
        self.get_logger().info('scan_publisher 已启动 (合并: 旋转+时间戳+投影)')

    def _callback(self, cloud: PointCloud2):
        # --- 节流: 按 scan_time 限速 ---
        now = self.get_clock().now()
        scan_period = Duration(seconds=self.get_parameter('scan_time').value)
        if now - self._last_pub_time < scan_period:
            return
        self._last_pub_time = now

        # --- 解析点云为 numpy ---
        raw = np.frombuffer(cloud.data, dtype=np.float32)
        stride = cloud.point_step // 4
        num_points = cloud.width * cloud.height
        points = raw.reshape(num_points, stride)
        # x=col0, y=col1, z=col2

        if not self._init_logged:
            self.get_logger().info(
                f'点云: {num_points} 点, point_step={cloud.point_step}, stride={stride}')
            self._init_logged = True

        # --- 绕 X 轴旋转 180°: y→-y, z→-z ---
        points[:, 1] = -points[:, 1]
        points[:, 2] = -points[:, 2]

        # --- 高度过滤 ---
        min_h = self.get_parameter('min_height').value
        max_h = self.get_parameter('max_height').value
        mask = (points[:, 2] >= min_h) & (points[:, 2] <= max_h)
        filtered = points[mask]

        if len(filtered) == 0:
            return

        # --- 计算角度和距离 ---
        x = filtered[:, 0]
        y = filtered[:, 1]
        angles = np.arctan2(y, x)
        distances = np.sqrt(x * x + y * y)

        # --- 距离过滤 ---
        r_min = self.get_parameter('range_min').value
        r_max = self.get_parameter('range_max').value
        range_mask = (distances >= r_min) & (distances <= r_max)
        angles = angles[range_mask]
        distances = distances[range_mask]

        # --- 角度分桶取最近点 ---
        a_min = self.get_parameter('angle_min').value
        a_max = self.get_parameter('angle_max').value
        a_inc = self.get_parameter('angle_increment').value
        num_bins = int((a_max - a_min) / a_inc) + 1

        ranges = np.full(num_bins, np.inf, dtype=np.float32)
        bin_indices = ((angles - a_min) / a_inc).astype(np.int32)
        valid = (bin_indices >= 0) & (bin_indices < num_bins)

        # 对每个有效 bin，取最小距离
        for i in np.where(valid)[0]:
            b = bin_indices[i]
            if distances[i] < ranges[b]:
                ranges[b] = distances[i]

        # --- 构建 LaserScan 消息 ---
        scan = LaserScan()
        scan.header.stamp = now.to_msg()
        scan.header.frame_id = self.get_parameter('target_frame').value
        scan.angle_min = a_min
        scan.angle_max = a_max
        scan.angle_increment = a_inc
        scan.time_increment = 0.0
        scan.scan_time = self.get_parameter('scan_time').value
        scan.range_min = r_min
        scan.range_max = r_max
        scan.ranges = ranges.tolist()
        scan.intensities = []

        self._pub.publish(scan)


def main():
    rclpy.init()
    rclpy.spin(ScanPublisher())
    rclpy.shutdown()
