#!/usr/bin/env python3
"""
calibrate_odom.py — 交互式里程计标定工具

通过闭环 PID 运动 + 人工测量 + 多次试验取平均，标定里程计 linear_scale 和 angular_scale。

用法:
  ros2 launch mycar_driver calibrate.launch.py   # 一键启动

流程:
  1. 直行标定（N 次取平均）：小车前进 ~1m，用户卷尺实测后输入距离
  2. 旋转标定（N 次取平均）：小车原地旋转 ~360°，用户测量实际转角后输入
  3. 自动更新 driver.launch.py 中的 linear_scale / angular_scale

标定公式:
  new_scale = old_scale × (实测值 / 里程计值)
  其中 old_scale 从 driver.launch.py 自动读取
"""
import math
import os
import re
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


# ================================================================
# 工具函数
# ================================================================

def quat_to_yaw(q):
    """四元数 → yaw (rad), 范围 (-π, π]"""
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def unwrap_delta(prev, curr):
    """计算最小角度差 (rad)，自动处理 ±π 跨越"""
    d = curr - prev
    return math.atan2(math.sin(d), math.cos(d))


def ask_positive(prompt):
    """交互式输入正数"""
    while True:
        raw = input(prompt).strip()
        try:
            val = float(raw)
            if val > 0:
                return val
            print('  ⚠ 请输入正数')
        except ValueError:
            print('  ⚠ 请输入数字')


def press_enter(prompt='按回车继续...'):
    """等待回车，允许输入 q 退出"""
    raw = input(prompt).strip().lower()
    if raw == 'q':
        print('\n  用户取消，退出标定。')
        raise SystemExit(0)


# ================================================================
# 标定节点
# ================================================================

class CalibrateOdom(Node):
    """里程计标定节点

    订阅 /odom_raw 获取里程计位姿，发布 /cmd_vel 驱动小车闭环运动。
    """

    def __init__(self):
        super().__init__('calibrate_odom')

        # --- ROS 参数 ---
        self.declare_parameter('linear_distance', 1.0)
        self.declare_parameter('linear_speed', 0.12)
        self.declare_parameter('angular_degrees', 360.0)
        self.declare_parameter('angular_speed', 0.4)
        self.declare_parameter('trials', 3)
        self.declare_parameter('workspace_dir', '')

        self._lin_target = self.get_parameter('linear_distance').value
        self._lin_speed = self.get_parameter('linear_speed').value
        self._ang_target_deg = self.get_parameter('angular_degrees').value
        self._ang_speed = self.get_parameter('angular_speed').value
        self._trials = self.get_parameter('trials').value
        self._workspace_dir = self.get_parameter('workspace_dir').value

        # 从 driver.launch.py 读取当前生效的 scale（用于正确计算新 scale）
        self._launch_path = self._get_launch_path()
        self._old_linear, self._old_angular = self._read_current_scales(
            self._launch_path)

        # --- 订阅 ---
        self._latest_odom = None
        self._odom_sub = self.create_subscription(
            Odometry, '/odom_raw', self._odom_cb, 10)

        self._latest_vel = None
        self._vel_sub = self.create_subscription(
            Twist, '/vel_raw', self._vel_cb, 10)

        # --- 发布 ---
        self._cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.get_logger().info(
            f'标定节点已启动 | '
            f'当前 linear_scale={self._old_linear:.4f}, '
            f'angular_scale={self._old_angular:.4f}')

    # ---- 回调 ----

    def _odom_cb(self, msg):
        self._latest_odom = msg

    def _vel_cb(self, msg):
        self._latest_vel = msg

    # ================================================================
    #  读取 / 写入 driver.launch.py
    # ================================================================

    def _get_launch_path(self):
        """定位 driver.launch.py 路径

        优先使用 workspace_dir 参数指向的源目录，
        确保写入后 colcon build 能保留标定结果。
        """
        # 1) workspace 源目录（由 calibrate_odom.sh 传入）
        if self._workspace_dir:
            path = os.path.join(
                self._workspace_dir,
                'src', 'mycar_driver', 'launch', 'driver.launch.py')
            if os.path.exists(path):
                return path

        # 2) ament share 目录（install 副本）
        try:
            from ament_index_python.packages import get_package_share_directory
            path = os.path.join(
                get_package_share_directory('mycar_driver'),
                'launch', 'driver.launch.py')
            if os.path.exists(path):
                return path
        except Exception:
            pass

        raise FileNotFoundError(
            '找不到 driver.launch.py。请通过 workspace_dir 参数指定工作空间路径。')

    @classmethod
    def _read_current_scales(cls, launch_path):
        """从 driver.launch.py 提取当前 linear_scale / angular_scale"""
        linear, angular = 1.0, 1.0
        try:
            with open(launch_path, 'r') as f:
                content = f.read()
            m = re.search(r"'linear_scale':\s*([\d.]+)", content)
            if m:
                linear = float(m.group(1))
            m = re.search(r"'angular_scale':\s*([\d.]+)", content)
            if m:
                angular = float(m.group(1))
        except Exception:
            pass
        return linear, angular

    @staticmethod
    def _write_scales(launch_path, linear_scale, angular_scale):
        """将新 scale 写入 driver.launch.py（源目录）"""
        with open(launch_path, 'r') as f:
            content = f.read()

        content = re.sub(
            r"'linear_scale':\s*[\d.]+",
            f"'linear_scale': {linear_scale:.4f}",
            content)
        content = re.sub(
            r"'angular_scale':\s*[\d.]+",
            f"'angular_scale': {angular_scale:.4f}",
            content)

        with open(launch_path, 'w') as f:
            f.write(content)
        return True

    # ================================================================
    #  底层控制
    # ================================================================

    def _wait_odom(self, timeout=5.0):
        """等待 /odom_raw 首条消息"""
        start = self.get_clock().now()
        while self._latest_odom is None:
            rclpy.spin_once(self, timeout_sec=0.1)
            if (self.get_clock().now() - start).nanoseconds * 1e-9 > timeout:
                self.get_logger().error('等待 /odom_raw 超时！请检查 odom_node 是否启动')
                return False
        return True

    def _get_pose(self):
        """提取当前 (x, y, yaw)"""
        if self._latest_odom is None:
            return None
        p = self._latest_odom.pose.pose.position
        q = self._latest_odom.pose.pose.orientation
        return (p.x, p.y, quat_to_yaw(q))

    def _get_fresh_pose(self, spins=5):
        """spin 几次获取最新里程计位姿，避免读到陈旧数据"""
        for _ in range(spins):
            rclpy.spin_once(self, timeout_sec=0.02)
        return self._get_pose()

    def _get_vel_str(self):
        """获取当前速度的字符串描述（用于诊断）"""
        if self._latest_vel is None:
            return 'vx=?'
        return f'vx={self._latest_vel.linear.x:.3f}, wz={self._latest_vel.angular.z:.3f}'

    def _wait_stop(self, timeout=5.0):
        """等待小车完全停下 (|vx| < 0.005 m/s 且 |wz| < 0.01 rad/s)"""
        start = self.get_clock().now()
        while True:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self._latest_vel is not None:
                vx = abs(self._latest_vel.linear.x)
                wz = abs(self._latest_vel.angular.z)
                if vx < 0.005 and wz < 0.01:
                    return True
            if (self.get_clock().now() - start).nanoseconds * 1e-9 > timeout:
                self.get_logger().warn('停车等待超时，继续...')
                return True

    def _move_linear(self, speed, target_dist, start_pose, max_duration=30.0):
        """前进直到里程计 >= target_dist，返回 (traveled_m, timed_out, odom_lost)"""
        t0 = self.get_clock().now()
        sx, sy = start_pose[0], start_pose[1]
        last_print = 0.0
        last_odom_time = t0
        odom_warned = False

        self.get_logger().info(
            f'  前进: {speed:.2f} m/s, 目标 {target_dist:.1f} m')
        print('  行进中', end='', flush=True)

        twist = Twist()
        twist.linear.x = speed
        self._cmd_pub.publish(twist)

        while True:
            rclpy.spin_once(self, timeout_sec=0.03)
            self._cmd_pub.publish(twist)  # 持续发送，防 MCU 超时

            cur = self._get_pose()
            if cur is None:
                # odom 丢失检测：超过 3 秒无数据则报错退出
                if not odom_warned:
                    self.get_logger().warn('等待里程计数据...')
                    odom_warned = True
                if (self.get_clock().now() - last_odom_time).nanoseconds * 1e-9 > 3.0:
                    self.get_logger().error('里程计数据丢失超过 3 秒！')
                    print(' ❌odom丢失')
                    self._cmd_pub.publish(Twist())
                    return 0.0, False, True
                continue
            last_odom_time = self.get_clock().now()
            odom_warned = False

            dx = cur[0] - sx
            dy = cur[1] - sy
            traveled = math.sqrt(dx * dx + dy * dy)

            if traveled - last_print >= 0.1:
                print('.', end='', flush=True)
                last_print = traveled

            if traveled >= target_dist:
                print(' ✓')
                self._cmd_pub.publish(Twist())
                self._wait_stop()
                return traveled, False, False

            elapsed = (self.get_clock().now() - t0).nanoseconds * 1e-9
            if elapsed > max_duration:
                self.get_logger().warn(
                    f'  超时: {traveled:.3f} m / {target_dist:.1f} m')
                print(' ⏱')
                self._cmd_pub.publish(Twist())
                self._wait_stop()
                return traveled, True, False

    def _move_angular(self, speed, target_rad, start_yaw, max_duration=30.0):
        """旋转直到累计角度 >= target_rad，返回 (cum_angle_rad, timed_out, odom_lost)"""
        t0 = self.get_clock().now()
        prev_yaw = start_yaw
        cum_angle = 0.0
        last_print = 0.0
        last_odom_time = t0
        odom_warned = False
        no_move_start = None

        self.get_logger().info(
            f'  旋转: {speed:.2f} rad/s, 目标 {math.degrees(target_rad):.0f}°, '
            f'起点 yaw={math.degrees(start_yaw):.1f}°, {self._get_vel_str()}')
        print('  旋转中', end='', flush=True)

        twist = Twist()
        twist.angular.z = speed
        self._cmd_pub.publish(twist)

        while True:
            rclpy.spin_once(self, timeout_sec=0.03)
            self._cmd_pub.publish(twist)

            cur = self._get_pose()
            if cur is None:
                if not odom_warned:
                    self.get_logger().warn('等待里程计数据...')
                    odom_warned = True
                if (self.get_clock().now() - last_odom_time).nanoseconds * 1e-9 > 3.0:
                    self.get_logger().error('里程计数据丢失超过 3 秒！')
                    print(' ❌odom丢失')
                    self._cmd_pub.publish(Twist())
                    return 0.0, False, True
                continue
            last_odom_time = self.get_clock().now()
            odom_warned = False

            delta = abs(unwrap_delta(prev_yaw, cur[2]))
            cum_angle += delta
            prev_yaw = cur[2]

            # 物理不动检测：超过 2 秒角度无变化
            if cum_angle < 0.01:
                if no_move_start is None:
                    no_move_start = self.get_clock().now()
                elif (self.get_clock().now() - no_move_start).nanoseconds * 1e-9 > 2.0:
                    self.get_logger().error(
                        '小车可能没有旋转！检查: 电池/电机线/驱动板上电 '
                        f'{self._get_vel_str()}')
                    print(' ⚠️不动')
                    self._cmd_pub.publish(Twist())
                    return cum_angle, True, False
            else:
                no_move_start = None

            if cum_angle - last_print >= math.radians(45):
                print('.', end='', flush=True)
                last_print = cum_angle

            if cum_angle >= target_rad:
                print(' ✓')
                self._cmd_pub.publish(Twist())
                self._wait_stop()
                return cum_angle, False, False

            elapsed = (self.get_clock().now() - t0).nanoseconds * 1e-9
            if elapsed > max_duration:
                self.get_logger().warn(
                    f'  超时: {math.degrees(cum_angle):.0f}° / '
                    f'{math.degrees(target_rad):.0f}°')
                print(' ⏱')
                self._cmd_pub.publish(Twist())
                self._wait_stop()
                return cum_angle, True, False

    # ================================================================
    #  直行标定
    # ================================================================

    def calibrate_linear(self):
        """直行标定：前进固定距离，比较里程计值与实测值"""
        print()
        print('=' * 55)
        print(f'  [步骤 1] 直行标定 — {self._trials} 次取平均')
        print('=' * 55)
        print(f'  准备: 在地上标记起点，备好卷尺')
        print(f'  速度 {self._lin_speed:.2f} m/s, 目标前进 {self._lin_target:.1f} m')
        print(f'  当前 linear_scale = {self._old_linear:.4f}')
        print('  (输入 q 可随时退出)')

        scales = []
        for i in range(1, self._trials + 1):
            print(f'\n  --- 第 {i}/{self._trials} 次 ---')
            press_enter('  把车放回起点，按回车开始 (q=退出)...')

            start = self._get_fresh_pose()
            if start is None:
                print('  ❌ 无法获取里程计，跳过')
                continue

            print(f'  起点=({start[0]:.2f}, {start[1]:.2f}), {self._get_vel_str()}')

            d_odom, timed_out, odom_lost = self._move_linear(
                self._lin_speed, self._lin_target, start)

            if odom_lost:
                print('  ❌ 里程计数据丢失，跳过本次')
                continue
            if timed_out:
                print('  ⚠ 未完成！检查小车是否正常移动')
                ans = input('  仍然记录? (y=记录/其他=跳过): ').strip().lower()
                if ans != 'y':
                    continue

            print(f'  里程计测量位移: {d_odom:.3f} m')
            d_real = ask_positive('  请输入卷尺实测距离 (米): ')

            if d_odom > 0.001:
                scale = self._old_linear * d_real / d_odom
            else:
                scale = self._old_linear

            print(f'  本次 scale = {self._old_linear:.4f} × {d_real:.3f} / {d_odom:.3f} = {scale:.4f}')
            scales.append(scale)

        if not scales:
            print('  ❌ 没有有效数据')
            return None

        avg = sum(scales) / len(scales)
        if len(scales) > 1:
            std = (sum((s - avg) ** 2 for s in scales) / len(scales)) ** 0.5
            print(f'\n  → 平均 linear_scale = {avg:.4f} ± {std:.4f} ({len(scales)} 次)')
        else:
            print(f'\n  → linear_scale = {avg:.4f}')
        return avg

    # ================================================================
    #  旋转标定
    # ================================================================

    def calibrate_angular(self):
        """旋转标定：旋转固定角度，比较里程计值与实测值"""
        print()
        print('=' * 55)
        print(f'  [步骤 2] 旋转标定 — {self._trials} 次取平均')
        print('=' * 55)
        print(f'  准备: 在地面标记车头方向')
        print(f'  速度 {self._ang_speed:.2f} rad/s, 目标旋转 {self._ang_target_deg:.0f}°')
        print(f'  当前 angular_scale = {self._old_angular:.4f}')
        print('  (输入 q 可随时退出)')

        target_rad = math.radians(self._ang_target_deg)

        scales = []
        for i in range(1, self._trials + 1):
            print(f'\n  --- 第 {i}/{self._trials} 次 ---')
            press_enter('  标记好车头方向，按回车开始 (q=退出)...')

            start = self._get_fresh_pose()
            if start is None:
                print('  ❌ 无法获取里程计，跳过')
                continue

            print(f'  起点 yaw={math.degrees(start[2]):.1f}°, {self._get_vel_str()}')

            cum_angle, timed_out, odom_lost = self._move_angular(
                self._ang_speed, target_rad, start[2])

            if odom_lost:
                print('  ❌ 里程计数据丢失，跳过本次')
                continue
            if timed_out:
                print('  ⚠ 未完成！检查小车是否正常旋转')
                ans = input('  仍然记录? (y=记录/其他=跳过): ').strip().lower()
                if ans != 'y':
                    continue

            a_odom_deg = math.degrees(cum_angle)
            print(f'  里程计测量转角: {a_odom_deg:.1f}°')
            a_real = ask_positive('  请输入实测转角 (度): ')

            if a_odom_deg > 0.1:
                scale = self._old_angular * a_real / a_odom_deg
            else:
                scale = self._old_angular

            print(f'  本次 scale = {self._old_angular:.4f} × {a_real:.1f} / {a_odom_deg:.1f} = {scale:.4f}')
            scales.append(scale)

        if not scales:
            print('  ❌ 没有有效数据')
            return None

        avg = sum(scales) / len(scales)
        if len(scales) > 1:
            std = (sum((s - avg) ** 2 for s in scales) / len(scales)) ** 0.5
            print(f'\n  → 平均 angular_scale = {avg:.4f} ± {std:.4f} ({len(scales)} 次)')
        else:
            print(f'\n  → angular_scale = {avg:.4f}')
        return avg


# ================================================================
#  main
# ================================================================

def main(args=None):
    rclpy.init(args=args)
    node = CalibrateOdom()

    # 等待里程计就绪
    if not node._wait_odom():
        node.destroy_node()
        rclpy.shutdown()
        return

    print()
    print('╔══════════════════════════════════════════════════════╗')
    print('║          mycar 里程计标定工具                        ║')
    print('╠══════════════════════════════════════════════════════╣')
    print('║  先标定直行 → 再标定旋转 → 自动写入 driver.launch.py  ║')
    print(f'║  每项 {node._trials} 次取平均                                      ║')
    print(f'║  当前 linear={node._old_linear:.4f}  angular={node._old_angular:.4f}                     ║')
    print('╚══════════════════════════════════════════════════════╝')

    try:
        # 1. 直行
        lin = node.calibrate_linear()
        if lin is None:
            print('\n❌ 直行标定失败，退出。')
            return

        # 2. 旋转
        ang = node.calibrate_angular()
        if ang is None:
            print('\n❌ 旋转标定失败，退出。')
            return

        # 3. 结果
        print()
        print('=' * 55)
        print('  [标定结果]')
        print('=' * 55)
        print(f'  linear_scale:  {lin:.4f}')
        print(f'  angular_scale: {ang:.4f}')

        if 0.5 <= lin <= 2.0 and 0.5 <= ang <= 2.0:
            print('  ✅ 系数在合理范围内')
        else:
            print('  ⚠ 系数偏离 1.0 较多，请确认测量准确后重试')

        # 4. 写入
        if node._write_scales(node._launch_path, lin, ang):
            print(f'\n  ✅ 已写入: {node._launch_path}')
            print('  请重新编译: colcon build --packages-select mycar_driver')
        else:
            print('\n  ⚠ 写入失败，请手动更新 driver.launch.py')

    except SystemExit:
        print('\n  标定已取消。')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
