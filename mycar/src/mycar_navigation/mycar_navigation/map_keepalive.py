#!/usr/bin/env python3
"""
map_keepalive.py — 地图保持活跃发布

问题: map_server 发布 /map 一次后停止，PC 端 RViz 晚订阅收不到。
解决: 订阅 /map (transient_local), 每秒重发一次，确保晚订阅者也能收到。

用法:
  ros2 run mycar_navigation map_keepalive
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from nav_msgs.msg import OccupancyGrid


class MapKeepalive(Node):
    def __init__(self):
        super().__init__('map_keepalive')

        # 用 transient_local 订阅, 确保能拿到 map_server 发布的消息
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )

        self._map = None
        self._sub = self.create_subscription(
            OccupancyGrid, '/map', self._map_cb, qos)

        # 每秒重发到 /map，让 PC 端晚订阅者也能收到
        self._pub = self.create_publisher(OccupancyGrid, '/map', 10)
        self._timer = self.create_timer(1.0, self._publish)

        self.get_logger().info('map_keepalive 已启动，等待 /map ...')

    def _map_cb(self, msg: OccupancyGrid):
        if self._map is None:
            self.get_logger().info(
                f'收到地图: {msg.info.width}x{msg.info.height}, '
                f'分辨率={msg.info.resolution}m')
        self._map = msg

    def _publish(self):
        if self._map is not None:
            self._map.header.stamp = self.get_clock().now().to_msg()
            self._pub.publish(self._map)


def main():
    rclpy.init()
    node = MapKeepalive()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
