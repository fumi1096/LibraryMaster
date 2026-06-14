# mycar_pc — PC 端 RGB-D 3D 建图工作空间

## 项目概述

基于 RTAB-Map RGB-D 的 3D 视觉建图系统（PC 端），小车端通过 VPN 发布修正后的图像话题，PC 端消费数据完成建图。

**硬件要求**: x86 PC + NVIDIA GPU (推荐, RTAB-Map 特征提取)
**软件栈**: ROS2 Humble + Fast-DDS + RTAB-Map

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 系统 | ROS2 Humble (Ubuntu 22.04) | 标准 ROS2 发行版 |
| 通信 | Fast-DDS Simple Discovery | `ROS_DOMAIN_ID=42`, UDP 组播 |
| 网络 | OpenVPN | 跨机器 DDS 流量透传 |
| SLAM | RTAB-Map (rtabmap_slam) | RGB-D 模式: ORB视觉特征 + 词袋回环 + ICP |
| 可视化 | RViz2 | 预配置: MapCloud + MapGraph + Grid + RobotModel |

### 架构

```
[mycar — 小车端 RDK X5]                    [mycar_pc — PC 端]
                                      
image_republisher (小车端)                mycar_rtabmap
  ├─ /rgb_fixed (bgr8, epoch)  ─────────→ rgb/image
  ├─ /depth_fixed (16UC1, epoch) ───────→ depth/image
  └─ /rgb_camera_info_fixed ────────────→ rgb/camera_info
                                           depth/camera_info
EKF (小车端)                              
  └─ /odom ──────────────────────────────→ odom
                                      
                                        robot_state_publisher (mycar_f)
                                          └─ TF: camera_Link → base_footprint
                                      
                                        RTAB-Map RGB-D
                                          ├── ORB 视觉特征提取
                                          ├── 深度→3D 投影
                                          ├── 词袋回环检测
                                          └── ICP 位姿优化
                                              ↓
                                          /rtabmap/cloud_map
                                          /rtabmap/grid_map
                                          /rtabmap/mapGraph
                                        keyboard_control → /cmd_vel
                                        RViz2 可视化
```

### 包结构

| 包 | 类型 | 职责 |
|----|------|------|
| `mycar_rtabmap` | Python | RTAB-Map RGB-D launch + config + keyboard_control |
| `mycar_f` | CMake | URDF 模型副本 (robot_state_publisher TF 用) |

### 目录结构

```
mycar_pc/
├── build.sh                          # colcon 构建
├── start_pc.sh                       # 启动入口 (mapping3d_rgbd)
├── README.md
├── config/
│   └── fastdds.xml                   # Fast-DDS (禁用 SHM)
└── src/
    ├── mycar_rtabmap/
    │   ├── launch/
    │   │   └── rtabmap_rgbd_pc.launch.py
    │   ├── config/
    │   │   ├── rtabmap_rgbd.yaml
    │   │   └── rtabmap_mapping.rviz
    │   └── mycar_rtabmap/
    │       └── keyboard_control.py
    └── mycar_f/
        └── urdf/mycar_f.urdf
```

### 话题对接

| RTAB-Map 订阅 | 小车端话题 | 原始话题 | 类型 |
|--------------|-----------|---------|------|
| `rgb/image` | `/image_republisher/rgb_fixed` | `/StereoNetNode/rectify_left_image` | `Image(bgr8)` |
| `rgb/camera_info` | `/image_republisher/rgb_camera_info_fixed` | camera_info | `CameraInfo` |
| `depth/image` | `/image_republisher/depth_fixed` | `/StereoNetNode/stereonet_depth` | `Image(16UC1, mm)` |
| `depth/camera_info` | `/image_republisher/rgb_camera_info_fixed` | (共用RGB内参) | `CameraInfo` |
| `odom` | `/odom` | EKF 融合里程计 | `Odometry` |

### 快速启动

```bash
# 1. 构建
./build.sh

# 2. 确保小车端已启动
cd ../mycar && ./start_mycar.sh mapping3d_distributed

# 3. 启动 PC 端
./start_pc.sh mapping3d_rgbd
# 键盘遥控: i 前进, , 后退, j/l 转向, k 停止
# Ctrl+C 停止, 数据库自动保存
```

### 查看结果

```bash
# 3D 点云地图
rtabmap-databaseViewer ~/.ros/rtabmap.db

# 导出 2D 栅格地图 (Nav2 导航)
ros2 run nav2_map_server map_saver_cli -f ~/mycar_map
```

### 依赖

```bash
sudo apt install ros-humble-rtabmap-slam
```
