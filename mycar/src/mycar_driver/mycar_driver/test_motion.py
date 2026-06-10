#!/usr/bin/env python3
"""
小车运动测试脚本 — 发布 /cmd_vel 指令验证驱动和运动控制是否正常。

测试序列（每个动作持续约 2 秒）：
  1. 前进 0.3 m/s
  2. 后退 0.3 m/s
  3. 左旋 1.0 rad/s
  4. 右旋 1.0 rad/s
  5. 前进 + 左旋（弧线）
  6. 停止

用法:
  ros2 run mycar_driver test_motion          # 默认速度
  ros2 run mycar_driver test_motion --ros-args -p linear_speed:=0.5 -p angular_speed:=1.5
"""
import sys
import time
import signal

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class MotionTester(Node):
    """运动测试节点"""

    def __init__(self):
        super().__init__('motion_tester')

        # 声明参数
        self.declare_parameter('linear_speed', 0.3)
        self.declare_parameter('angular_speed', 1.0)
        self.declare_parameter('duration', 2.0)

        self._linear = self.get_parameter('linear_speed').value
        self._angular = self.get_parameter('angular_speed').value
        self._duration = self.get_parameter('duration').value

        # 发布者
        self._pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.get_logger().info('=' * 50)
        self.get_logger().info('  小车运动测试 — 请确保小车悬空或放在地上!')
        self.get_logger().info(f'  线速度: {self._linear:.1f} m/s')
        self.get_logger().info(f'  角速度: {self._angular:.1f} rad/s')
        self.get_logger().info(f'  每步时长: {self._duration:.0f}s')
        self.get_logger().info('=' * 50)

        # 定时器：启动后稍等再开始测试（给驱动节点初始化时间）
        self._step = -1
        self._timer = self.create_timer(1.0, self._run_test)

    def _send(self, vx, angular, desc):
        """发送速度指令"""
        msg = Twist()
        msg.linear.x = vx
        msg.angular.z = angular
        self._pub.publish(msg)
        self.get_logger().info(f'  [{self._step}] {desc}: vx={vx:.1f}, w={angular:.1f}')

    def _stop(self):
        self._send(0.0, 0.0, '停止')
        self.get_logger().info('✅ 测试完成，小车已停止')
        self._timer.cancel()

    def _run_test(self):
        """执行测试序列（每步间隔 duration 秒）"""
        speed = self._linear
        turn = self._angular
        dur = self._duration

        self._step += 1

        if self._step == 0:
            # 初始化等待（给驱动节点准备时间）
            self.get_logger().info('🟢 开始运动测试...')
            self._send(0.0, 0.0, '初始化')
            self._timer.cancel()
            self._timer = self.create_timer(dur, self._run_test)

        elif self._step == 1:
            self._send(speed, 0.0, '前进 ↑')
            self._timer.cancel()
            self._timer = self.create_timer(dur, self._run_test)

        elif self._step == 2:
            self._send(-speed, 0.0, '后退 ↓')
            self._timer.cancel()
            self._timer = self.create_timer(dur, self._run_test)

        elif self._step == 3:
            self._send(0.0, turn, '左旋 ↺')
            self._timer.cancel()
            self._timer = self.create_timer(dur, self._run_test)

        elif self._step == 4:
            self._send(0.0, -turn, '右旋 ↻')
            self._timer.cancel()
            self._timer = self.create_timer(dur, self._run_test)

        elif self._step == 5:
            self._send(speed * 0.5, turn * 0.5, '弧线前进 ↶')
            self._timer.cancel()
            self._timer = self.create_timer(dur, self._run_test)

        elif self._step == 6:
            self._send(-speed * 0.5, -turn * 0.5, '弧线后退 ↷')
            self._timer.cancel()
            self._timer = self.create_timer(dur, self._run_test)

        else:
            self._stop()
            # 退出程序
            self.destroy_node()
            rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)

    # 注册 SIGINT 处理：Ctrl+C 时紧急停止
    node = None

    def sigint_handler(sig, frame):
        print('\n⚠️  紧急停止!')
        if node:
            stop_msg = Twist()
            node._pub.publish(stop_msg)
        rclpy.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)

    node = MotionTester()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        stop_msg = Twist()
        try:
            node._pub.publish(stop_msg)
        except Exception:
            pass
        rclpy.shutdown()


if __name__ == '__main__':
    main()
