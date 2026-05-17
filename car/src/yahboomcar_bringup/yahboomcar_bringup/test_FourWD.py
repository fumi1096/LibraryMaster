#!/usr/bin/env python
# encoding: utf-8

"""
mycar00 (FourWD) 综合测试程序

功能：按顺序执行一系列标准测试，验证小车的各项基本功能
- 前进、后退、左转、右转
- 不同速度下的稳定性
- 前进中转弯（弧线运动）

使用方法：
  ros2 run yahboomcar_bringup test_FourWD

注意：需要先启动 FourWD_driver 节点
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import sys
from math import pi

# 精确角度计算
# 90° = π/2 rad ≈ 1.57 rad
# 旋转时间 = 目标角度(rad) / 角速度(rad/s) ← 闭环电机精确执行


class FourWDTest(Node):
    def __init__(self):
        super().__init__('fourwd_test_node')

        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)

        # 测试参数
        self.linear_speed = 0.3        # 线速度 (m/s)
        self.angular_speed = 1.57       # 角速度 = π/2 rad/s (90°/s)
        self.test_duration = 2.0    # 每个测试持续时间 (s)
        self.wait_time = 0.5        # 测试间等待时间 (s)

        self.get_logger().info("=" * 50)
        self.get_logger().info("🚗 mycar00 (FourWD) 综合测试程序")
        self.get_logger().info("=" * 50)
        self.get_logger().info("线速度: %.2f m/s" % self.linear_speed)
        self.get_logger().info("角速度: %.2f rad/s" % self.angular_speed)
        self.get_logger().info("测试持续时间: %.1f 秒" % self.test_duration)
        self.get_logger().info("=" * 50)

    def publish_velocity(self, vx, vy, angular, duration):
        """发布速度并持续指定时间"""
        twist = Twist()
        twist.linear.x = vx
        twist.linear.y = vy       # 四驱普通轮：vy 保持 0
        twist.angular.z = angular

        self.cmd_vel_pub.publish(twist)
        self.get_logger().info("→ 速度: vx=%.2f, vy=%.2f, ω=%.2f  [%.1fs]" % (
            vx, vy, angular, duration))

        start_time = time.time()
        while time.time() - start_time < duration and rclpy.ok():
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.05)

    def stop_robot(self):
        """停止"""
        twist = Twist()
        twist.linear.x = 0.0
        twist.linear.y = 0.0
        twist.angular.z = 0.0
        self.cmd_vel_pub.publish(twist)
        self.get_logger().info("⏹️  停止")
        time.sleep(self.wait_time)

    # ============ 测试用例 ============

    def test_forward(self):
        """测试1: 前进"""
        self.get_logger().info("\n[测试1/7] 🚀 前进")
        self.publish_velocity(self.linear_speed, 0.0, 0.0, self.test_duration)
        self.stop_robot()

    def test_backward(self):
        """测试2: 后退"""
        self.get_logger().info("\n[测试2/7] 🔄 后退")
        self.publish_velocity(-self.linear_speed, 0.0, 0.0, self.test_duration)
        self.stop_robot()

    def test_rotate_cw(self):
        """测试3: 顺时针旋转"""
        self.get_logger().info("\n[测试3/7] 🔄 顺时针旋转")
        self.publish_velocity(0.0, 0.0, -self.angular_speed, self.test_duration)
        self.stop_robot()

    def test_rotate_ccw(self):
        """测试4: 逆时针旋转"""
        self.get_logger().info("\n[测试4/7] 🔄 逆时针旋转")
        self.publish_velocity(0.0, 0.0, self.angular_speed, self.test_duration)
        self.stop_robot()

    def test_arc_left(self):
        """测试5: 左弧线（前进+左转）"""
        self.get_logger().info("\n[测试5/7] 🌈 左弧线运动")
        self.publish_velocity(
            self.linear_speed * 0.5, 0.0, self.angular_speed * 0.5, self.test_duration)
        self.stop_robot()

    def test_arc_right(self):
        """测试6: 右弧线（前进+右转）"""
        self.get_logger().info("\n[测试6/7] 🌈 右弧线运动")
        self.publish_velocity(
            self.linear_speed * 0.5, 0.0, -self.angular_speed * 0.5, self.test_duration)
        self.stop_robot()

    def test_speed_variations(self):
        """测试7: 不同速度下的前进"""
        self.get_logger().info("\n[测试7/7] ⚡ 速度变化测试")
        speeds = [0.1, 0.2, 0.3, 0.5]
        for speed in speeds:
            self.get_logger().info("  速度: %.1f m/s" % speed)
            self.publish_velocity(speed, 0.0, 0.0, 1.0)
            self.stop_robot()

    def run_all_tests(self):
        """运行所有测试"""
        self.get_logger().info("\n" + "=" * 50)
        self.get_logger().info("开始执行全部测试 (共7项)")
        self.get_logger().info("=" * 50)

        self.test_forward()
        self.test_backward()
        self.test_rotate_cw()
        self.test_rotate_ccw()
        self.test_arc_left()
        self.test_arc_right()
        self.test_speed_variations()

        self.get_logger().info("\n" + "=" * 50)
        self.get_logger().info("✅ 全部测试完成！")
        self.get_logger().info("=" * 50)


def main():
    rclpy.init()
    test_node = FourWDTest()

    print("\n" + "=" * 50)
    print("  🚗 mycar00 (FourWD) 综合测试程序")
    print("=" * 50)
    print("  请选择:")
    print("   1. 运行全部测试")
    print("   2. 仅测试前进/后退")
    print("   3. 仅测试旋转")
    print("   4. 仅测试弧线运动")
    print("   0. 退出")
    print("=" * 50)

    while rclpy.ok():
        try:
            choice = input("\n请输入选择 (0-4): ").strip()
            if choice == '1':
                test_node.run_all_tests()
            elif choice == '2':
                test_node.test_forward()
                test_node.test_backward()
            elif choice == '3':
                test_node.test_rotate_cw()
                test_node.test_rotate_ccw()
            elif choice == '4':
                test_node.test_arc_left()
                test_node.test_arc_right()
            elif choice == '0':
                break
            else:
                print("无效输入")
        except KeyboardInterrupt:
            break

    test_node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
