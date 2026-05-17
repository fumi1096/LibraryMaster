#!/usr/bin/env python
# encoding: utf-8

"""
mycar00 (FourWD) 简单交互测试程序

功能：通过交互菜单选择，测试小车的基本运动功能
- 快速测试：前进→后退→左转→右转
- 电机测试：每个方向单独测试
- 方形路径：走一个正方形
- 圆形路径：画圆

使用方法：
  ros2 run yahboomcar_bringup simple_test

注意：需要先启动 FourWD_driver 节点
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
import time
from math import pi


# 精确角度计算
# 90° = π/2 rad ≈ 1.57 rad
# 旋转时间 = 目标角度(rad) / 角速度(rad/s) ← 闭环电机精确执行

class SimpleFourWDTest(Node):
    def __init__(self):
        super().__init__('simple_fourwd_test')

        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.status_pub = self.create_publisher(String, 'test_status', 10)

        self.get_logger().info("=" * 50)
        self.get_logger().info("🚗 mycar00 (FourWD) 简单测试程序")
        self.get_logger().info("=" * 50)
        self.get_logger().info("请确保 FourWD_driver 节点已启动！")
        self.get_logger().info("=" * 50)

    def publish_status(self, status):
        msg = String()
        msg.data = status
        self.status_pub.publish(msg)
        self.get_logger().info("[状态] %s" % status)

    def move_forward(self, speed=0.3, duration=1.0):
        self.publish_status("前进 %.1f m/s, 持续 %.1f s" % (speed, duration))
        twist = Twist()
        twist.linear.x = speed
        twist.angular.z = 0.0
        start_time = time.time()
        while time.time() - start_time < duration:
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.stop_robot()

    def move_backward(self, speed=0.3, duration=1.0):
        self.publish_status("后退 %.1f m/s, 持续 %.1f s" % (speed, duration))
        twist = Twist()
        twist.linear.x = -speed
        twist.angular.z = 0.0
        start_time = time.time()
        while time.time() - start_time < duration:
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.stop_robot()

    def rotate_left(self, speed=1.57, duration=1.0):
        """
        左转 90° (默认参数)
        90° = π/2 rad ≈ 1.57 rad
        时间 = 1.57 rad / 1.57 rad/s = 1.0 s
        """
        self.publish_status("左转 %.1f°, %.1f rad/s, %.1f s" % (duration * speed * 180 / pi, speed, duration))
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = speed
        start_time = time.time()
        while time.time() - start_time < duration:
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.stop_robot()

    def rotate_right(self, speed=1.57, duration=1.0):
        """
        右转 90° (默认参数)
        """
        self.publish_status("右转 %.1f°, %.1f rad/s, %.1f s" % (duration * speed * 180 / pi, speed, duration))
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = -speed
        start_time = time.time()
        while time.time() - start_time < duration:
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.stop_robot()

    def stop_robot(self):
        twist = Twist()
        twist.linear.x = 0.0
        twist.linear.y = 0.0
        twist.angular.z = 0.0
        self.cmd_vel_pub.publish(twist)
        time.sleep(0.3)

    # ============ 测试序列 ============

    def run_quick_test(self):
        """快速测试：各个方向简单试一下"""
        self.publish_status("=== 快速测试开始 ===")
        self.get_logger().info("\n⚡ 快速测试")
        self.get_logger().info("-" * 40)
        self.move_forward(0.3, 1.0)
        self.move_backward(0.3, 1.0)
        self.rotate_left(0.5, 1.0)
        self.rotate_right(0.5, 1.0)
        self.publish_status("=== 快速测试完成 ===")

    def test_motors(self):
        """完整电机测试"""
        self.publish_status("=== 电机测试开始 ===")
        self.get_logger().info("\n🔧 电机测试")
        self.get_logger().info("-" * 40)

        self.get_logger().info("[1/4] 前进")
        self.move_forward(0.2, 2.0)
        time.sleep(0.5)

        self.get_logger().info("[2/4] 后退")
        self.move_backward(0.2, 2.0)
        time.sleep(0.5)

        self.get_logger().info("[3/4] 左转 90°")
        self.rotate_left(1.57, 1.0)   # π/2 ÷ π/2 = 1.0s → 90°
        time.sleep(0.5)

        self.get_logger().info("[4/4] 右转 90°")
        self.rotate_right(1.57, 1.0)  # 回到原位
        time.sleep(0.5)

        self.publish_status("=== 电机测试完成 ===")

    def test_square(self):
        """方形路径测试"""
        self.publish_status("=== 方形路径测试开始 ===")
        self.get_logger().info("\n🔲 方形路径测试")
        self.get_logger().info("-" * 40)

        for i in range(4):
            self.get_logger().info("边 %d/4" % (i + 1))
            self.move_forward(0.3, 1.5)
            self.get_logger().info("转向 %d/4 (90°)" % (i + 1))
            self.rotate_left(1.57, 1.0)  # 90°

        self.publish_status("=== 方形路径测试完成 ===")

    def test_circle(self):
        """圆形路径测试"""
        self.publish_status("=== 圆形路径测试开始 ===")
        self.get_logger().info("\n⭕ 圆形路径测试")
        self.get_logger().info("-" * 40)

        twist = Twist()
        twist.linear.x = 0.2
        twist.angular.z = 0.3

        start_time = time.time()
        while time.time() - start_time < 8.0:
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.05)

        self.stop_robot()
        self.publish_status("=== 圆形路径测试完成 ===")


def main():
    rclpy.init()
    test_node = SimpleFourWDTest()

    print("\n" + "=" * 50)
    print("   🚗 mycar00 (FourWD) 简单测试程序")
    print("=" * 50)
    print("  请选择测试模式:")
    print("   1. 快速测试 (推荐)")
    print("   2. 完整电机测试")
    print("   3. 方形路径测试")
    print("   4. 圆形路径测试")
    print("   0. 退出")
    print("=" * 50)

    while rclpy.ok():
        try:
            choice = input("\n请输入选择 (0-4): ").strip()
            if choice == '1':
                test_node.run_quick_test()
            elif choice == '2':
                test_node.test_motors()
            elif choice == '3':
                test_node.test_square()
            elif choice == '4':
                test_node.test_circle()
            elif choice == '0':
                print("退出测试程序。")
                break
            else:
                print("无效输入，请输入 0-4")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("错误: %s" % str(e))

    test_node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
