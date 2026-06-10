#!/usr/bin/env python3
"""
键盘遥控节点 — 按下动、松手停

操作键:
  i     前进      ,     后退
  j     左转      l     右转
  u     前进+左转  o     前进+右转
  m     后退+左转  .     后退+右转
  k/空格 紧急停止

  q/z   加减最大速度 10%
  w/x   加减线速度 10%
  e/c   加减角速度 10%
  Ctrl+C 退出

用法:
  ros2 run mycar_driver keyboard_control
"""
import sys
import time
import select
import termios
import tty

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

MSG = """
建图遥控 — mycar (按下动、松手停)
───────────────────────────
   u    i    o
   j    k    l
   m    ,    .

  k/空格: 停  q/z: 调速
  Ctrl+C: 退出
───────────────────────────
"""

MOVE = {
    'i': (1, 0),   'o': (1, -1),
    'j': (0, 1),   'l': (0, -1),
    'u': (1, 1),   ',': (-1, 0),
    '.': (-1, 1),  'm': (-1, -1),
}
SPEED = {
    'q': (1.1, 1.1), 'z': (0.9, 0.9),
    'w': (1.1, 1.0), 'x': (0.9, 1.0),
    'e': (1.0, 1.1), 'c': (1.0, 0.9),
}

STOP_TIMEOUT = 0.15  # 松手后 150ms 自动停止


class KeyboardControl(Node):
    def __init__(self):
        super().__init__('keyboard_control')
        self._pub = self.create_publisher(Twist, '/cmd_vel', 1)

        self.declare_parameter('linear_speed', 0.2)
        self.declare_parameter('angular_speed', 1.0)
        self._linear = self.get_parameter('linear_speed').value
        self._angular = self.get_parameter('angular_speed').value

        self._save_attrs = termios.tcgetattr(sys.stdin)
        self._last_move_time = 0.0

        # 定时检查：松手超时自动停止
        self._timer = self.create_timer(0.05, self._auto_stop_check)

        self.get_logger().info('键盘遥控已启动 (按下动、松手停)')
        self.get_logger().info(f'速度: linear={self._linear}, angular={self._angular}')

    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        r, _, _ = select.select([sys.stdin], [], [], 0.02)
        key = sys.stdin.read(1) if r else ''
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._save_attrs)
        return key

    def send(self, vx, angular):
        msg = Twist()
        msg.linear.x = vx
        msg.angular.z = angular
        self._pub.publish(msg)

    def stop(self):
        self.send(0.0, 0.0)

    def _auto_stop_check(self):
        """超过 STOP_TIMEOUT 没收到移动指令 → 自动停止"""
        if self._last_move_time > 0 and (time.time() - self._last_move_time) > STOP_TIMEOUT:
            self.stop()
            self._last_move_time = 0.0


def main():
    rclpy.init()
    node = KeyboardControl()
    linear = node._linear
    angular = node._angular

    print(MSG)
    print(f'  速度: linear={linear:.2f}  angular={angular:.2f}')
    print()

    try:
        while True:
            key = node.get_key()

            if key in ('k', ' '):
                node.stop()
                node._last_move_time = 0.0
                print('\r  ⏹ 停止               ', end='')

            elif key in MOVE:
                v_dir, a_dir = MOVE[key]
                vx = v_dir * linear
                az = a_dir * angular
                node.send(vx, az)
                node._last_move_time = time.time()
                print(f'\r  ▶ vx={vx:+.1f} az={az:+.1f}  ', end='')

            elif key in SPEED:
                ls, ags = SPEED[key]
                linear = round(min(max(linear * ls, 0.05), 1.0), 2)
                angular = round(min(max(angular * ags, 0.1), 3.0), 2)
                print(f'\r  🔧 {linear:.2f} / {angular:.2f}   ', end='')

            rclpy.spin_once(node, timeout_sec=0.01)

    except KeyboardInterrupt:
        print('\n\n  退出...')
    finally:
        node.stop()
        print('  已停止')
        rclpy.shutdown()
