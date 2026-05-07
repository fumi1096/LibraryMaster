#!/usr/bin/env python
# encoding: utf-8
"""
四驱普通轮子驱动节点 (FourWD_driver)
适用于四轮独立驱动、差速转向的普通轮小车（如 mycar1）

与 X3 驱动节点的区别：
1. car_type = 6 (FOURWD)，表示四驱普通轮子
2. vy（横向速度）强制设为 0，普通轮子不支持横向移动
3. 关节名适配 mycar1 的 URDF：fl_joint, fr_joint, br_joint, bl_joint
4. IMU link 名适配 mycar1：imu_Link（注意大小写）

硬件依赖：Rosmaster_Lib（与厂家驱动板通信）
"""

# public lib
import sys
import math
import random
import threading
from math import pi
from time import sleep
from Rosmaster_Lib import Rosmaster

# ros lib
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32, Int32, Bool
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu, MagneticField, JointState
from rclpy.clock import Clock

car_type_dic = {
    'R2': 5,
    'X3': 1,
    'X1': 4,
    'FOURWD': 1,  # 四驱普通轮子：使用X3类型(1)，vy=0时等同于差速驱动
    'NONE': -1
}


class yahboomcar_driver(Node):
    def __init__(self, name):
        super().__init__(name)
        global car_type_dic
        self.RA2DE = 180 / pi
        self.car = Rosmaster()
        self.car.set_car_type(1)  # 使用X3类型，vy=0时就是标准差速驱动

        # === 参数声明 ===
        self.declare_parameter('car_type', 'FOURWD')
        self.car_type = self.get_parameter('car_type').get_parameter_value().string_value

        # 注意：mycar1 URDF 中 IMU link 名为 imu_Link（大写L）
        self.declare_parameter('imu_link', 'imu_Link')
        self.imu_link = self.get_parameter('imu_link').get_parameter_value().string_value

        self.declare_parameter('Prefix', "")
        self.Prefix = self.get_parameter('Prefix').get_parameter_value().string_value

        self.declare_parameter('xlinear_limit', 1.0)
        self.xlinear_limit = self.get_parameter('xlinear_limit').get_parameter_value().double_value

        # 四驱普通轮子：横向速度限制为0，不支持横移
        self.declare_parameter('ylinear_limit', 0.0)
        self.ylinear_limit = self.get_parameter('ylinear_limit').get_parameter_value().double_value

        self.declare_parameter('angular_limit', 3.0)
        self.angular_limit = self.get_parameter('angular_limit').get_parameter_value().double_value

        # 打印参数
        self.get_logger().info("car_type: %s" % self.car_type)
        self.get_logger().info("imu_link: %s" % self.imu_link)
        self.get_logger().info("Prefix: %s" % self.Prefix)
        self.get_logger().info("xlinear_limit: %.2f" % self.xlinear_limit)
        self.get_logger().info("ylinear_limit: %.2f" % self.ylinear_limit)
        self.get_logger().info("angular_limit: %.2f" % self.angular_limit)

        # === 订阅话题 ===
        # cmd_vel：接收导航/手柄下发的运动控制指令
        self.sub_cmd_vel = self.create_subscription(
            Twist, "cmd_vel", self.cmd_vel_callback, 1)
        # RGB灯控制（兼容厂家协议）
        self.sub_RGBLight = self.create_subscription(
            Int32, "RGBLight", self.RGBLightcallback, 100)
        # 蜂鸣器控制（兼容厂家协议）
        self.sub_BUzzer = self.create_subscription(
            Bool, "Buzzer", self.Buzzercallback, 100)

        # === 发布话题 ===
        # vel_raw：发布原始速度数据，供里程计节点(base_node)订阅
        self.velPublisher = self.create_publisher(Twist, "vel_raw", 50)
        # IMU传感器数据
        self.imuPublisher = self.create_publisher(Imu, "/imu/data_raw", 100)
        # 磁力计数据
        self.magPublisher = self.create_publisher(MagneticField, "/imu/mag", 100)
        # 电池电压
        self.volPublisher = self.create_publisher(Float32, "voltage", 100)
        # 驱动版本
        self.EdiPublisher = self.create_publisher(Float32, "edition", 100)
        # 关节状态（用于RViz可视化轮子转动）
        self.staPublisher = self.create_publisher(JointState, "joint_states", 100)

        # === 定时器 ===
        # 每 0.1 秒发布一次传感器数据
        self.timer = self.create_timer(0.1, self.pub_data)

        # === 初始化 ===
        self.edition = Float32()
        self.edition.data = 1.0
        self.car.create_receive_threading()

        # === 串口通信测试 ===
        # 读取版本号验证通信正常
        version = self.car.get_version()
        battery = self.car.get_battery_voltage()
        self.get_logger().info("驱动板版本: %.2f" % version)
        self.get_logger().info("电池电压: %.2f V" % battery)

        if version == 0.0 and battery == 0.0:
            self.get_logger().error("❌ 串口通信失败！请检查 /dev/myserial 连接")
        else:
            self.get_logger().info("✅ 串口通信正常")

        # 关闭蜂鸣器（防止旧代码或误操作导致蜂鸣器一直响）
        for i in range(3):
            self.car.set_beep(0)
        self.get_logger().info("🔕 蜂鸣器已关闭")

        self.get_logger().info("=" * 50)
        self.get_logger().info("FourWD driver node started! 车型: %s" % self.car_type)

    # ========== 回调函数 ==========

    def cmd_vel_callback(self, msg):
        """
        运动控制回调
        对于四驱普通轮子：
        - vx: 前进/后退速度（有效）
        - vy: 横向速度（强制为0，普通轮不支持横移）
        - angular: 旋转角速度（有效）
        """
        if not isinstance(msg, Twist):
            return
        # ⚠️ 硬件电机接线方向与ROS标准相反，vx取反以匹配
        # ROS标准：vx>0=前进，vx<0=后退
        vx = -msg.linear.x * 1.0
        # 四驱普通轮子不支持横向移动，vy 强制设为 0
        vy = 0.0
        angular = msg.angular.z * 1.0

        # 速度限幅
        if abs(vx) > self.xlinear_limit:
            vx = self.xlinear_limit if vx > 0 else -self.xlinear_limit
        if abs(angular) > self.angular_limit:
            angular = self.angular_limit if angular > 0 else -self.angular_limit

        # 下发运动指令
        self.car.set_car_motion(vx, vy, angular)

    def RGBLightcallback(self, msg):
        """流水灯控制"""
        if not isinstance(msg, Int32):
            return
        for i in range(3):
            self.car.set_colorful_effect(msg.data, 6, parm=1)

    def Buzzercallback(self, msg):
        """蜂鸣器控制"""
        if not isinstance(msg, Bool):
            return
        if msg.data:
            for i in range(3):
                self.car.set_beep(1)
        else:
            for i in range(3):
                self.car.set_beep(0)

    # ========== 数据发布 ==========

    def pub_data(self):
        """
        定时发布传感器数据（IMU、磁力计、电池、速度、关节状态）
        """
        time_stamp = Clock().now()

        # --- 读取传感器数据 ---
        ax, ay, az = self.car.get_accelerometer_data()
        gx, gy, gz = self.car.get_gyroscope_data()
        mx, my, mz = self.car.get_magnetometer_data()
        vx, vy, angular = self.car.get_motion_data()
        battery_voltage = self.car.get_battery_voltage() * 1.0
        edition_val = self.car.get_version() * 1.0

        # --- 发布 IMU 数据 ---
        imu = Imu()
        imu.header.stamp = time_stamp.to_msg()
        imu.header.frame_id = self.imu_link
        imu.linear_acceleration.x = ax * 1.0
        imu.linear_acceleration.y = ay * 1.0
        imu.linear_acceleration.z = az * 1.0
        imu.angular_velocity.x = gx * 1.0
        imu.angular_velocity.y = gy * 1.0
        imu.angular_velocity.z = gz * 1.0

        # --- 发布磁力计数据 ---
        mag = MagneticField()
        mag.header.stamp = time_stamp.to_msg()
        mag.header.frame_id = self.imu_link
        mag.magnetic_field.x = mx * 1.0
        mag.magnetic_field.y = my * 1.0
        mag.magnetic_field.z = mz * 1.0

        # --- 发布速度数据 ---
        twist = Twist()
        twist.linear.x = vx * 1.0
        twist.linear.y = 0.0  # 四驱普通轮无横向速度
        twist.angular.z = angular * 1.0

        # --- 发布关节状态（用于RViz轮子可视化） ---
        state = JointState()
        state.header.stamp = time_stamp.to_msg()
        state.header.frame_id = "joint_states"
        if len(self.Prefix) == 0:
            state.name = ["fl_joint", "fr_joint", "br_joint", "bl_joint"]
        else:
            state.name = [
                self.Prefix + "fl_joint",
                self.Prefix + "fr_joint",
                self.Prefix + "br_joint",
                self.Prefix + "bl_joint"
            ]
        # 关节位置（简化处理，便于RViz中观察轮子转动）
        if vx == 0 and angular == 0:
            state.position = [0.0, 0.0, 0.0, 0.0]
        else:
            # 根据速度估算轮子角度变化
            wheel_angle = time_stamp.nanoseconds * vx * 0.001
            state.position = [wheel_angle, wheel_angle, wheel_angle, wheel_angle]

        # --- 发布电池和版本 ---
        battery = Float32()
        battery.data = battery_voltage
        edition = Float32()
        edition.data = edition_val

        # --- 一次性发布所有话题 ---
        self.imuPublisher.publish(imu)
        self.magPublisher.publish(mag)
        self.velPublisher.publish(twist)
        self.staPublisher.publish(state)
        self.volPublisher.publish(battery)
        self.EdiPublisher.publish(edition)


def main():
    rclpy.init()
    driver = yahboomcar_driver('driver_node')
    rclpy.spin(driver)


if __name__ == '__main__':
    main()
