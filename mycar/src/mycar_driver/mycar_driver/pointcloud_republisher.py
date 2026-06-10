#!/usr/bin/env python3
"""
pointcloud_republisher.py — 重新发布点云，修正时间戳

hobot_stereonet 的点云时间戳是相机内部时间（秒级启动时间），与 ROS 时间（epoch）
相差巨大，导致 pointcloud_to_laserscan / slam_toolbox 无法做 TF 变换。

本节点用当前 ROS 时间替换点云的 header.stamp。
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2


class PointCloudRepublisher(Node):
    def __init__(self):
        super().__init__('pointcloud_republisher')
        self._pub = self.create_publisher(PointCloud2, '~/pointcloud_fixed', 10)
        self._sub = self.create_subscription(
            PointCloud2,
            '/StereoNetNode/stereonet_pointcloud2',
            self._callback,
            10)
        self.get_logger().info('点云时间戳修正已启动')

    def _callback(self, msg: PointCloud2):
        msg.header.stamp = self.get_clock().now().to_msg()
        self._pub.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(PointCloudRepublisher())
    rclpy.shutdown()
