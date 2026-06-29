#!/usr/bin/env python3
"""
odom_node.py — 里程计节点（差速驱动模型）

订阅 /vel_raw (Twist)，通过一阶欧拉积分计算里程计，发布:
  /odom_raw — nav_msgs/Odometry
  odom → base_footprint TF（可选）

运动学模型（差速驱动，一阶欧拉积分）:
  delta_heading = ω * dt
  delta_x = v * cos(heading) * dt
  delta_y = v * sin(heading) * dt
"""
import math

import rclpy
from rclpy.node import Node
from rclpy.clock import Clock
from geometry_msgs.msg import Twist, TransformStamped, Quaternion
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster


class OdomNode(Node):
    """差速驱动里程计节点"""

    def __init__(self):
        super().__init__('odom_node')

        # === 参数 ===
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_footprint')
        self.declare_parameter('pub_odom_tf', True)
        self.declare_parameter('linear_scale', 1.0)
        self.declare_parameter('angular_scale', 1.0)

        self._odom_frame = self.get_parameter('odom_frame').value
        self._base_frame = self.get_parameter('base_frame').value
        self._pub_odom_tf = self.get_parameter('pub_odom_tf').value
        self._linear_scale = self.get_parameter('linear_scale').value
        self._angular_scale = self.get_parameter('angular_scale').value

        # === 状态 ===
        self._x = 0.0
        self._y = 0.0
        self._heading = 0.0
        self._last_time = self.get_clock().now()

        # === TF 广播器 ===
        self._tf_broadcaster = TransformBroadcaster(self)

        # === 订阅 /vel_raw ===
        self._vel_sub = self.create_subscription(
            Twist, '/vel_raw', self._vel_callback, 10)

        # === 发布 /odom_raw ===
        self._odom_pub = self.create_publisher(Odometry, '/odom_raw', 10)

        self.get_logger().info(
            f'OdomNode 初始化: odom={self._odom_frame}, '
            f'base={self._base_frame}, pub_tf={self._pub_odom_tf}')

    def _vel_callback(self, msg: Twist):
        """速度回调：一阶欧拉积分（无 PID 拟合）"""
        now = self.get_clock().now()
        dt = (now - self._last_time).nanoseconds * 1e-9
        self._last_time = now

        if dt <= 0.0 or dt > 0.5:
            return

        vx = msg.linear.x * self._linear_scale
        angular = msg.angular.z * self._angular_scale

        # 一阶欧拉积分
        delta_heading = angular * dt
        delta_x = vx * math.cos(self._heading) * dt
        delta_y = vx * math.sin(self._heading) * dt

        self._x += delta_x
        self._y += delta_y
        self._heading += delta_heading

        # 偏航角 → 四元数
        cy = math.cos(self._heading * 0.5)
        sy = math.sin(self._heading * 0.5)
        q = Quaternion()
        q.z = sy
        q.w = cy

        # === 发布里程计消息 ===
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = self._odom_frame
        odom.child_frame_id = self._base_frame

        odom.pose.pose.position.x = self._x
        odom.pose.pose.position.y = self._y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation = q
        # 协方差：位姿 (x, y, yaw)
        odom.pose.covariance[0] = 0.001
        odom.pose.covariance[7] = 0.001
        odom.pose.covariance[35] = 0.001

        # 速度
        odom.twist.twist.linear.x = vx
        odom.twist.twist.linear.y = 0.0
        odom.twist.twist.angular.z = angular
        odom.twist.covariance[0] = 0.0001
        odom.twist.covariance[7] = 0.0001
        odom.twist.covariance[35] = 0.0001

        self._odom_pub.publish(odom)

        # === 发布 TF: odom → base_footprint ===
        if self._pub_odom_tf:
            t = TransformStamped()
            t.header.stamp = now.to_msg()
            t.header.frame_id = self._odom_frame
            t.child_frame_id = self._base_frame
            t.transform.translation.x = self._x
            t.transform.translation.y = self._y
            t.transform.translation.z = 0.0
            t.transform.rotation = q
            self._tf_broadcaster.sendTransform(t)


def main(args=None):
    rclpy.init(args=args)
    node = OdomNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
