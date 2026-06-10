#!/usr/bin/env python3
"""
driver_node.py — mycar 四驱小车驱动主节点

组合 serial_bridge + sensor_publisher + motion_controller，
统一管理 ROS2 接口和 MCU 通信。

启动:
  ros2 run mycar_driver driver_node --ros-args -p serial_port:="/dev/ttyUSB0"
  ros2 launch mycar_driver driver.launch.py
"""
import rclpy
from rclpy.node import Node

from .serial_bridge import SerialBridge
from .sensor_publisher import SensorPublisher
from .motion_controller import MotionController


class DriverNode(Node):
    """mycar 驱动主节点"""

    def __init__(self):
        super().__init__('driver_node')

        # === 声明参数 ===
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('car_type', 1)
        self.declare_parameter('imu_frame_id', 'imu_Link')
        self.declare_parameter('base_frame_id', 'base_link')
        self.declare_parameter('joint_names', [
            'fl_joint', 'fr_joint', 'br_joint', 'bl_joint'])
        self.declare_parameter('linear_x_limit', 1.0)
        self.declare_parameter('angular_limit', 3.0)
        self.declare_parameter('invert_vx', False)
        self.declare_parameter('sensor_publish_rate', 20.0)
        self.declare_parameter('debug', False)

        # 读取参数
        serial_port = self.get_parameter('serial_port').value
        car_type = self.get_parameter('car_type').value
        imu_frame_id = self.get_parameter('imu_frame_id').value
        joint_names = self.get_parameter('joint_names').value
        linear_x_limit = self.get_parameter('linear_x_limit').value
        angular_limit = self.get_parameter('angular_limit').value
        invert_vx = self.get_parameter('invert_vx').value
        sensor_rate = self.get_parameter('sensor_publish_rate').value
        debug = self.get_parameter('debug').value

        # === 初始化串口 ===
        self.get_logger().info(f'正在连接串口: {serial_port} ...')
        try:
            self._bridge = SerialBridge(
                port=serial_port, car_type=car_type, debug=debug)
        except ConnectionError as e:
            self.get_logger().error(str(e))
            self.get_logger().error('❌ 串口连接失败！请检查:')
            self.get_logger().error(f'  1. 设备路径是否正确: {serial_port}')
            self.get_logger().error(f'  2. 是否有权限: sudo chmod 666 {serial_port}')
            self.get_logger().error(f'  3. 驱动板是否已上电')
            raise

        self.get_logger().info(f'✅ 串口已连接: {serial_port}')
        self.get_logger().info(
            f'固件版本: V{self._bridge.firmware_version:.1f}')
        self.get_logger().info(
            f'电池电压: {self._bridge.battery_voltage:.1f}V')

        # === 初始化子模块 ===
        self._sensors = SensorPublisher(
            self, self._bridge,
            imu_frame_id=imu_frame_id,
            joint_names=joint_names,
            publish_rate=sensor_rate)

        self._motion = MotionController(
            self, self._bridge,
            linear_x_limit=linear_x_limit,
            angular_limit=angular_limit,
            invert_vx=invert_vx)

        # === 输出信息 ===
        self.get_logger().info('=' * 50)
        self.get_logger().info('mycar_driver 驱动节点已启动')
        self.get_logger().info(f'  车型: {"FOURWD (差速)" if car_type == 1 else car_type}')
        self.get_logger().info(f'  IMU 帧: {imu_frame_id}')
        self.get_logger().info(f'  关节: {joint_names}')
        self.get_logger().info(f'  速度限制: vx={linear_x_limit}, angular={angular_limit}')
        self.get_logger().info(f'  发布频率: {sensor_rate}Hz')
        self.get_logger().info('=' * 50)

    def destroy_node(self):
        """清理资源"""
        self.get_logger().info('正在停止驱动节点...')
        if hasattr(self, '_motion'):
            self._motion.stop()
        if hasattr(self, '_bridge'):
            self._bridge.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = DriverNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'驱动节点异常: {e}')
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
