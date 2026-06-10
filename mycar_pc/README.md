# mycar_pc — PC 端分布式部署工作空间

## 概述

`mycar_pc` 是 mycar 小车系统的 **PC 端工作空间**，负责运行计算密集型节点和可视化：

- **2D 建图**：`slam_toolbox` (在线异步) + RViz2
- **3D 建图**：`RTAB-Map` (scan-to-scan ICP) + RViz2

所有硬件相关节点（驱动、IMU、EKF、相机、体素滤波）运行在小车端 (`mycar/`)。

## 分布式通信

使用 **Fast DDS Discovery Server** 作为 ROS2 分布式发现协议：

```bash
# 1. 在 PC 或小车上启动发现服务器
fastdds discovery --server-id 0

# 2. 所有节点配置连接（PC 和小车都需设置）
export ROS_DISCOVERY_SERVER=<服务器ip>:11811
```

## 目录结构

```
mycar_pc/
├── README.md
├── build.sh                    # colcon 构建
├── start_pc.sh                 # PC 端启动脚本
└── src/
    ├── mycar_slam/             # 2D SLAM (slam_toolbox 配置 + launch)
    ├── mycar_rtabmap/          # 3D SLAM (RTAB-Map 配置 + launch, 不含体素滤波)
    └── mycar_f/                # URDF 小车模型 (RViz RobotModel 显示用)
```

## 使用方法

### 1. 构建

```bash
cd mycar_pc
./build.sh
```

### 2. 启动发现服务器

```bash
fastdds discovery --server-id 0
```

### 3. 配置发现服务器地址

```bash
# 替换为实际 IP
export ROS_DISCOVERY_SERVER=<服务器ip>:11811
```

### 4. 启动小车端

在小车上：

```bash
# 2D 建图
./start_mycar.sh mapping_distributed

# 3D 建图
./start_mycar.sh mapping3d_distributed
```

### 5. 启动 PC 端

```bash
# 2D 建图
./start_pc.sh mapping2d

# 3D 建图
./start_pc.sh mapping3d
```

## 数据流

```
[小车端 RDK X5]                          [PC 端]
=================                        =========

MCU 驱动板
  ├→ /imu/data_raw, /vel_raw
  ├→ odom_node → /odom_raw
  └→ motion_controller ← /cmd_vel

EKF ← /odom_raw + /imu/data
  └→ /odom + TF (odom→base_footprint)

双目相机 (hobot_stereonet)
  ├→ 点云 (原始)
  ├→ pointcloud_to_laserscan → /scan ────→ slam_toolbox → /map
  └→ voxel_filter → /scan_cloud ────────→ RTAB-Map → 3D 地图

                                         RViz2 (可视化)
```

## 依赖

PC 端需要安装以下 ROS2 包：

```bash
sudo apt install ros-humble-slam-toolbox
sudo apt install ros-humble-rtabmap-ros
sudo apt install ros-humble-nav2-map-server
sudo apt install ros-humble-robot-localization
sudo apt install ros-humble-pointcloud-to-laserscan
```

## 保存建图结果

```bash
# 2D 地图
ros2 run nav2_map_server map_saver_cli -f ~/mycar_map

# 3D 数据库
ros2 service call /rtabmap/save_database rtabmap_msgs/srv/SaveDatabase
```
