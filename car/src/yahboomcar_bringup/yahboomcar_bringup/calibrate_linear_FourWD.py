#!/usr/bin/env python
# encoding: utf-8

"""
mycar00 (FourWD) 线性速度校准程序

功能：校准前进/后退的线性速度比例因子 (linear_scale_x)
通过让小车实际行驶一段距离，对比理论值和实际值，计算校准系数。

使用方法：
  方式1 - 直接硬件控制（不依赖ROS）：
    ros2 run yahboomcar_bringup calibrate_linear_FourWD

  方式2 - 通过ROS栈（需要FourWD_driver运行）：
    先启动 FourWD_driver，再手动发布 cmd_vel 测试

校准步骤：
  1. 小车前进指定距离
  2. 测量实际行驶距离
  3. 计算比例因子 correction = 理论距离 / 实际距离
  4. 更新 base_node_fourwd 的 linear_scale_x 参数

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


class CalibrateLinear(Node):
    def __init__(self, name):
        super().__init__(name)
        self.car = Rosmaster()
        self.car.set_car_type(6)  # 四驱普通轮子

        # 声明参数
        self.declare_parameter('test_speed', 0.3)
        self.declare_parameter('test_distance', 1.0)
        self.declare_parameter('linear_scale_x', 1.0)
        self.declare_parameter('calibrate_backward', True)

        self.test_speed = self.get_parameter(
            'test_speed').get_parameter_value().double_value
        self.test_distance = self.get_parameter(
            'test_distance').get_parameter_value().double_value
        self.scale_x = self.get_parameter(
            'linear_scale_x').get_parameter_value().double_value
        self.calibrate_backward = self.get_parameter(
            'calibrate_backward').get_parameter_value().bool_value

        self.get_logger().info("=" * 50)
        self.get_logger().info("📏 FourWD 线性速度校准")
        self.get_logger().info("=" * 50)
        self.get_logger().info("测试速度: %.2f m/s" % self.test_speed)
        self.get_logger().info("测试距离: %.2f m" % self.test_distance)
        self.get_logger().info("当前比例因子: %.3f" % self.scale_x)
        self.get_logger().info("=" * 50)

    def calibrate_forward(self):
        """前向校准"""
        self.get_logger().info("\n🚀 前进校准")
        self.get_logger().info("小车将以 %.2f m/s 前进 %.2f 米" %
                              (self.test_speed, self.test_distance))
        self.get_logger().info("请观察并测量实际行驶距离！")
        sleep(2)

        # 前进
        duration = self.test_distance / self.test_speed
        self.car.set_car_motion(self.test_speed, 0, 0)
        self.get_logger().info("⏳ 运行中... (%.1f 秒)" % duration)
        sleep(duration)

        # 停止
        self.car.set_car_motion(0, 0, 0)
        self.get_logger().info("⏹️  停止")

        # 用户输入实际距离
        actual = input("\n📐 请输入实际行驶距离 (米): ")
        try:
            actual = float(actual)
            if actual > 0:
                correction = self.test_distance / actual
                self.scale_x *= correction
                self.get_logger().info("\n✅ 校准结果:")
                self.get_logger().info("  理论距离: %.2f m" % self.test_distance)
                self.get_logger().info("  实际距离: %.2f m" % actual)
                self.get_logger().info("  修正系数: %.4f" % correction)
                self.get_logger().info(
                    "  建议设置 linear_scale_x = %.4f" % self.scale_x)
            else:
                self.get_logger().warn("距离必须大于0")
        except ValueError:
            self.get_logger().warn("输入无效，跳过校准")

    def calibrate_backward_func(self):
        """后向校准"""
        if not self.calibrate_backward:
            return

        self.get_logger().info("\n🔙 后退校准")
        self.get_logger().info("小车将以 %.2f m/s 后退 %.2f 米" %
                              (self.test_speed, self.test_distance))
        sleep(2)

        duration = self.test_distance / self.test_speed
        self.car.set_car_motion(-self.test_speed, 0, 0)
        self.get_logger().info("⏳ 运行中... (%.1f 秒)" % duration)
        sleep(duration)

        self.car.set_car_motion(0, 0, 0)
        self.get_logger().info("⏹️  停止")

        actual = input("\n📐 请输入实际后退距离 (米): ")
        try:
            actual = float(actual)
            if actual > 0:
                correction = self.test_distance / actual
                self.get_logger().info("\n✅ 后退校准结果:")
                self.get_logger().info("  修正系数: %.4f" % correction)
        except ValueError:
            self.get_logger().warn("输入无效")

    def run(self):
        """执行校准"""
        input("\n⚠️  请确保小车前方 %.2f 米无障碍物，按回车开始..." %
              self.test_distance)
        self.calibrate_forward()

        if self.calibrate_backward:
            input("\n⚠️  请确保小车后方 %.2f 米无障碍物，按回车开始..." %
                  self.test_distance)
            self.calibrate_backward_func()

        self.get_logger().info("\n" + "=" * 50)
        self.get_logger().info("📌 校准完成！")
        self.get_logger().info("请将 base_node_fourwd 的 linear_scale_x 参数更新为: %.4f" %
                              self.scale_x)
        self.get_logger().info("=" * 50)


def main():
    rclpy.init()
    calibrator = CalibrateLinear('calibrate_linear')
    calibrator.run()
    calibrator.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
