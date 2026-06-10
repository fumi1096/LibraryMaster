#!/usr/bin/env python3
"""
serial_bridge.py — 串口通信封装层
封装 Rosmaster_Lib 驱动库，提供线程安全的数据读写接口。

硬件依赖: Rosmaster_Lib (Yahboom Rosmaster 主板驱动)
"""
import threading
import time
from Rosmaster_Lib import Rosmaster


class SerialBridge:
    """串口桥接器 — 封装与 MCU 主板的串口通信"""

    # 支持的车型常量
    CAR_TYPES = {
        'X3': 1,       # 四驱麦克纳姆轮
        'X3_PLUS': 2,
        'X1': 4,
        'R2': 5,       # 阿克曼转向
        'FOURWD': 1,   # 四驱普通轮 = X3 类型（差速）
    }

    def __init__(self, port='/dev/ttyUSB0', car_type=1, debug=False):
        """
        初始化串口连接。

        Args:
            port:     串口设备路径，如 /dev/ttyUSB0, /dev/myserial
            car_type: 小车类型，参见 CAR_TYPES
            debug:    是否开启调试输出
        """
        self._port = port
        self._car_type = car_type
        self._lock = threading.Lock()
        self._connected = False
        self._version = 0.0
        self._battery = 0.0

        try:
            self._bot = Rosmaster(car_type=car_type, com=port, debug=debug)
            self._bot.create_receive_threading()

            # 等待接收线程启动并产生第一批有效数据（最多等 2 秒）
            self._version = 0.0
            self._battery = 0.0
            for _ in range(20):
                time.sleep(0.1)
                self._version = self._bot.get_version()
                self._battery = self._bot.get_battery_voltage()
                if self._version > 0.0 or self._battery > 0.0:
                    break

            if self._version > 0.0 or self._battery > 0.0:
                self._connected = True
                time.sleep(0.5)  # 等 IMU 数据稳定
        except Exception as e:
            self._connected = False
            self._bot = None
            raise ConnectionError(f"串口连接失败 ({port}): {e}")

        # 强制复位 + 关闭蜂鸣器
        self._silence()

    def _silence(self):
        """强制静音：先 reset_car_state 再循环 set_beep"""
        try:
            self._bot.reset_car_state()
            time.sleep(0.3)
        except Exception:
            pass
        for _ in range(10):
            try:
                self._bot.set_beep(0)
                time.sleep(0.05)
            except Exception:
                pass

    # ==================== 属性 ====================

    @property
    def connected(self):
        return self._connected

    @property
    def firmware_version(self):
        return self._version

    @property
    def battery_voltage(self):
        return self._battery

    # ==================== 传感器读取 ====================

    # Rosmaster_Lib 内部已做线程安全，不加额外锁避免与接收线程死锁
    def read_accelerometer(self):
        return self._bot.get_accelerometer_data()

    def read_gyroscope(self):
        return self._bot.get_gyroscope_data()

    def read_magnetometer(self):
        return self._bot.get_magnetometer_data()

    def read_motion(self):
        return self._bot.get_motion_data()

    def read_encoder(self):
        return self._bot.get_motor_encoder()

    def read_battery(self):
        return self._bot.get_battery_voltage()

    def read_version(self):
        return self._bot.get_version()

    # ==================== 运动控制 ====================

    def set_motion(self, vx, vy, angular):
        """
        闭环运动控制（受 PID 参数影响）。

        Args:
            vx:      X 轴线速度 (m/s)，范围 [-1.0, 1.0]
            vy:      横向速度，四驱普通轮固定为 0
            angular: Z 轴角速度 (rad/s)，范围 [-5, 5]
        """
        with self._lock:
            self._bot.set_car_motion(vx, vy, angular)

    def stop(self):
        """紧急停止"""
        with self._lock:
            self._bot.set_car_motion(0.0, 0.0, 0.0)

    # ==================== 外设控制 ====================

    def set_beep(self, duration_ms):
        """蜂鸣器: 0=关闭, 1=持续, >=10=响xx毫秒"""
        with self._lock:
            self._bot.set_beep(duration_ms)

    def set_rgb_effect(self, effect, speed=5):
        """RGB 灯效: 0=关闭, 1=流水, 2=跑马, 3=呼吸, 4=渐变, 5=星光, 6=电量"""
        with self._lock:
            self._bot.set_colorful_effect(effect, speed)

    def set_rgb_led(self, led_id, r, g, b):
        """控制单颗 RGB 灯: led_id 0~13 或 0xFF=全部"""
        with self._lock:
            self._bot.set_colorful_lamps(led_id, r, g, b)

    # ==================== 生命周期 ====================

    def close(self):
        """关闭串口，释放资源"""
        if self._bot:
            with self._lock:
                try:
                    self._bot.set_car_motion(0, 0, 0)
                except Exception:
                    pass
            self._connected = False

    def __del__(self):
        self.close()
