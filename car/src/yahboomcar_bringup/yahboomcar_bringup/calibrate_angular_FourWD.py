#!/usr/bin/env python
# encoding: utf-8

"""
mycar1 (FourWD) 角速度校准程序

功能：校准旋转角速度比例因子
通过让小车旋转指定角度，对比理论值和实际值，计算校准系数。

使用方法：
  ros2 run yahboomcar_bringup calibrate_angular_FourWD

参数：
  test_angular_speed: 测试角速度 (rad/s), 默认 1.0
  test_angle: 测试角度 (度), 默认 90

注意：由于使用 Rosmaster 直接控制硬件，
      本节点独立运行，无需启动 FourWD_driver。
"""

import sys
import math
from math import pi
from time import sleep

from Rosmaster_Lib import Rosmaster

import rclpy
from rclpy.node import Node


class CalibrateAngular(Node):
    def __init__(self, name):
        super().__init__(name)
        self.car = Rosmaster()
        self.car.set_car_type(6)  # 四驱普通轮子

        # 声明参数
        self.declare_parameter('test_angular_speed', 1.0)
        self.declare_parameter('test_angle', 90.0)

        self.test_speed = self.get_parameter(
            'test_angular_speed').get_parameter_value().double_value
        self.test_angle = self.get_parameter(
            'test_angle').get_parameter_value().double_value

        self.get_logger().info("=" * 50)
        self.get_logger().info("🔄 FourWD 角速度校准")
        self.get_logger().info("=" * 50)
        self.get_logger().info("测试角速度: %.2f rad/s" % self.test_speed)
        self.get_logger().info("测试角度: %.1f 度" % self.test_angle)
        self.get_logger().info("=" * 50)

    def calibrate_cw(self):
        """顺时针校准"""
        self.get_logger().info("\n▶️  顺时针旋转 %.1f 度" % self.test_angle)
        sleep(2)

        # 将角度转为弧度，计算运行时间
        angle_rad = self.test_angle * pi / 180.0
        duration = angle_rad / self.test_speed

        self.car.set_car_motion(0, 0, self.test_speed)
        self.get_logger().info("⏳ 旋转中... (%.1f 秒)" % duration)
        sleep(duration)

        self.car.set_car_motion(0, 0, 0)
        self.get_logger().info("⏹️  停止")

        actual = input("\n📐 实际旋转了多少度？(输入角度): ")
        try:
            actual = float(actual)
            if actual > 0:
                correction = self.test_angle / actual
                self.get_logger().info("\n✅ 顺时针校准结果:")
                self.get_logger().info("  理论角度: %.1f°" % self.test_angle)
                self.get_logger().info("  实际角度: %.1f°" % actual)
                self.get_logger().info("  修正系数: %.4f" % correction)
                return correction
        except ValueError:
            self.get_logger().warn("输入无效")
        return 1.0

    def calibrate_ccw(self):
        """逆时针校准"""
        self.get_logger().info("\n◀️  逆时针旋转 %.1f 度" % self.test_angle)
        sleep(2)

        angle_rad = self.test_angle * pi / 180.0
        duration = angle_rad / self.test_speed

        self.car.set_car_motion(0, 0, -self.test_speed)
        self.get_logger().info("⏳ 旋转中... (%.1f 秒)" % duration)
        sleep(duration)

        self.car.set_car_motion(0, 0, 0)
        self.get_logger().info("⏹️  停止")

        actual = input("\n📐 实际旋转了多少度？(输入角度): ")
        try:
            actual = float(actual)
            if actual > 0:
                correction = self.test_angle / actual
                self.get_logger().info("\n✅ 逆时针校准结果:")
                self.get_logger().info("  修正系数: %.4f" % correction)
                return correction
        except ValueError:
            self.get_logger().warn("输入无效")
        return 1.0

    def run(self):
        """执行校准"""
        input("\n⚠️  确保小车周围无障碍物，按回车开始顺时针校准...")
        cw_correction = self.calibrate_cw()

        input("\n⚠️  按回车开始逆时针校准...")
        ccw_correction = self.calibrate_ccw()

        avg_correction = (cw_correction + ccw_correction) / 2.0

        self.get_logger().info("\n" + "=" * 50)
        self.get_logger().info("📌 角速度校准完成！")
        self.get_logger().info("  顺时针修正: %.4f" % cw_correction)
        self.get_logger().info("  逆时针修正: %.4f" % ccw_correction)
        self.get_logger().info("  平均修正: %.4f" % avg_correction)
        self.get_logger().info("=" * 50)


def main():
    rclpy.init()
    calibrator = CalibrateAngular('calibrate_angular')
    calibrator.run()
    calibrator.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
