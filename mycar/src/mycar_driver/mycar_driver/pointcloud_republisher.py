#!/usr/bin/env python3
"""
pointcloud_republisher.py — 重新发布点云，修正时间戳 + 旋转

hobot_stereonet 的点云时间戳是相机内部时间（秒级启动时间），与 ROS 时间（epoch）
相差巨大，导致 pointcloud_to_laserscan / slam_toolbox 无法做 TF 变换。

相机倒置安装 → 点云绕 X 轴旋转 180° (x→x, y→-y, z→-z)。

本节点:
  1. 用当前 ROS 时间替换点云的 header.stamp
  2. 绕 X 轴旋转 180°
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
import numpy as np


class PointCloudRepublisher(Node):
    def __init__(self):
        super().__init__('pointcloud_republisher')
        self._pub = self.create_publisher(PointCloud2, '~/pointcloud_fixed', 10)
        self._sub = self.create_subscription(
            PointCloud2,
            '/StereoNetNode/stereonet_pointcloud2',
            self._callback,
            10)
        self._transform_logged = False
        self.get_logger().info('点云时间戳修正 + X轴旋转180° 已启动')

    def _rotate_points_x180(self, cloud: PointCloud2):
        """绕X轴旋转180°: x→x, y→-y, z→-z (向量化)"""
        # 解析为 float32 视图，每个点按 point_step 字节排列
        raw = np.frombuffer(cloud.data, dtype=np.float32)
        # point_step // 4 = 每个点有多少个 float32
        stride = cloud.point_step // 4
        num_points = cloud.width * cloud.height

        if not self._transform_logged:
            self.get_logger().info(
                f'点云: {num_points} 点, point_step={cloud.point_step}, '
                f'stride={stride}, '
                f'fields={[(f.name, f.offset) for f in cloud.fields]}')
            self._transform_logged = True

        # 重塑为 (num_points, stride) 便于批量操作
        pc = raw.reshape(num_points, stride)
        # x = offset 0 → 第0列, y = offset 4 → 第1列
        # x (第0列) 不变
        pc[:, 1] = -pc[:, 1]  # y → -y
        pc[:, 2] = -pc[:, 2]  # z → -z

        cloud.data = pc.tobytes()
        return cloud

    def _callback(self, msg: PointCloud2):
        msg = self._rotate_points_x180(msg)
        msg.header.stamp = self.get_clock().now().to_msg()
        self._pub.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(PointCloudRepublisher())
    rclpy.shutdown()
