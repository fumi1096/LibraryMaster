#!/usr/bin/env python3
"""
verify_odom.py — 里程计标定验证程序

自动执行一组运动（前进、后退、旋转），对比里程计测量值与目标值，
验证 linear_scale / angular_scale 标定效果。

用法:
  ros2 launch mycar_driver driver.launch.py   # 先启动驱动 + 里程计
  ros2 run mycar_driver verify_odom            # 再运行验证

输出:
  运动      | 目标    | 里程计   | 误差    | 状态
  ----------|---------|----------|---------|------
  前进 1m   | 1.000m  | 1.012m   | +1.2%   | ✓
  后退 1m   | 1.000m  | 0.985m   | -1.5%   | ✓
  旋转 360° | 360.0°  | 358.2°   | -0.5%   | ✓
"""
import math
import sys
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


def quat_to_yaw(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def unwrap_delta(prev, curr):
    d = curr - prev
    return math.atan2(math.sin(d), math.cos(d))


class VerifyOdom(Node):
    """里程计验证节点"""

    def __init__(self):
        super().__init__('verify_odom')

        self.declare_parameter('linear_distance', 1.0)
        self.declare_parameter('linear_speed', 0.12)
        self.declare_parameter('angular_degrees', 360.0)
        self.declare_parameter('angular_speed', 0.4)

        self._lin_dist = self.get_parameter('linear_distance').value
        self._lin_speed = self.get_parameter('linear_speed').value
        self._ang_deg = self.get_parameter('angular_degrees').value
        self._ang_speed = self.get_parameter('angular_speed').value

        # 订阅
        self._latest_odom = None
        self._odom_sub = self.create_subscription(
            Odometry, '/odom_raw', self._odom_cb, 10)

        # 发布
        self._cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self._results = []

    def _odom_cb(self, msg):
        self._latest_odom = msg

    # ---- helpers ----

    def _wait_odom(self, timeout=5.0):
        start = self.get_clock().now()
        while self._latest_odom is None:
            rclpy.spin_once(self, timeout_sec=0.1)
            if (self.get_clock().now() - start).nanoseconds * 1e-9 > timeout:
                return False
        return True

    def _get_pose(self):
        if self._latest_odom is None:
            return None
        p = self._latest_odom.pose.pose.position
        q = self._latest_odom.pose.pose.orientation
        return (p.x, p.y, quat_to_yaw(q))

    def _get_fresh_pose(self, spins=5):
        for _ in range(spins):
            rclpy.spin_once(self, timeout_sec=0.02)
        return self._get_pose()

    def _wait_stop(self, timeout=3.0):
        start = self.get_clock().now()
        while True:
            rclpy.spin_once(self, timeout_sec=0.05)
            # 检查里程计速度是否接近零
            if self._latest_odom is not None:
                vx = abs(self._latest_odom.twist.twist.linear.x)
                wz = abs(self._latest_odom.twist.twist.angular.z)
                if vx < 0.005 and wz < 0.01:
                    return
            if (self.get_clock().now() - start).nanoseconds * 1e-9 > timeout:
                return

    def _move_linear(self, speed, target_dist):
        """前进，返回 odom 测量的位移"""
        start = self._get_fresh_pose()
        if start is None:
            return None

        sx, sy = start[0], start[1]

        twist = Twist()
        twist.linear.x = speed
        self._cmd_pub.publish(twist)

        t0 = self.get_clock().now()
        while True:
            rclpy.spin_once(self, timeout_sec=0.03)
            self._cmd_pub.publish(twist)

            cur = self._get_pose()
            if cur is None:
                continue

            dx = cur[0] - sx
            dy = cur[1] - sy
            traveled = math.sqrt(dx * dx + dy * dy)

            if traveled >= target_dist:
                self._cmd_pub.publish(Twist())
                self._wait_stop()
                return traveled

            if (self.get_clock().now() - t0).nanoseconds * 1e-9 > 30.0:
                self._cmd_pub.publish(Twist())
                return traveled

    def _move_angular(self, speed, target_rad):
        """旋转，返回 odom 测量的累计角度"""
        start = self._get_fresh_pose()
        if start is None:
            return None

        prev_yaw = start[2]
        cum_angle = 0.0

        twist = Twist()
        twist.angular.z = speed
        self._cmd_pub.publish(twist)

        t0 = self.get_clock().now()
        while True:
            rclpy.spin_once(self, timeout_sec=0.03)
            self._cmd_pub.publish(twist)

            cur = self._get_pose()
            if cur is None:
                continue

            delta = abs(unwrap_delta(prev_yaw, cur[2]))
            cum_angle += delta
            prev_yaw = cur[2]

            if cum_angle >= target_rad:
                self._cmd_pub.publish(Twist())
                self._wait_stop()
                return cum_angle

            if (self.get_clock().now() - t0).nanoseconds * 1e-9 > 30.0:
                self._cmd_pub.publish(Twist())
                return cum_angle

    # ---- results ----

    def _record(self, name, target, measured, unit):
        if measured is None:
            self._results.append((name, target, float('nan'), float('nan'), '❌ 失败'))
            return

        if target > 0.001:
            err_pct = (measured - target) / target * 100.0
        else:
            err_pct = 0.0

        if abs(err_pct) < 2.0:
            status = '✓ 良好'
        elif abs(err_pct) < 5.0:
            status = '⚠ 一般'
        else:
            status = '✗ 需重标定'

        self._results.append((name, target, measured, err_pct, status))

    def _print_table(self):
        print()
        print('╔══════════════════════════════════════════════════════════════╗')
        print('║              里程计标定验证结果                             ║')
        print('╠══════════════╤══════════╤══════════╤══════════╤════════════╣')
        print('║  运动        │ 目标     │ 里程计   │ 误差     │ 状态       ║')
        print('╠══════════════╪══════════╪══════════╪══════════╪════════════╣')
        for name, target, measured, err, status in self._results:
            if math.isnan(measured):
                print(f'║ {name:<12} │ {"—":>8} │ {"—":>8} │ {"—":>8} │ {status:<10} ║')
            else:
                print(f'║ {name:<12} │ {target:>7.1f}  │ {measured:>7.1f}  │ '
                      f'{err:>+6.1f}%  │ {status:<10} ║')
        print('╚══════════════╧══════════╧══════════╧══════════╧════════════╝')

    # ---- main ----

    def run(self):
        if not self._wait_odom():
            self.get_logger().error('等待 /odom_raw 超时')
            return

        print()
        print('=' * 55)
        print('  里程计标定验证')
        print('=' * 55)
        print(f'  前进距离: {self._lin_dist:.1f} m')
        print(f'  前进速度: {self._lin_speed:.2f} m/s')
        print(f'  旋转角度: {self._ang_deg:.0f}°')
        print(f'  旋转速度: {self._ang_speed:.2f} rad/s')
        print()
        print('  ⚠ 请确保小车有足够空间移动！')
        print('  按回车开始，或 Ctrl+C 退出...')
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print('\n  已取消')
            return

        # --- 前进 ---
        print('\n  ▶ 前进 {:.0f}m ...'.format(self._lin_dist))
        d_fwd = self._move_linear(self._lin_speed, self._lin_dist)
        if d_fwd is not None:
            print(f'  里程计: {d_fwd:.2f} m')
        else:
            print('  ❌ 无里程计数据')
        self._record(f'前进 {self._lin_dist:.0f}m', self._lin_dist, d_fwd, 'm')
        time.sleep(1)

        # --- 后退 ---
        print('\n  ▶ 后退 {:.0f}m ...'.format(self._lin_dist))
        d_bwd = self._move_linear(-self._lin_speed, self._lin_dist)
        if d_bwd is not None:
            print(f'  里程计: {d_bwd:.2f} m')
        else:
            print('  ❌ 无里程计数据')
        self._record(f'后退 {self._lin_dist:.0f}m', self._lin_dist, d_bwd, 'm')
        time.sleep(1)

        # --- 旋转 ---
        print('\n  ▶ 旋转 {:.0f}° ...'.format(self._ang_deg))
        ang_rad_target = math.radians(self._ang_deg)
        a_rot = self._move_angular(self._ang_speed, ang_rad_target)
        if a_rot is not None:
            print(f'  里程计: {math.degrees(a_rot):.1f}°')
        else:
            print('  ❌ 无里程计数据')
        self._record(f'旋转 {self._ang_deg:.0f}°', self._ang_deg,
                     math.degrees(a_rot) if a_rot else None, '°')

        # --- 结果 ---
        self._print_table()

        # 提示
        good = sum(1 for _, _, _, e, _ in self._results
                   if not math.isnan(e) and abs(e) < 2.0)
        total = len(self._results)
        if good == total:
            print('  ✅ 所有项目误差 < 2%，标定效果良好！')
        elif good >= total - 1:
            print('  ⚠ 部分项目误差偏大，可考虑重新标定')
        else:
            print('  ✗ 多项误差超标，建议重新标定')
        print()


def main(args=None):
    rclpy.init(args=args)
    node = VerifyOdom()
    try:
        node.run()
    except KeyboardInterrupt:
        print('\n  已取消')
    finally:
        node._cmd_pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
