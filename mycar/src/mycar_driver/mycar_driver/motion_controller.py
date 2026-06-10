#!/usr/bin/env python3
"""
motion_controller.py — 运动控制模块
订阅 /cmd_vel，转换为 MCU 运动指令。四驱普通轮 = 差速驱动模型。

订阅话题:
  /cmd_vel — geometry_msgs/Twist
"""
from rclpy.node import Node
from geometry_msgs.msg import Twist


class MotionController:
    """运动控制器 — 接收 cmd_vel 并下发到 MCU"""

    def __init__(self, node: Node, bridge, *,
                 linear_x_limit=1.0,
                 angular_limit=3.0,
                 invert_vx=False):
        """
        Args:
            node:             ROS2 Node
            bridge:           SerialBridge 实例
            linear_x_limit:   最大线速度 (m/s)
            angular_limit:    最大角速度 (rad/s)
            invert_vx:        反转 vx 方向 (硬件接线方向与 ROS 标准不一致时启用)
        """
        self._node = node
        self._bridge = bridge
        self._linear_x_limit = linear_x_limit
        self._angular_limit = angular_limit
        self._invert_vx = invert_vx

        # 订阅 cmd_vel（队列深度 1，只取最新指令）
        self._sub = node.create_subscription(
            Twist, '/cmd_vel', self._cmd_vel_callback, 1)

        node.get_logger().info(
            f'MotionController 初始化: '
            f'linear_limit={linear_x_limit}, angular_limit={angular_limit}, '
            f'invert_vx={invert_vx}')

    def _cmd_vel_callback(self, msg: Twist):
        """
        处理运动指令。

        差速模型:
          - vx (linear.x):  前进/后退速度
          - vy (linear.y):  忽略（普通轮不支持横向移动）
          - angular.z:      旋转角速度
        """
        vx = -msg.linear.x if self._invert_vx else msg.linear.x
        vy = 0.0  # 四驱普通轮无横向
        angular = msg.angular.z

        # 限幅
        if abs(vx) > self._linear_x_limit:
            vx = self._linear_x_limit if vx > 0 else -self._linear_x_limit
        if abs(angular) > self._angular_limit:
            angular = self._angular_limit if angular > 0 else -self._angular_limit

        self._bridge.set_motion(vx, vy, angular)

    def stop(self):
        """紧急停止"""
        self._bridge.stop()
