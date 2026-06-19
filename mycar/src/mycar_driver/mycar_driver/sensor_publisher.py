#!/usr/bin/env python3
"""
sensor_publisher.py — 传感器数据采集与发布
定时读取 MCU 的 IMU、磁力计、电池电压、编码器数据，发布到 ROS2 话题。

发布话题:
  /imu/data_raw   — sensor_msgs/Imu (加速度计 + 陀螺仪)
  /imu/mag        — sensor_msgs/MagneticField
  /voltage        — std_msgs/Float32
  /joint_states   — sensor_msgs/JointState (编码器驱动的轮子转角)
"""
import threading
from math import pi

from rclpy.node import Node
from rclpy.clock import Clock
from std_msgs.msg import Float32
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu, MagneticField, JointState


class SensorPublisher:
    """传感器发布器 — 从 SerialBridge 读取数据并发布到 ROS2"""

    # 编码器转角度系数（需根据实际电机标定）
    # 典型值: 每圈 11 个脉冲 * 减速比 ≈ 需要实测
    ENCODER_TO_RAD = 2.0 * pi / 1000.0  # 预估值，1 脉冲 ≈ 0.00628 rad

    def __init__(self, node: Node, bridge, *,
                 imu_frame_id='imu_Link',
                 joint_names=None,
                 publish_rate=20.0):
        """
        Args:
            node:         ROS2 Node 实例（用于创建 publisher）
            bridge:       SerialBridge 实例
            imu_frame_id: IMU 数据的 frame_id
            joint_names:  关节名称列表 ['fl_joint', 'fr_joint', 'br_joint', 'bl_joint']
            publish_rate: 发布频率 (Hz)
        """
        self._node = node
        self._bridge = bridge
        self._imu_frame_id = imu_frame_id
        self._joint_names = joint_names or [
            'fl_joint', 'fr_joint', 'br_joint', 'bl_joint']

        # --- 发布者 ---
        self._imu_pub = node.create_publisher(Imu, '/imu/data_raw', 30)
        self._mag_pub = node.create_publisher(MagneticField, '/imu/mag', 30)
        self._vol_pub = node.create_publisher(Float32, '/voltage', 10)
        self._vel_pub = node.create_publisher(Twist, '/vel_raw', 30)
        self._joint_pub = node.create_publisher(JointState, '/joint_states', 30)

        # --- 编码器累积值（用于计算差分角度） ---
        self._last_encoder = [0, 0, 0, 0]
        self._first_read = True

        # --- 定时器 ---
        period = 1.0 / publish_rate
        self._timer = node.create_timer(period, self._publish_callback)

        node.get_logger().info(
            f'SensorPublisher 初始化完成: imu_frame={imu_frame_id}, '
            f'joints={self._joint_names}, rate={publish_rate}Hz')

    def _publish_callback(self):
        """定时回调：读取传感器并发布"""
        try:
            self._do_publish()
        except Exception as e:
            self._node.get_logger().error(f'传感器回调异常: {e}', throttle_duration_sec=5.0)

    def _do_publish(self):
        stamp = Clock().now().to_msg()

        # === IMU (加速度计 + 陀螺仪) ===
        ax, ay, az = self._bridge.read_accelerometer()
        gx, gy, gz = self._bridge.read_gyroscope()

        # 跳过全零数据（MCU 尚未初始化完成，避免 imu_filter 报 free fall）
        if not (ax == 0.0 and ay == 0.0 and az == 0.0 and
                gx == 0.0 and gy == 0.0 and gz == 0.0):
            imu = Imu()
            imu.header.stamp = stamp
            imu.header.frame_id = self._imu_frame_id
            imu.linear_acceleration.x = ax
            imu.linear_acceleration.y = ay
            imu.linear_acceleration.z = az
            imu.angular_velocity.x = gx
            imu.angular_velocity.y = gy
            imu.angular_velocity.z = gz
            self._imu_pub.publish(imu)

        # === 磁力计 ===
        mx, my, mz = self._bridge.read_magnetometer()
        mag = MagneticField()
        mag.header.stamp = stamp
        mag.header.frame_id = self._imu_frame_id
        mag.magnetic_field.x = mx
        mag.magnetic_field.y = my
        mag.magnetic_field.z = mz
        self._mag_pub.publish(mag)

        # === 电池电压 ===
        voltage = self._bridge.read_battery()
        v = Float32()
        v.data = voltage
        self._vol_pub.publish(v)

        # === 速度（供里程计使用） ===
        vx, vy, vz = self._bridge.read_motion()
        twist = Twist()
        twist.linear.x = -vx  # MCU→ROS: MCU 负=前进，ROS 正=前进
        twist.linear.y = 0.0
        twist.angular.z = vz   # 角速度符号正常
        self._vel_pub.publish(twist)

        # === 关节状态（编码器增量 → 轮子转动可视化） ===
        enc = self._bridge.read_encoder()
        js = JointState()
        js.header.stamp = stamp
        js.header.frame_id = 'joint_states'
        js.name = list(self._joint_names)

        if self._first_read:
            self._first_read = False
            js.position = [0.0] * len(self._joint_names)
        else:
            positions = []
            for i in range(min(len(enc), len(self._joint_names))):
                delta = enc[i] - self._last_encoder[i]
                positions.append(delta * self.ENCODER_TO_RAD)
            while len(positions) < len(self._joint_names):
                positions.append(0.0)
            js.position = positions

        self._last_encoder = list(enc)
        self._joint_pub.publish(js)

        # === 周期性静音（每 2 秒，仅关蜂鸣器，不碰运动状态） ===
        self._beep_counter = getattr(self, '_beep_counter', 0) + 1
        if self._beep_counter % 40 == 0:
            try:
                self._bridge.set_beep(0)
            except Exception:
                pass
