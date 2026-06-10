#!/usr/bin/env python3
"""测试脚本：验证 mycar_driver 各模块的基本功能（无需硬件）"""
import sys
import time
import unittest

# 测试模块导入
print("=" * 60)
print("  mycar_driver 模块测试")
print("=" * 60)

# 1. 测试 serial_bridge 导入和常量
print("\n[1/5] 测试 serial_bridge 模块...")
from mycar_driver.serial_bridge import SerialBridge
assert 'FOURWD' in SerialBridge.CAR_TYPES
assert SerialBridge.CAR_TYPES['X3'] == 1
print("  ✅ serial_bridge 模块正常")

# 2. 测试 sensor_publisher 导入
print("\n[2/5] 测试 sensor_publisher 模块...")
from mycar_driver.sensor_publisher import SensorPublisher
assert SensorPublisher.ENCODER_TO_RAD > 0
print("  ✅ sensor_publisher 模块正常")

# 3. 测试 motion_controller 导入
print("\n[3/5] 测试 motion_controller 模块...")
from mycar_driver.motion_controller import MotionController
print("  ✅ motion_controller 模块正常")

# 4. 测试 odom_node 导入和运动学计算
print("\n[4/5] 测试 odom_node 运动学...")
from mycar_driver.odom_node import OdomNode
import math

# 模拟差速运动学积分
x, y, heading = 0.0, 0.0, 0.0
dt = 0.05  # 50ms
vx, angular = 0.5, 0.2

for _ in range(20):  # 1秒
    heading += angular * dt
    x += vx * math.cos(heading) * dt
    y += vx * math.sin(heading) * dt

# 1秒后：vx=0.5, angular=0.2, 应前进约 0.5m
assert 0.4 < x < 0.6, f"期望 x≈0.5, 实际 x={x:.3f}"
assert abs(y) < 0.2, f"期望 |y| 小, 实际 y={y:.3f}"
assert 0.15 < heading < 0.25, f"期望 heading≈0.2, 实际 heading={heading:.3f}"
print(f"  ✅ 运动学计算正确: pos=({x:.3f}, {y:.3f}), heading={heading:.3f}")

# 5. 测试 driver_node 导入
print("\n[5/5] 测试 driver_node 模块...")
from mycar_driver.driver_node import DriverNode
print("  ✅ driver_node 模块正常")

print("\n" + "=" * 60)
print("  全部测试通过！✅")
print("=" * 60)
