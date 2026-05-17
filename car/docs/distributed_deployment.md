# mycar00 分布式 ROS2 部署文档

## 系统架构

```
┌── 嵌入式 (RDK X5) ─────────────────────┐      ┌── PC (笔记本) ──────────┐
│                                         │      │                         │
│  ┌─────────────────────────────────┐    │      │  建图阶段:               │
│  │ FourWD_driver (硬件驱动)        │    │      │  ┌─────────────────┐    │
│  │  ├─ /imu                        │    │      │  │ slam_toolbox    │    │
│  │  ├─ /joint_states               │    │      │  │ (online_async)  │    │
│  │  └─ sub /cmd_vel → 电机控制     │    │ WiFi │  └─────────────────┘    │
│  └─────────────────────────────────┘    │◄───►│  ┌─────────────────┐    │
│  ┌─────────────────────────────────┐    │      │  │ RViz2           │    │
│  │ base_node_fourwd (里程计)       │    │      │  │ (可视化建图)    │    │
│  │  └─ /odom_raw                   │    │      │  └─────────────────┘    │
│  └─────────────────────────────────┘    │      │  ┌─────────────────┐    │
│  ┌─────────────────────────────────┐    │      │  │ yahboom_keyboard│    │
│  │ StereoNet (双目深度)            │    │      │  │ (键盘遥控)      │    │
│  │  └─ /StereoNetNode/             │    │      │  └─────────────────┘    │
│  │     stereonet_pointcloud2       │    │      │                         │
│  └──────────────┬──────────────────┘    │      └─────────────────────────┘
│                 │                       │
│  ┌──────────────▼──────────────────┐    │
│  │ pointcloud_to_laserscan         │    │      ┌── PC 任务 ──────────────┐
│  │  └─ /scan                       │    │      │ ros2 launch mycar_slam  │
│  └─────────────────────────────────┘    │      │   slam_pc.launch.py     │
│  ┌─────────────────────────────────┐    │      │ 建图完成后:             │
│  │ robot_state_publisher (URDF TF) │    │      │ ros2 run nav2_map_server│
│  │ imu_filter_madgwick (IMU滤波)   │    │      │   map_saver_cli -f map  │
│  │ ekf_se_odom (EKF融合)           │    │      │ scp map.* sunrise@rdk:  │
│  │  └─ /odom, TF odom→base_fp      │    │      └─────────────────────────┘
│  └─────────────────────────────────┘    │
│                                         │      ┌── 嵌入式导航任务 ────────┐
│  建图完成后，嵌入式独立导航:            │      │ ./start_mycar00.sh       │
│  ┌─────────────────────────────────┐    │      │   navigate map.yaml     │
│  │ Nav2 导航栈:                     │    │      │ 在 RViz 中设 2D Nav    │
│  │  map_server (加载地图)           │    │      │   Goal → 自主到达      │
│  │  amcl (定位)                     │    │      └─────────────────────────┘
│  │  planner_server (全局规划)       │    │
│  │  controller_server (DWB控制)     │    │
│  │  bt_navigator (行为树)           │    │
│  │  lifecycle_manager              │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

---

## 1. 硬件准备

| 硬件 | 说明 |
|------|------|
| 嵌入式主板 | RDK X5，Ubuntu Server + TROS Humble |
| 驱动板 | Rosmaster 系列，串口通信 (`/dev/myserial`) |
| 双目相机 | 双目 MIPI 相机，StereoNet 深度算法 |
| 底盘 | 四驱差速轮，闭环电机 |
| 网络 | 嵌入式和 PC 连同一 WiFi |

---

## 2. 网络配置

两台机器的 `~/.bashrc` 添加：

```bash
# === 嵌入式 (RDK X5) ===
export ROS_DOMAIN_ID=42
# 如果 PC 的 hostname 不在 /etc/hosts，加：
# export ROS_IP=192.168.x.x

# === PC ===
export ROS_DOMAIN_ID=42
```

**验证连通性**：嵌入式启动后，PC 端执行：
```bash
ros2 topic list   # 应能看到 /scan, /odom, /imu, /cmd_vel 等话题
```

---

## 3. 软件依赖

```bash
# 嵌入式 & PC 都需安装
sudo apt install -y ros-humble-pointcloud-to-laserscan
sudo apt install -y ros-humble-navigation2 ros-humble-nav2-bringup

# 仅 PC
sudo apt install -y ros-humble-slam-toolbox
sudo apt install -y ros-humble-rviz2

# 嵌入式（如果还缺）
sudo apt install -y ros-humble-robot-localization ros-humble-imu-filter-madgwick
```

---

## 4. 文件结构

```
car/src/
├── yahboomcar_bringup/          # 硬件驱动、IMU 滤波、EKF 配置
│   ├── launch/
│   │   └── yahboomcar_bringup_mycar00_launch.py   # 核心启动（已改造）
│   └── param/
│       ├── imu_filter_param.yaml                   # IMU 滤波器参数
│       └── ekf_mycar00.yaml                        # EKF 融合参数（新增）
├── yahboomcar_base_node/        # 里程计 C++ 节点
├── yahboomcar_ctrl/             # 键盘/手柄遥控
├── mycar00/                     # 机器人 URDF 模型
├── launch/                      # 共享 launch 文件
│   └── camera_scan.launch.py    # 点云→LaserScan 管线（新增）
├── mycar_slam/                  # SLAM 建图包 — PC 端运行（新增）
│   ├── config/slam_toolbox_mapping.yaml
│   └── launch/slam_pc.launch.py
├── mycar_navigation/            # Nav2 导航包 — 嵌入式运行（新增）
│   ├── config/nav2_params.yaml
│   ├── launch/navigation_embedded.launch.py
│   └── maps/                    # 地图存放目录
├── start_mycar00.sh             # 统一启动脚本（已改造）
├── camera_start.sh              # 相机启动（已修正 frame_id）
└── start.sh                     # 单独运行 FourWD_driver
```

---

## 5. 操作流程

### 5.1 编译

```bash
cd car/src
source /opt/tros/humble/setup.bash
colcon build --packages-select mycar_slam mycar_navigation yahboomcar_bringup
source install/setup.bash
```

### 5.2 建图流程

**Step 1: 嵌入式启动核心节点**
```bash
# 嵌入式终端
cd ~/project/LibraryMaster/car/src
./start_mycar00.sh embedded
```
等待日志输出稳定（驱动、EKF、相机管线全部就绪）。

**Step 2: PC 端验证话题**
```bash
# PC 终端
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
ros2 topic list
# 应看到: /scan /odom /imu /cmd_vel /tf 等
```

**Step 3: PC 端启动建图**
```bash
# PC 终端（另开）
source /opt/ros/humble/setup.bash
cd ~/project/LibraryMaster/car/src
source install/setup.bash
ros2 launch mycar_slam slam_pc.launch.py
```
RViz 会自动打开，添加以下显示：
- `Map` 话题：`/map`
- `LaserScan` 话题：`/scan`
- `TF` 显示
- `RobotModel` 显示

**Step 4: 键盘遥控建图**
```bash
# PC 终端（另开）
ros2 run yahboomcar_ctrl yahboom_keyboard
```
按 `i` 前进、`j` 左转、`l` 右转、`,` 后退、`k` 停止。

走遍需要建图的区域后，保存地图：
```bash
# PC 终端
ros2 run nav2_map_server map_saver_cli -f ~/mycar_map
# 生成: ~/mycar_map.pgm + ~/mycar_map.yaml
```

**Step 5: 地图同步到嵌入式**
```bash
# PC 终端
scp ~/mycar_map.pgm ~/mycar_map.yaml sunrise@<rdk-ip>:~/project/LibraryMaster/car/src/mycar_navigation/maps/
```

### 5.3 自主导航流程

**Step 1: 嵌入式启动导航**
```bash
# 嵌入式终端
cd ~/project/LibraryMaster/car/src
./start_mycar00.sh navigate mycar_navigation/maps/mycar_map.yaml
```

**Step 2: PC 端 RViz 可视化（可选）**
```bash
# PC 终端
rviz2
```
在 RViz 中添加 Map、TF、LaserScan、RobotModel，订阅话题。

**Step 3: 设定导航目标**
- RViz 工具栏 → `2D Nav Goal`
- 在地图上点击目标位置并拖拽方向
- 小车自动规划路径并行驶到目标点

---

## 6. start_mycar00.sh 模式速查

| 命令 | 模式 | 启动内容 |
|------|------|----------|
| `./start_mycar00.sh` | embedded | 驱动 + 里程计 + IMU + 相机 + TF + EKF |
| `./start_mycar00.sh mapping` | 建图 | embedded + 键盘遥控 |
| `./start_mycar00.sh navigate <map.yaml>` | 导航 | embedded + Nav2 全栈 |
| `./start_mycar00.sh driver` | 调试 | 仅 FourWD_driver |

---

## 7. 关键话题速查

| 话题 | 类型 | 发布者 | 用途 |
|------|------|--------|------|
| `/scan` | LaserScan | pointcloud_to_laserscan | SLAM + AMCL 的激光输入 |
| `/odom` | Odometry | ekf_se_odom (EKF) | 融合里程计，SLAM/Nav2 使用 |
| `/odom_raw` | Odometry | base_node_fourwd | 原始车轮里程计 |
| `/imu/data` | Imu | imu_filter_madgwick | 滤波后 IMU |
| `/cmd_vel` | Twist | 键盘/手柄/Nav2 | 运动控制指令 |
| `/tf` | TF2 | robot_state_publisher + ekf | 坐标系变换 |
| `/map` | OccupancyGrid | slam_toolbox / map_server | 地图 |

---

## 8. TF 树

```
map ──→ odom ──→ base_footprint ──→ base_link ──→ camera_Link
         ↑EKF        ↑EKF            ↑URDF         ├── imu_Link
         │                           │             ├── fl_joint → fl_wheel
    /odom_raw                   robot_state_       ├── fr_joint → fr_wheel
    + /imu/data                 publisher          ├── br_joint → br_wheel
                                                   └── bl_joint → bl_wheel
```

- `map → odom`: slam_toolbox (建图时) / AMCL (导航时)
- `odom → base_footprint`: EKF
- `base_footprint → base_link`: URDF (固定变换)
- 其余: URDF 中定义

---

## 9. 故障排查

| 问题 | 检查方法 |
|------|----------|
| PC 看不到话题 | `ros2 topic list` 两面都跑；检查 `ROS_DOMAIN_ID` 一致；检查是否同一子网 |
| `/scan` 无数据 | 检查相机是否启动：`ros2 topic echo /StereoNetNode/stereonet_pointcloud2` |
| EKF 不发布 `/odom` | `ros2 topic echo /odom_raw` 和 `/imu/data` 必须有数据；检查 `ekf_mycar00.yaml` |
| AMCL 不收敛 | 调整 `alpha1~5` 噪声参数；确认 `robot_model_type: "differential"` |
| 导航规划失败 | 检查 costmap 是否看到障碍物；确认 `allow_unknown: true` |
| 驱动板通信失败 | 检查 `/dev/myserial` 是否存在；检查 udev 规则 |
