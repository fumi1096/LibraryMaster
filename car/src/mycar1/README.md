# mycar1 - 四驱普通轮小车 ROS2 控制系统

mycar1 是一个四轮独立驱动、**差速转向**的普通轮小车，使用 Yahboom 提供的驱动板（`Rosmaster_Lib`）与硬件通信。
本工程基于 yahboomcar 系列 ROS2 驱动框架，针对四驱普通轮进行了适配。

---

## 📋 目录

- [快速启动](#-快速启动)
- [系统架构](#-系统架构)
- [运动学原理](#-运动学原理)
- [文件说明](#-文件说明)
- [节点详解](#-节点详解)
- [测试指南](#-测试指南)
- [校准方法](#-校准方法)
- [参数配置](#-参数配置)
- [话题列表](#-话题列表)
- [常见问题](#-常见问题)

---

## 🚀 快速启动

```bash
# 1. 进入工程目录
cd /home/sunrise/project/LibraryMaster/car/src

# 2. 加载环境
source /opt/tros/humble/setup.bash
source ./install/setup.bash

# 3. 启动驱动节点（硬件通信+传感器采集）
ros2 run yahboomcar_bringup FourWD_driver

# 4. 新终端 - 运行测试
ros2 run yahboomcar_bringup simple_test
```

### 启动脚本

```bash
./start_mycar1.sh               # 仅启动驱动节点
./start_mycar1.sh launch        # 启动完整系统（含里程计、URDF等）
./start_mycar1.sh rviz          # 启动驱动 + RViz 可视化
```

---

## 🔧 系统架构

```
用户输入 (导航/手柄)
    │
    │ cmd_vel (Twist: vx, angular)
    ▼
┌──────────────────────────────────────────────────────────────┐
│                    FourWD_driver (驱动节点)                    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ cmd_vel_callback():                                 │     │
│  │   vx = -msg.linear.x    ← 电机取反修正              │     │
│  │   vy = 0.0              ← 普通轮无横向速度           │     │
│  │   angular = msg.angular.z                           │     │
│  │   self.car.set_car_motion(vx, 0, angular)           │     │
│  │                          ↑                          │     │
│  │                    底层固件根据car_type=1(X3)        │     │
│  │                    执行差速映射                      │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  pub_data() 每0.1s：                                        │
│   ├─ vel_raw       → base_node_fourwd (里程计积分)           │
│   ├─ /imu/data_raw → IMU传感器数据                           │
│   ├─ /imu/mag      → 磁力计数据                              │
│   ├─ voltage       → 电池电压                                │
│   └─ joint_states  → RViz可视化                             │
└──────────────────────────────────────────────────────────────┘
        │                       ▲
        │ 串口(/dev/myserial)   │
        ▼                       │
┌───────────────────────────────┴──┐
│       驱动板 (Rosmaster固件)      │
│  car_type=1 (X3模式)             │
│  差速映射：                      │
│    左轮 = vx + angular           │
│    右轮 = vx - angular           │
│    后左 = vx + angular           │
│    后右 = vx - angular           │
└──────────────────────────────────┘
```

---

## 📐 运动学原理

### 差速驱动模型

mycar1 采用四轮差速驱动，通过左右两侧的轮速差来实现转向：

```
左轮速度 = vx + angular × (track_width / 2)
右轮速度 = vx - angular × (track_width / 2)
```

### ⚠️ 关键适配：car_type=1 (X3模式)

Rosmaster固件中**没有专门的四驱差速车型号**，已知型号：
- `1` = X3（麦克纳姆轮） ✅ 可用（vy=0时=差速驱动）
- `4` = X1
- `5` = R2（阿克曼转向）
- ~~`6` = 不存在 ❌ 会导致固件报错、蜂鸣器长鸣~~

**解决方案：** 使用 `car_type=1` (X3)，此时底层映射为：
```
麦克纳姆轮公式:            vy=0 时简化为:
左前 = vx + vy + angular   左前 = vx + angular  ← 标准差速 ✓
右前 = vx - vy - angular   右前 = vx - angular  ← 标准差速 ✓
左后 = vx - vy + angular   左后 = vx + angular  ← 标准差速 ✓
右后 = vx + vy - angular   右后 = vx - angular  ← 标准差速 ✓
```

**结论：** vy 始终为 0，X3模式完全等价于四轮差速驱动。

### 前进方向修正

由于电机接线方向与ROS标准相反，`cmd_vel_callback` 中对 vx 取反：
```python
vx = -msg.linear.x   # ROS正=前进 → 硬件正=后退 → 取反修正
```

### 角度计算公式

所有电机为**闭环控制**，角速度值被精确执行：

```
旋转角度(°) = angular.z(rad/s) × 时间(s) × (180/π)

常用值（推荐 angular_speed = π/2 = 1.57 rad/s）：
  90°  →  π/2 / (π/2) = 1.0 秒
  180° →  π / (π/2)   = 2.0 秒
  360° →  2π / (π/2)  = 4.0 秒
```

---

## 📁 文件说明

### mycar1 相关文件

| 文件 | 说明 |
|------|------|
| `mycar1/urdf/mycar1.urdf` | URDF 模型（含 base_footprint） |
| `mycar1/meshes/*.STL` | 3D 模型文件 |
| `mycar1/package.xml` | 描述包配置 |
| `mycar1/README.md` | **本文件** |

### 新建的节点文件

| 文件 | 入口命令 | 说明 |
|------|---------|------|
| `yahboomcar_bringup/.../FourWD_driver.py` | `ros2 run yahboomcar_bringup FourWD_driver` | **驱动节点** - 硬件通信、运动控制、传感器采集 |
| `yahboomcar_base_node/src/base_node_fourwd.cpp` | `ros2 run yahboomcar_base_node base_node_fourwd` | **里程计节点** - 速度积分、位姿估计、TF发布 |

### 新建的测试文件

| 文件 | 入口命令 | 说明 |
|------|---------|------|
| `yahboomcar_bringup/.../simple_test.py` | `ros2 run yahboomcar_bringup simple_test` | **交互菜单测试** - 快速/电机/方形/圆形 |
| `yahboomcar_bringup/.../test_FourWD.py` | `ros2 run yahboomcar_bringup test_FourWD` | **综合测试** - 7项自动化测试 |
| `yahboomcar_bringup/.../patrol_FourWD.py` | `ros2 run yahboomcar_bringup patrol_FourWD` | **自主巡逻** - 方形/8字/往返 |
| `yahboomcar_bringup/.../calibrate_linear_FourWD.py` | `ros2 run yahboomcar_bringup calibrate_linear_FourWD` | **线速度校准** - 独立运行 |
| `yahboomcar_bringup/.../calibrate_angular_FourWD.py` | `ros2 run yahboomcar_bringup calibrate_angular_FourWD` | **角速度校准** - 独立运行 |

### 新建的启动文件

| 文件 | 说明 |
|------|------|
| `yahboomcar_bringup/launch/...mycar1_launch.py` | mycar1 完整系统 launch |
| `start_mycar1.sh` | 启动脚本（driver/launch/rviz模式） |

### 复用的现有文件（无需修改）

| 文件 | 说明 |
|------|------|
| `Rosmaster_Lib` | 硬件抽象层，同一家驱动板，完全兼容 |
| `yahboomcar_bringup/setup.py` | 已包含 `FourWD_driver` 入口点 |
| `yahboomcar_base_node/CMakeLists.txt` | 已包含 `base_node_fourwd` 构建目标 |

### 编译方法

```bash
cd /home/sunrise/project/LibraryMaster/car/src
source /opt/tros/humble/setup.bash
source ./install/setup.bash
colcon build --packages-select yahboomcar_bringup yahboomcar_base_node
source ./install/setup.bash
```

---

## 🧩 节点详解

### FourWD_driver (驱动节点)

**核心功能：** 与 Rosmaster 驱动板通过串口通信，实现运动控制和传感器数据采集。

#### 初始化流程

```
1. Rosmaster(串口初始化)
2. set_car_type(1)  ← 使用X3模式
3. 声明参数（车型、速度限制等）
4. 创建订阅器（cmd_vel, RGBLight, Buzzer）
5. 创建发布器（vel_raw, imu, mag, voltage等）
6. create_receive_threading()
7. 读取版本号 + 电池电压（诊断串口通信）
8. set_beep(0) × 3（关闭蜂鸣器）
```

#### cmd_vel 回调处理

```python
def cmd_vel_callback(self, msg):
    vx = -msg.linear.x     # 电机方向修正
    vy = 0.0               # 普通轮无横向速度
    angular = msg.angular.z
    # 速度限幅
    vx = clamp(vx, -xlinear_limit, xlinear_limit)
    angular = clamp(angular, -angular_limit, angular_limit)
    # 下发运动指令
    self.car.set_car_motion(vx, vy, angular)
```

#### 传感器数据发布 (10Hz)

| 数据来源 | 发布话题 | 说明 |
|---------|---------|------|
| `get_motion_data()` | `vel_raw` | 当前速度（vx, vy, angular） |
| `get_accelerometer_data()` | `/imu/data_raw` | 加速度 |
| `get_gyroscope_data()` | `/imu/data_raw` | 角速度 |
| `get_magnetometer_data()` | `/imu/mag` | 磁场强度 |
| `get_battery_voltage()` | `voltage` | 电池电压 |
| `get_version()` | `edition` | 驱动板版本 |

### base_node_fourwd (里程计节点)

**核心功能：** 订阅 `vel_raw`，积分计算里程计位姿。

**运动学积分公式：**
```
delta_heading = angular_z × dt
delta_x = (vx × cos(heading) - vy × sin(heading)) × dt
delta_y = (vx × sin(heading) + vy × cos(heading)) × dt
# 四驱差速：vy = 0，简化为：
delta_x = vx × cos(heading) × dt
delta_y = vx × sin(heading) × dt
```

**发布：** `/odom_raw` + TF `odom → base_footprint`

---

## 🧪 测试指南

### simple_test - 交互菜单测试（推荐）

```bash
ros2 run yahboomcar_bringup simple_test
```

菜单选项：
```
1. 快速测试     - 前进1s → 后退1s → 左转90° → 右转90°
2. 完整电机测试  - 各方向2s测试
3. 方形路径测试  - 走正方形（4×前进+左转90°）
4. 圆形路径测试  - 画圆8秒
```

### test_FourWD - 综合自动化测试

```bash
ros2 run yahboomcar_bringup test_FourWD
```

7项测试：前进、后退、顺/逆时针旋转、左/右弧线、速度变化

### patrol_FourWD - 自主巡逻

```bash
ros2 run yahboomcar_bringup patrol_FourWD
```

4种巡逻模式：方形(1圈/3圈)、直线往返、8字形

### 启动顺序

```
终端1: FourWD_driver (必需)
终端2: base_node_fourwd (可选，需要里程计时)
终端3: simple_test / test_FourWD / patrol_FourWD
```

---

## 📏 校准方法

### 角速度校准

由于是闭环电机，理论上是精确的，如果实测有偏差：

```bash
ros2 run yahboomcar_bringup calibrate_angular_FourWD
```

程序会让小车旋转90°，您输入实际角度，程序计算修正系数。

### 线速度校准

如果里程计显示距离与实际不符：

```bash
ros2 run yahboomcar_bringup calibrate_linear_FourWD
```

程序让小车前进1米，您输入实际距离，程序计算 `linear_scale_x` 修正值。

校准后更新 `base_node_fourwd` 的参数：
```bash
ros2 run yahboomcar_base_node base_node_fourwd \
    --ros-args -p linear_scale_x:=1.05
```

---

## ⚙️ 参数配置

### FourWD_driver 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `car_type` | `FOURWD` | 车型标识（实际硬件使用X3=1模式） |
| `imu_link` | `imu_Link` | IMU坐标系名称（注意大写L，与URDF一致） |
| `Prefix` | `""` | 关节名前缀（多机器人用） |
| `xlinear_limit` | `1.0` | 最大前进速度 (m/s) |
| `ylinear_limit` | `0.0` | 最大横向速度（普通轮为0） |
| `angular_limit` | `3.0` | 最大旋转角速度 (rad/s) |

### base_node_fourwd 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `wheelbase` | `0.25` | 轴距 (m) |
| `linear_scale_x` | `1.0` | 前进速度比例因子（校准用） |
| `linear_scale_y` | `1.0` | 横向速度比例因子 |
| `pub_odom_tf` | `true` | 是否发布 odom→base_footprint TF |
| `odom_frame` | `odom` | 里程计坐标系 |
| `base_footprint_frame` | `base_footprint` | 机器基座坐标系 |

---

## 📌 话题列表

### 订阅话题

| 话题 | 类型 | 说明 |
|------|------|------|
| `cmd_vel` | `geometry_msgs/Twist` | 运动控制指令 |
| `RGBLight` | `std_msgs/Int32` | RGB灯效控制 |
| `Buzzer` | `std_msgs/Bool` | 蜂鸣器开关 |

### 发布话题

| 话题 | 类型 | 说明 | 频率 |
|------|------|------|------|
| `vel_raw` | `geometry_msgs/Twist` | 原始速度数据 | 10Hz |
| `/imu/data_raw` | `sensor_msgs/Imu` | IMU数据 | 10Hz |
| `/imu/mag` | `sensor_msgs/MagneticField` | 磁力计 | 10Hz |
| `/odom_raw` | `nav_msgs/Odometry` | 里程计 | 10Hz |
| `voltage` | `std_msgs/Float32` | 电池电压 | 10Hz |
| `edition` | `std_msgs/Float32` | 驱动版本 | 10Hz |
| `joint_states` | `sensor_msgs/JointState` | 关节状态 | 10Hz |

### TF树

```
odom
  └── base_footprint (里程计发布)
        └── base_link (URDF)
              ├── fl_Link (左前轮)
              ├── fr_Link (右前轮)
              ├── br_Link (右后轮)
              ├── bl_Link (左后轮)
              └── imu_Link (IMU)
```

---

## 🆚 与 X3（麦克纳姆轮）的关键区别

| 特性 | X3（麦克纳姆轮） | mycar1（普通轮） |
|------|-----------------|-----------------|
| **轮子类型** | 麦克纳姆轮（全向） | 普通轮（差速） |
| **car_type(实际)** | 1 | 1（使用X3模式，vy=0） |
| **横向移动(vy)** | ✅ 支持 | ❌ 不支持，强制为0 |
| **转向方式** | 全向平移+旋转 | 差速转向 |
| **关节数** | 6个（含转向机构） | 4个（纯驱动） |
| **关节名** | `back_right_joint`... | `fl_joint`, `fr_joint`, `br_joint`, `bl_joint` |

---

## 🐛 常见问题

### Q: 蜂鸣器一直叫

启动日志中可以看到提示。原因：`car_type=6` 固件不识别，已修复为 `car_type=1`。

如果还是叫，检查串口：
```bash
ls -l /dev/myserial           # 设备是否存在
sudo chmod 666 /dev/myserial  # 权限修复
```

### Q: 小车不动

```bash
# 检查串口
ls -l /dev/myserial
# 检查驱动节点日志
ros2 run yahboomcar_bringup FourWD_driver
# 应看到：版本号、电池电压、✅ 串口通信正常
# 检查cmd_vel是否发布
ros2 topic echo /cmd_vel
```

### Q: 前进后退方向反了

已修复：`FourWD_driver.py` 中 `vx = -msg.linear.x` 取反。

### Q: 转向角度不准

使用 `calibrate_angular_FourWD` 校准，或检查 `angular_speed` 设置：

```python
# 正确计算：90° = 1.57 rad/s × 1.0s
# 如果转多了，减小 angular_limit
```

### Q: 里程计不准

```bash
# 校准线性速度比例因子
ros2 run yahboomcar_bringup calibrate_linear_FourWD

# 重新启动里程计节点，传入校准值
ros2 run yahboomcar_base_node base_node_fourwd \
    --ros-args -p linear_scale_x:=1.05
```

### Q: RViz 中轮子不转

确认 `joint_states` 话题有数据，且 URDF 中的关节名与驱动节点一致：
```
URDF: fl_joint, fr_joint, br_joint, bl_joint
驱动: state.name = ["fl_joint", "fr_joint", "br_joint", "bl_joint"]
```

### Q: 编译报错 `test_odom.cpp` 缺失

已修复：在 `CMakeLists.txt` 中注释掉了缺失的 `test_odom.cpp`。

---

## 📐 URDF 模型参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 轮子半径 | 34.5 mm | 0.0345 m |
| 轮子中心高度 | -0.0315 m | 相对 base_link |
| base_footprint z | 0.066 m | 地面到 base_link |
| 轴距 (前后轮) | ≈160 mm | |
| 轮距 (左右轮) | ≈172 mm | |
| IMU 位置 | (-0.017, 0.029, 0.011) | 相对 base_link |

---

## 📝 修改历史

| 日期 | 修改内容 |
|------|---------|
| 2026-05-06 | 初始创建 FourWD_driver 和相关测试文件 |
| 2026-05-06 | 修复 car_type=6→1（固件不识别导致蜂鸣器长鸣） |
| 2026-05-06 | 修复前进后退方向（vx取反） |
| 2026-05-06 | 修正角度计算（闭环电机精确执行，使用 π/2=1.57 rad/s） |
| 2026-05-06 | 添加串口通信诊断（启动时打印版本号和电池电压） |
| 2026-05-06 | 更新 test_odom.cpp 缺失修复（CMakeLists.txt注释掉） |
