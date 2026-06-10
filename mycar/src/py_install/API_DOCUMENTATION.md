# Rosmaster_Lib 驱动库接口文档

> **版本**: V3.3.9  
> **作者**: Yahboom Team  
> **通信方式**: UART 串口 (115200 bps)  
> **适用平台**: RDK X3 / X3 Plus / X1 / R2 系列机器人小车  

---

## 目录

- [1. 概述](#1-概述)
- [2. 安装与导入](#2-安装与导入)
- [3. 通信协议说明](#3-通信协议说明)
- [4. 类与构造函数](#4-类与构造函数)
- [5. 系统与控制接口](#5-系统与控制接口)
- [6. 电机与运动控制接口](#6-电机与运动控制接口)
- [7. 舵机控制接口](#7-舵机控制接口)
- [8. RGB 灯带控制接口](#8-rgb-灯带控制接口)
- [9. 传感器数据读取接口](#9-传感器数据读取接口)
- [10. PID 参数接口](#10-pid-参数接口)
- [11. 阿克曼转向接口（R2 车型）](#11-阿克曼转向接口r2-车型)
- [12. 系统维护接口](#12-系统维护接口)
- [13. 小车类型常量](#13-小车类型常量)
- [14. 使用示例](#14-使用示例)

---

## 1. 概述

`Rosmaster_Lib` 是 Yahboom 团队为 Rosmaster 系列机器人小车开发的 Python 底层驱动库。通过串口与底层单片机（MCU）通信，实现对小车电机、舵机、传感器、RGB 灯带等外设的控制与数据读取。

**核心特性：**
- 串口通信，波特率 115200
- 自动数据上报机制（每 10ms 发送一包，4 种数据包轮流发送，每类数据 40ms 刷新一次）
- 支持多种车型（X3、X3 Plus、X1、R2）
- 完整的机械臂（6 路总线舵机）控制
- IMU 传感器数据读取（加速度计/陀螺仪/磁力计/姿态角）

---

## 2. 安装与导入

### 安装

```bash
cd py_install
sudo python3 setup.py install
```

### 导入

```python
from Rosmaster_Lib import Rosmaster
```

---

## 3. 通信协议说明

### 数据帧格式

| 字节位置 | 内容 | 说明 |
|:---:|:---|:---|
| 0 | `0xFF` | 帧头 |
| 1 | `0xFC` | 设备 ID |
| 2 | `len` | 数据长度（不含帧头和校验） |
| 3 | `func` | 功能码 |
| 4 ~ N-1 | `data` | 数据载荷 |
| N | `checksum` | 校验和（(sum + complement) % 256） |

### 自动上报机制

默认开启，MCU 自动上报 4 类数据包（轮询发送）：

| 功能码 | 数据内容 | 刷新周期 |
|:---:|:---|:---:|
| `0x0A` | 速度数据 (vx, vy, vz) + 电池电压 | 40ms |
| `0x0B` | MPU9250 原始数据（陀螺仪/加速度计/磁力计） | 40ms |
| `0x0C` | IMU 姿态角 (roll, pitch, yaw) | 40ms |
| `0x0D` | 四路电机编码器数据 | 40ms |

---

## 4. 类与构造函数

### `Rosmaster(car_type=1, com="/dev/myserial", delay=.002, debug=False)`

创建 Rosmaster 小车控制对象，初始化串口连接。

| 参数 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `car_type` | `int` | `1` | 小车类型，见[小车类型常量](#13-小车类型常量) |
| `com` | `str` | `"/dev/myserial"` | 串口设备路径，Linux 下如 `/dev/ttyUSB0`，Windows 下如 `COM30` |
| `delay` | `float` | `.002` | 命令发送后的延时（秒），防止单片机丢包 |
| `debug` | `bool` | `False` | 是否开启调试打印 |

**示例：**
```python
# Linux (RDK X5)
bot = Rosmaster(car_type=1, com="/dev/ttyUSB0", debug=True)

# Windows
bot = Rosmaster(car_type=1, com="COM30", debug=True)
```

> **注意**: 构造函数初始化时会自动打开机械臂扭矩力（`set_uart_servo_torque(1)`），避免 6 号舵机首次插上去读不到角度。

---

## 5. 系统与控制接口

### 5.1 `create_receive_threading()`

开启接收数据的后台线程。必须在读取传感器数据之前调用。

```python
bot.create_receive_threading()
```

| 参数 | 说明 |
|:---|:---|
| 无 | — |

---

### 5.2 `set_auto_report_state(enable, forever=False)`

设置单片机自动上报数据功能的开关。

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `enable` | `bool` | `True` 开启自动上报，`False` 关闭 |
| `forever` | `bool` | `True` 永久保存到 Flash，`False` 临时生效（重启后恢复默认） |

```python
bot.set_auto_report_state(False)  # 临时关闭自动上报
```

> **注意**: 关闭自动上报会影响部分读取数据功能。

---

### 5.3 `set_beep(on_time)`

控制蜂鸣器鸣响。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `on_time` | `int` | `0`：关闭 / `1`：持续响 / `>=10`：响 xx ms（10 的倍数） | 鸣响时长 |

```python
bot.set_beep(50)    # 蜂鸣器响 50ms
bot.set_beep(0)     # 关闭蜂鸣器
```

---

### 5.4 `set_car_type(car_type)`

设置小车类型（永久保存到 Flash）。

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `car_type` | `int` | 见[小车类型常量](#13-小车类型常量) |

```python
bot.set_car_type(4)   # 设置为 R2 车型
```

---

## 6. 电机与运动控制接口

### 6.1 `set_motor(speed_1, speed_2, speed_3, speed_4)`

直接控制四路电机的 PWM 占空比（开环控制，不使用编码器）。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `speed_1` ~ `speed_4` | `int` | `[-100, 100]` | 四路电机速度，`127` 表示保持当前速度不变 |

```python
bot.set_motor(50, 50, 50, 50)   # 四个电机同时以 50% 速度正转
bot.set_motor(0, 0, 0, 0)       # 停止
```

---

### 6.2 `set_car_run(state, speed, adjust=False)`

控制小车运动方向。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `state` | `int` | `0`~`7` | 运动状态（见下表） |
| `speed` | `int` | `[-100, 100]` | 运动速度 |
| `adjust` | `bool` | — | 是否开启陀螺仪辅助方向（暂未开通） |

**`state` 运动状态表：**

| state | 动作 |
|:---:|:---|
| `0` | 停止 |
| `1` | 前进 |
| `2` | 后退 |
| `3` | 向左平移 |
| `4` | 向右平移 |
| `5` | 左旋 |
| `6` | 右旋 |
| `7` | 停车 |

```python
bot.set_car_run(1, 50)   # 以 50% 速度前进
bot.set_car_run(0, 0)    # 停止
```

---

### 6.3 `set_car_motion(v_x, v_y, v_z)`

小车运动控制（闭环控制，受 PID 参数影响）。

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `v_x` | `float` | X 轴线速度（m/s），范围取决于车型 |
| `v_y` | `float` | Y 轴线速度（m/s），范围取决于车型 |
| `v_z` | `float` | Z 轴角速度（rad/s），范围取决于车型 |

**各车型输入范围：**

| 车型 | `v_x` | `v_y` | `v_z` |
|:---|:---|:---|:---|
| X3 | `[-1.0, 1.0]` | `[-1.0, 1.0]` | `[-5, 5]` |
| X3 Plus | `[-0.7, 0.7]` | `[-0.7, 0.7]` | `[-3.2, 3.2]` |
| R2/R2L | `[-1.8, 1.8]` | `[-0.045, 0.045]` | `[-3, 3]` |

```python
bot.set_car_motion(0.5, 0, 0)    # 以 0.5 m/s 前进
bot.set_car_motion(0, 0, 0)      # 停止
```

---

## 7. 舵机控制接口

### 7.1 PWM 舵机（四路）

#### `set_pwm_servo(servo_id, angle)`

控制单路 PWM 舵机角度。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `servo_id` | `int` | `[1, 4]` | 舵机编号 |
| `angle` | `int` | `[0, 180]` | 目标角度（°） |

```python
bot.set_pwm_servo(1, 90)   # 1 号舵机转到 90°
```

#### `set_pwm_servo_all(angle_s1, angle_s2, angle_s3, angle_s4)`

同时控制四路 PWM 舵机。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `angle_s1` ~ `angle_s4` | `int` | `[0, 180]` 或 `255`（不修改） | 四路舵机角度 |

```python
bot.set_pwm_servo_all(90, 90, 90, 90)   # 四路同时转到 90°
```

---

### 7.2 总线舵机（机械臂，六路）

#### `set_uart_servo(servo_id, pulse_value, run_time=500)`

控制总线舵机位置脉冲。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `servo_id` | `int` | `[1, 255]`，`254`=全体 | 舵机 ID |
| `pulse_value` | `int` | `[96, 4000]` | 位置脉冲值 |
| `run_time` | `int` | `[0, 2000]` | 运行时间（ms），越小越快 |

---

#### `set_uart_servo_angle(s_id, s_angle, run_time=500)`

设置单个总线舵机角度（角度制，自动转换为脉冲）。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `s_id` | `int` | `[1, 6]` | 舵机编号 |
| `s_angle` | `int` | 1~4: `[0, 180]` / 5: `[0, 270]` / 6: `[0, 180]` | 目标角度 |
| `run_time` | `int` | `[0, 2000]` | 运行时间（ms） |

```python
bot.set_uart_servo_angle(1, 90, 500)    # 1 号舵机转到 90°
bot.set_uart_servo_angle(5, 180, 1000)  # 5 号舵机转到 180°（夹爪）
```

---

#### `set_uart_servo_angle_array(angle_s=[90,90,90,90,90,180], run_time=500)`

同时控制六路机械臂舵机。

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `angle_s` | `list[int]` (6 元素) | 六路舵机角度 `[s1, s2, s3, s4, s5, s6]` |
| `run_time` | `int` | 运行时间（ms） |

```python
bot.set_uart_servo_angle_array([90, 90, 90, 90, 180, 50], 800)
```

---

#### `set_uart_servo_id(servo_id)`

设置总线舵机的 ID 号（**谨慎使用！**）。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `servo_id` | `int` | `[1, 250]` | 新 ID |

> ⚠️ **警告**: 执行前请确保只连接了一个总线舵机，否则所有已连接舵机都会被设置为同一 ID。

---

#### `set_uart_servo_torque(enable)`

开关总线舵机扭矩力。

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `enable` | `int` | `0`：释放扭矩（可用手转动）/ `1`：锁定扭矩（不可手转，命令控制） |

```python
bot.set_uart_servo_torque(1)   # 锁定舵机
bot.set_uart_servo_torque(0)   # 释放舵机
```

---

#### `set_uart_servo_ctrl_enable(enable)`

设置机械臂控制开关。

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `enable` | `bool` | `True` 允许发送控制协议，`False` 禁止发送 |

---

#### `set_uart_servo_offset(servo_id)`

设置机械臂中位偏差（校准用）。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `servo_id` | `int` | `0`~`6` | `0`=全部恢复出厂默认值；`1`~`6`=对应舵机 |

**返回值**: `int` — 偏移状态

```python
state = bot.set_uart_servo_offset(6)   # 校准 6 号舵机
```

---

## 8. RGB 灯带控制接口

### 8.1 `set_colorful_lamps(led_id, red, green, blue)`

控制 RGB 可编程灯带。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `led_id` | `int` | `[0, 13]` 或 `0xFF` | `0`~`13`=单个灯；`0xFF`=所有灯 |
| `red` | `int` | `[0, 255]` | 红色分量 |
| `green` | `int` | `[0, 255]` | 绿色分量 |
| `blue` | `int` | `[0, 255]` | 蓝色分量 |

```python
bot.set_colorful_lamps(0, 255, 0, 0)        # 0 号灯亮红色
bot.set_colorful_lamps(0xFF, 0, 255, 0)     # 所有灯亮绿色
```

> **注意**: 使用前需要先停止 RGB 灯特效。

---

### 8.2 `set_colorful_effect(effect, speed=255, parm=255)`

控制 RGB 灯带特效。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `effect` | `int` | `[0, 6]` | 特效编号（见下表） |
| `speed` | `int` | `[1, 10]` | 速度，越小越快 |
| `parm` | `int` | — | 附加参数（呼吸灯效果下，`[0, 6]` 修改颜色） |

**特效编号表：**

| effect | 特效 |
|:---:|:---|
| `0` | 停止灯效 |
| `1` | 流水灯 |
| `2` | 跑马灯 |
| `3` | 呼吸灯 |
| `4` | 渐变灯 |
| `5` | 星光点点 |
| `6` | 电量显示 |

```python
bot.set_colorful_effect(3, 5)       # 呼吸灯，速度 5
bot.set_colorful_effect(0)          # 停止灯效
```

---

## 9. 传感器数据读取接口

> ⚠️ **前提**: 所有读取接口需要在调用 `create_receive_threading()` 之后使用。

### 9.1 `get_accelerometer_data()`

获取加速度计三轴数据。

**返回值**: `(ax, ay, az)` — 单位：m/s²

```python
ax, ay, az = bot.get_accelerometer_data()
```

---

### 9.2 `get_gyroscope_data()`

获取陀螺仪三轴数据。

**返回值**: `(gx, gy, gz)` — 单位：rad/s

```python
gx, gy, gz = bot.get_gyroscope_data()
```

---

### 9.3 `get_magnetometer_data()`

获取磁力计三轴数据。

**返回值**: `(mx, my, mz)` — 单位：原始值

```python
mx, my, mz = bot.get_magnetometer_data()
```

---

### 9.4 `get_imu_attitude_data(ToAngle=True)`

获取 IMU 姿态角。

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `ToAngle` | `bool` | `True` 返回角度制（°），`False` 返回弧度制（rad） |

**返回值**: `(roll, pitch, yaw)`

```python
roll, pitch, yaw = bot.get_imu_attitude_data()          # 角度制
roll, pitch, yaw = bot.get_imu_attitude_data(False)     # 弧度制
```

---

### 9.5 `get_motion_data()`

获取小车当前速度。

**返回值**: `(vx, vy, vz)` — 单位：m/s, rad/s

```python
vx, vy, vz = bot.get_motion_data()
```

---

### 9.6 `get_motor_encoder()`

获取四路电机编码器累计值。

**返回值**: `(m1, m2, m3, m4)` — 单位：编码器脉冲数

```python
m1, m2, m3, m4 = bot.get_motor_encoder()
```

---

### 9.7 `get_battery_voltage()`

获取电池电压。

**返回值**: `float` — 单位：V

```python
voltage = bot.get_battery_voltage()
```

---

### 9.8 `get_uart_servo_value(servo_id)`

读取总线舵机当前位置脉冲值。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `servo_id` | `int` | `[1, 250]` | 舵机 ID |

**返回值**: `(read_id, pulse_value)` — 失败返回 `(-1, -1)` 或 `(-2, -2)`

```python
sid, value = bot.get_uart_servo_value(1)
```

---

### 9.9 `get_uart_servo_angle(s_id)`

读取单个总线舵机角度。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `s_id` | `int` | `[1, 6]` | 舵机编号 |

**返回值**: `int` — 角度值（°），失败返回 `-1` 或 `-2`

```python
angle = bot.get_uart_servo_angle(1)
```

---

### 9.10 `get_uart_servo_angle_array()`

一次性读取全部六路机械臂舵机角度。

**返回值**: `list[int]` (6 元素) — `[s1, s2, s3, s4, s5, s6]`，读取失败的位置为 `-1`

```python
angles = bot.get_uart_servo_angle_array()
# angles = [90, 45, 120, 80, 180, 30]
```

---

### 9.11 `get_motion_pid()`

获取当前运动 PID 参数。

**返回值**: `[kp, ki, kd]` — 失败返回 `[-1, -1, -1]`

```python
kp, ki, kd = bot.get_motion_pid()
```

---

### 9.12 `get_car_type_from_machine()`

从底层单片机读取当前设置的小车类型。

**返回值**: `int` — 小车类型常量值，失败返回 `-1`

```python
car_type = bot.get_car_type_from_machine()
```

---

### 9.13 `get_version()`

获取底层单片机固件版本号。

**返回值**: `float` — 如 `1.1`，失败返回 `-1`

```python
version = bot.get_version()
print(f"Firmware version: V{version}")
```

---

### 9.14 `get_akm_default_angle()`

获取阿克曼小车前轮舵机默认角度。

**返回值**: `int` — 角度值（°），失败返回 `-1`

---

### 9.15 `clear_auto_report_data()`

清除本地缓存的自动上报数据（将传感器数据全部归零）。

```python
bot.clear_auto_report_data()
```

---

## 10. PID 参数接口

### `set_pid_param(kp, ki, kd, forever=False)`

设置运动 PID 参数，影响 `set_car_motion()` 的速度控制效果。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `kp` | `float` | `[0, 10.00]` | 比例系数 |
| `ki` | `float` | `[0, 10.00]` | 积分系数 |
| `kd` | `float` | `[0, 10.00]` | 微分系数 |
| `forever` | `bool` | — | `True` 永久保存到 Flash（耗时较长），`False` 临时生效 |

```python
bot.set_pid_param(0.5, 0.1, 0.3, forever=False)   # 临时设置 PID
bot.set_pid_param(0.5, 0.1, 0.3, forever=True)    # 永久保存 PID
```

---

## 11. 阿克曼转向接口（R2 车型）

### 11.1 `set_akm_default_angle(angle, forever=False)`

设置阿克曼小车前轮默认角度（舵机中位）。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `angle` | `int` | `[60, 120]` | 默认角度 |
| `forever` | `bool` | — | `True` 永久保存，`False` 临时生效 |

```python
bot.set_akm_default_angle(100, forever=True)
```

---

### 11.2 `set_akm_steering_angle(angle, ctrl_car=False)`

控制阿克曼小车相对于默认角度的转向角。

| 参数 | 类型 | 范围 | 说明 |
|:---|:---|:---|:---|
| `angle` | `int` | `[-45, 45]` | 转向角，左负右正 |
| `ctrl_car` | `bool` | — | `True` 同时控制电机速度以辅助转向 |

```python
bot.set_akm_steering_angle(30)           # 右转 30°
bot.set_akm_steering_angle(-20, True)    # 左转 20°并联动电机
```

---

## 12. 系统维护接口

### 12.1 `reset_flash_value()`

重置小车 Flash 保存的所有数据，恢复出厂默认值。

```python
bot.reset_flash_value()
```

---

### 12.2 `reset_car_state()`

重置小车状态：停车、关灯、关蜂鸣器。

```python
bot.reset_car_state()
```

---

## 13. 小车类型常量

| 常量 | 值 | 对应车型 |
|:---|:---:|:---|
| `bot.CARTYPE_X3` | `0x01` (1) | X3 |
| `bot.CARTYPE_X3_PLUS` | `0x02` (2) | X3 Plus |
| `bot.CARTYPE_X1` | `0x04` (4) | X1 |
| `bot.CARTYPE_R2` | `0x05` (5) | R2 |

---

## 14. 使用示例

### 完整示例：初始化 + 读取传感器 + 控制运动

```python
from Rosmaster_Lib import Rosmaster
import time

# 1. 初始化（Linux RDK X5）
bot = Rosmaster(car_type=1, com="/dev/ttyUSB0", debug=True)

# 2. 启动数据接收线程
bot.create_receive_threading()
time.sleep(0.1)

# 3. 蜂鸣器提示
bot.set_beep(50)

# 4. 读取固件版本
version = bot.get_version()
print(f"固件版本: V{version}")

# 5. 读取传感器数据
ax, ay, az = bot.get_accelerometer_data()
print(f"加速度计: ax={ax:.3f}, ay={ay:.3f}, az={az:.3f} (m/s²)")

roll, pitch, yaw = bot.get_imu_attitude_data()
print(f"姿态角: roll={roll:.2f}°, pitch={pitch:.2f}°, yaw={yaw:.2f}°")

voltage = bot.get_battery_voltage()
print(f"电池电压: {voltage:.1f}V")

# 6. 控制运动
bot.set_car_motion(0.3, 0, 0)    # 前进 0.3 m/s
time.sleep(2)
bot.set_car_motion(0, 0, 0)      # 停止

# 7. 控制机械臂
bot.set_uart_servo_angle_array([90, 60, 120, 80, 180, 50], 1000)

# 8. 读取机械臂角度
angles = bot.get_uart_servo_angle_array()
print(f"机械臂角度: {angles}")

# 9. RGB 灯效
bot.set_colorful_effect(3, 5)    # 呼吸灯

# 10. 清理
del bot
```

### 循环读取传感器数据

```python
try:
    while True:
        ax, ay, az = bot.get_accelerometer_data()
        gx, gy, gz = bot.get_gyroscope_data()
        vx, vy, vz = bot.get_motion_data()
        vol = bot.get_battery_voltage()
        
        print(f"速度: ({vx:.2f}, {vy:.2f}, {vz:.2f}) | 电量: {vol:.1f}V")
        time.sleep(0.1)
except KeyboardInterrupt:
    bot.set_car_motion(0, 0, 0)    # 安全停止
    print("程序退出")
```

---

> 📝 **文档版本**: 基于 Rosmaster_Lib V3.3.9 整理  
> 📅 **整理日期**: 2026-05-22
