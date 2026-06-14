# mycar — 小车嵌入式端工作空间

## 项目概述

基于 RDK X5 的四驱差速轮小车 3D 建图系统（嵌入式端）。

**硬件平台**: RDK X5 + Yahboom Rosmaster 驱动板 + 双目深度相机
**软件栈**: TROS Humble (ROS2) + Fast-DDS + hobot_stereonet BPU 推理

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 系统 | TROS Humble (Ubuntu 22.04) | RDK X5 官方 ROS2 发行版 |
| 通信 | Fast-DDS Simple Discovery | ROS 2 默认 DDS，UDP 组播 |
| 跨机器 | OpenVPN + `ROS_DOMAIN_ID=42` | VPN 隧道透传 DDS 流量 |
| 相机 | hobot_stereonet V2.4_int16 | BPU 深度推理，双目立体匹配 |
| 驱动 | Rosmaster_Lib (串口) | MCU 编码器/IMU/电压 读写 |
| 定位 | robot_localization (EKF) | 编码器+IMU 融合 → `/odom` |
| 建图 | RTAB-Map / slam_toolbox | 3D RGB-D (PC端) / 2D (本地) |

### 架构

```
[mycar — 小车端 RDK X5]                    [mycar_pc — PC 端]
                                      
┌─ mycar_driver ─────────────────┐       ┌─ mycar_rtabmap ──────┐
│ driver_node     串口→MCU       │       │ RTAB-Map RGB-D       │
│ sensor_publisher IMU/编码器    │       │  ORB特征 + 深度投影   │
│ odom_node       速度积分       │  VPN  │  词袋回环 + ICP      │
│ ekf_se_odom     融合定位→/odom │ ←───→ │  → /cloud_map       │
│                                  │       │  → /grid_map        │
│ hobot_stereonet 双目BPU推理     │       │  → /mapGraph        │
│  → /rectify_left_image (bgr8)  │       └─────────────────────┘
│  → /stereonet_depth (mono16)   │       ┌─ mycar_f ───────────┐
│                                  │       │ robot_state_pub     │
│ image_republisher               │       │  (URDF TF 树)       │
│  时间戳 realtime→epoch          │       └─────────────────────┘
│  编码 mono16→16UC1              │       keyboard_control → /cmd_vel
│  P矩阵 从K填充                  │       RViz2 可视化
└─────────────────────────────────┘
```

### 包结构

| 包 | 类型 | 职责 |
|----|------|------|
| `mycar_driver` | Python | 驱动节点、里程计、图像/点云修正、键盘遥控 |
| `mycar_f` | CMake | SolidWorks URDF 模型 (7 links, STL meshes) |
| `mycar_slam` | CMake | slam_toolbox 2D 在线异步建图 (本地模式) |
| `mycar_rtabmap` | Python | RTAB-Map ICP 3D 建图 + 体素滤波 (本地模式) |

### 启动模式

| 模式 | 命令 | 节点 |
|------|------|------|
| driver | `./start_mycar.sh driver` | 驱动 + 里程计 |
| embedded | `./start_mycar.sh embedded` | 驱动 + EKF + 相机 + LaserScan |
| mapping | `./start_mycar.sh mapping` | embedded + slam_toolbox 2D |
| mapping3d | `./start_mycar.sh mapping3d` | embedded + RTAB-Map ICP |
| mapping_distributed | `./start_mycar.sh mapping_distributed` | embedded (SLAM 在 PC) |
| **mapping3d_distributed** | `./start_mycar.sh mapping3d_distributed` | embedded + image_republisher (RGB-D 在 PC) |

### 数据流 (分布式 RGB-D 模式)

```
双目相机 ──→ hobot_stereonet ──→ /rectify_left_image (bgr8, realtime)
           (BPU 深度推理)     ├─→ /stereonet_depth (mono16, realtime)
                              └─→ camera_info
                                        │
                              image_republisher
                              时间戳: realtime → epoch
                              编码:   mono16 → 16UC1
                              P矩阵:  K → 复制到 P
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
         /image_republisher   /image_republisher   /image_republisher
         /rgb_fixed           /depth_fixed         /rgb_camera_info_fixed
         (bgr8, epoch)        (16UC1 mm, epoch)    (CameraInfo)
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │  VPN
                                        ▼
                                   PC 端 RTAB-Map RGB-D
```

### 快速启动

```bash
# 小车端
./start_mycar.sh mapping3d_distributed

# PC 端 (另一台机器)
cd ../mycar_pc && ./start_pc.sh mapping3d_rgbd
```
