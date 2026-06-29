#!/usr/bin/env python3
"""
odom_delay.py — 里程计延迟中继节点

功能: 订阅 /odom_internal，缓冲 delay_ms 后再发布到 /odom
      用于对齐 /scan 和 /odom 的时间差（scan 因 BPU 推理有额外延迟）。

用法:
  ros2 run mycar_driver odom_delay --ros-args -p delay_ms:=300
"""
import collections
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry


class OdomDelay(Node):
    """里程计消息延迟缓冲节点"""

    def __init__(self):
        super().__init__('odom_delay')

        # === 参数 ===
        self.declare_parameter('delay_ms', 300)
        self._delay_ms = self.get_parameter('delay_ms').value
        delay_s = self._delay_ms / 1000.0

        self.declare_parameter('input_topic', '/odom_internal')
        self.declare_parameter('output_topic', '/odom')

        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value

        # === 消息缓冲 (deque: (receipt_time, message)) ===
        self._buffer = collections.deque()
        self._delay_s = delay_s

        # === 订阅 + 发布 ===
        self._sub = self.create_subscription(
            Odometry, input_topic, self._callback, 10)
        self._pub = self.create_publisher(Odometry, output_topic, 10)

        # 定时器: 每 20ms 检查一次过期消息
        self._timer = self.create_timer(0.02, self._flush)

        self.get_logger().info(
            f'OdomDelay: {input_topic} → {output_topic}, '
            f'delay={self._delay_ms}ms')

    def _callback(self, msg: Odometry):
        """收到消息，存入缓冲"""
        now = self.get_clock().now()
        self._buffer.append((now, msg))

    def _flush(self):
        """将已过延迟时间的消息发布"""
        now = self.get_clock().now()
        while self._buffer:
            receipt_time, msg = self._buffer[0]
            if (now - receipt_time).nanoseconds * 1e-9 >= self._delay_s:
                self._buffer.popleft()
                # 修正时间戳为当前时间（让下游看到"当前"的位姿）
                msg.header.stamp = now.to_msg()
                self._pub.publish(msg)
            else:
                break


def main(args=None):
    rclpy.init(args=args)
    node = OdomDelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
