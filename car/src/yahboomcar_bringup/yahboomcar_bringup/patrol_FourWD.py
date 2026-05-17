#!/usr/bin/env python
# encoding: utf-8

"""
mycar00 (FourWD) 自主巡逻程序

功能：让小车按照预设路径自主行驶
- 方形巡逻：走正方形路径
- 8字巡逻：走8字形路径
- 直线往返：直线来回行驶

使用方法：
  ros2 run yahboomcar_bringup patrol_FourWD

注意：需要先启动 FourWD_driver 节点
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
from math import pi

# 精确角度计算
# 90° = π/2 rad ≈ 1.57 rad
# 旋转时间 = 目标角度(rad) / 角速度(rad/s)


class FourWDPatrol(Node):
    def __init__(self):
        super().__init__('fourwd_patrol_node')

        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)

        # 巡逻参数
        self.linear_speed = 0.3
        self.angular_speed = 1.57    # π/2 rad/s = 正好 90°/s
        self.patrol_distance = 1.0
        self.patrol_angle = 90.0

        self.get_logger().info("=" * 50)
        self.get_logger().info("🚗 mycar00 (FourWD) 自主巡逻程序")
        self.get_logger().info("=" * 50)
        self.get_logger().info("速度: %.2f m/s, 角速度: %.2f rad/s" %
                              (self.linear_speed, self.angular_speed))
        self.get_logger().info("=" * 50)

    def move_forward(self, distance=None):
        """前进指定距离"""
        dist = distance or self.patrol_distance
        duration = dist / self.linear_speed

        twist = Twist()
        twist.linear.x = self.linear_speed
        twist.angular.z = 0.0

        self.get_logger().info("🚀 前进 %.2f 米" % dist)
        start = time.time()
        while time.time() - start < duration and rclpy.ok():
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.stop()

    def rotate(self, angle_deg=None):
        """旋转指定角度"""
        angle = angle_deg or self.patrol_angle
        # 精确计算：时间 = 角度(rad) / 角速度(rad/s)
        # 90° → π/2 / (π/2) = 1.0 秒
        angle_rad = angle * pi / 180.0
        duration = angle_rad / self.angular_speed

        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = self.angular_speed

        self.get_logger().info("🔄 左转 %.1f 度" % angle)
        start = time.time()
        while time.time() - start < duration and rclpy.ok():
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.stop()

    def stop(self):
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        self.cmd_vel_pub.publish(twist)
        time.sleep(0.5)

    # ============ 巡逻模式 ============

    def patrol_square(self, laps=1):
        """方形巡逻"""
        self.get_logger().info("\n🔲 方形巡逻开始 (%d 圈)" % laps)
        for lap in range(laps):
            self.get_logger().info("第 %d/%d 圈" % (lap + 1, laps))
            for i in range(4):
                self.get_logger().info("  边 %d/4" % (i + 1))
                self.move_forward()
                self.rotate()
        self.get_logger().info("✅ 方形巡逻完成")

    def patrol_forward_backward(self, times=3):
        """直线往返"""
        self.get_logger().info("\n↔️  直线往返开始 (%d 次)" % times)
        for i in range(times):
            self.get_logger().info("第 %d/%d 次" % (i + 1, times))
            self.move_forward()
            # 掉头 180°（π rad，需要 2.0 秒）
            self.rotate(180.0)
            self.move_forward()
            self.rotate(180.0)
        self.get_logger().info("✅ 直线往返完成")

    def patrol_figure8(self, laps=1):
        """8字形巡逻"""
        self.get_logger().info("\n8⃣  8字形巡逻开始 (%d 圈)" % laps)
        for lap in range(laps):
            self.get_logger().info("第 %d/%d 圈" % (lap + 1, laps))
            # 左转弯走半圆
            # 半圆 → 旋转 360° → 时间 = 2π / v_angular
            twist = Twist()
            twist.linear.x = self.linear_speed
            twist.angular.z = self.angular_speed * 0.6
            self.get_logger().info("  左半圆")
            start = time.time()
            while time.time() - start < 6.0 and rclpy.ok():
                self.cmd_vel_pub.publish(twist)
                rclpy.spin_once(self, timeout_sec=0.05)
            self.stop()

            # 右转弯走半圆
            twist.angular.z = -self.angular_speed * 0.6
            self.get_logger().info("  右半圆")
            start = time.time()
            while time.time() - start < 6.0 and rclpy.ok():
                self.cmd_vel_pub.publish(twist)
                rclpy.spin_once(self, timeout_sec=0.05)
            self.stop()
        self.get_logger().info("✅ 8字形巡逻完成")


def main():
    rclpy.init()
    patrol = FourWDPatrol()

    print("\n" + "=" * 50)
    print("  🚗 mycar00 (FourWD) 自主巡逻")
    print("=" * 50)
    print("  请选择巡逻模式:")
    print("   1. 方形巡逻 (1圈)")
    print("   2. 方形巡逻 (3圈)")
    print("   3. 直线往返 (3次)")
    print("   4. 8字形巡逻 (1圈)")
    print("   0. 退出")
    print("=" * 50)

    while rclpy.ok():
        try:
            choice = input("\n请输入选择 (0-4): ").strip()
            if choice == '1':
                patrol.patrol_square(1)
            elif choice == '2':
                patrol.patrol_square(3)
            elif choice == '3':
                patrol.patrol_forward_backward(3)
            elif choice == '4':
                patrol.patrol_figure8(1)
            elif choice == '0':
                break
            else:
                print("无效输入")
        except KeyboardInterrupt:
            break

    patrol.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
