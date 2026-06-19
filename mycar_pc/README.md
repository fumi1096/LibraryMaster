# mycar_pc — PC 端 2D + 3D 建图工作空间

## 项目概述

分布式建图系统 PC 端：消费小车端通过 VPN 发布的传感器数据，完成 2D (slam_toolbox) 或 3D (RTAB-Map RGB-D) 建图与可视化。

**硬件要求**: x86 PC + NVIDIA GPU (推荐, RTAB-Map 特征提取)
**软件栈**: ROS2 Humble + Fast-DDS + RTAB-Map

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 系统 | ROS2 Humble (Ubuntu 22.04) | 标准 ROS2 发行版 |
| 通信 | Fast-DDS Simple Discovery | `ROS_DOMAIN_ID=42`, UDP 组播 |
| 网络 | OpenVPN | 跨机器 DDS 流量透传 |
| 2D SLAM | slam_toolbox (online_async) | 扫描匹配 + 位姿图优化 + 回环检测 |
| 3D SLAM | RTAB-Map (rtabmap_slam) | RGB-D 模式: ORB视觉特征 + 词袋回环 + ICP |
| 可视化 | RViz2 | 预配置: Map + LaserScan + TF + RobotModel |

### 架构

```
[mycar — 小车端 RDK X5]                    [mycar_pc — PC 端]

【2D 分布式】
bringup (小车端)
  ├─ /scan (LaserScan) ──────────────────→ slam_toolbox
  ├─ /odom (EKF) ────────────────────────→   ├── 扫描匹配
  └─ TF 树 ──────────────────────────────→   ├── 位姿图优化
                                              ├── 回环检测
                                              └── /map (OccupancyGrid)
                                           RViz2
                                             ├─ Map (/map)
                                             ├─ LaserScan (/scan)
                                             ├─ TF
                                             └─ RobotModel

【3D 分布式】
image_republisher (小车端)
  ├─ /rgb_fixed (bgr8, epoch)  ─────────→ image_relay → RTAB-Map RGB-D
  ├─ /depth_fixed (16UC1, epoch) ───────→                ├── ORB 特征提取
  └─ /rgb_camera_info_fixed ────────────→                ├── 深度→3D 投影
                                                          ├── 词袋回环检测
EKF (小车端)                                              └── ICP 位姿优化
  └─ /odom ─────────────────────────────→ odom                ↓
                                                         /rtabmap/cloud_map
                                        robot_state_publisher  /rtabmap/grid_map
                                          └─ TF: camera_Link → base_footprint  /rtabmap/mapGraph
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
├── start_pc.sh                       # 启动入口 (mapping2d / mapping3d_rgbd)
├── README.md
├── config/
│   └── fastdds.xml                   # Fast-DDS (禁用 SHM)
└── src/
    ├── mycar_rtabmap/
    │   ├── launch/
    │   │   ├── slam2d_pc.launch.py       # 2D slam_toolbox + RViz2
    │   │   └── rtabmap_rgbd_pc.launch.py # 3D RTAB-Map + RViz2
    │   ├── config/
    │   │   ├── slam_toolbox_mapping.yaml # slam_toolbox 参数
    │   │   ├── slam_mapping_pc.rviz      # 2D RViz 布局
    │   │   ├── rtabmap_rgbd.yaml         # RTAB-Map 参数
    │   │   └── rtabmap_mapping.rviz      # 3D RViz 布局
    │   └── mycar_rtabmap/
    │       ├── keyboard_control.py
    │       └── image_relay.py
    └── mycar_f/
        └── urdf/mycar_f.urdf
```

### 话题对接

#### 2D 建图

| slam_toolbox 订阅 | 小车端话题 | 类型 |
|------------------|-----------|------|
| `/scan` | `/scan` (pointcloud_to_laserscan) | `LaserScan` |
| `/odom` | `/odom` (EKF 融合) | `Odometry` |
| TF | `odom→base_footprint` (robot_state_publisher) | `TFMessage` |

#### 3D 建图

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

# ===== 2D 分布式建图 =====
# 小车端 (先启动)
cd ../mycar && ./start_mycar.sh mapping_distributed
# PC 端
cd ../mycar_pc && ./start_pc.sh mapping2d

# ===== 3D 分布式建图 =====
# 小车端 (先启动)
cd ../mycar && ./start_mycar.sh mapping3d_distributed
# (可选) 数据流测试
./test_3d_mapping.sh
# PC 端
cd ../mycar_pc && ./start_pc.sh mapping3d_rgbd

# 键盘遥控: i 前进, , 后退, j/l 转向, k 停止
# Ctrl+C 停止, 地图自动保存
```

---

## 数据流测试工具

`test_3d_mapping.py` / `test_3d_mapping.sh` 用于验证小车端→PC端建图数据是否正确传输。

### 一键测试（推荐）

```bash
./test_3d_mapping.sh
```

自动执行：重启 ROS2 daemon → 话题预检 → 逐个测试建图管线 → 汇总报告。

### 高级用法

```bash
# 指定测试模块
python3 test_3d_mapping.py --check rgb depth odom

# 输出 JSON 报告
python3 test_3d_mapping.py --json

# 指定报告路径
python3 test_3d_mapping.py --json /tmp/report.json

# 查看帮助
python3 test_3d_mapping.py --help
```

### 测试模块

| 模块 | 测试内容 | 测试项 |
|------|---------|:------:|
| `connectivity` | 话题发现、网络连通性 | 4 |
| `raw` | 原始 StereoNetNode 数据（camera_info + 点云） | 2 |
| `camera_info` | CameraInfo K矩阵、P矩阵、frame_id、时间戳 | 5 |
| `rgb` | RGB 编码、frame_id、分辨率、时间戳、像素完整性 | 6 |
| `depth` | 深度编码、frame_id、时间戳、有效深度比例 | 5 |
| `odom` | 里程计 frame_id、2D 模式验证、时间戳、协方差 | 5 |
| `tf` | TF 树: odom→base_footprint, base_footprint→camera_Link | 2 |

### 退出码

- `0`: 全部通过，可以启动建图
- `1`: 存在失败项，检查红色标记

### 测试流程

```bash
# 1. 车端启动
cd ../mycar && ./start_mycar.sh mapping3d_distributed

# 2. 等待节点就绪 (约 5-10s)
# 3. PC 端测试
cd ../mycar_pc && ./test_3d_mapping.sh

# 4. 确认全部通过后启动建图
./start_pc.sh mapping3d_rgbd
```

### 并行订阅机制

测试工具使用**一次性并行订阅**所有话题，而非逐个顺序订阅，确保不丢失消息。

```
旧版 (顺序):  订阅RGB → 等15s → 订阅深度 → 等15s → 订阅odom
              ↑ 深度消息在等RGB时已被丢弃！

新版 (并行):  同时订阅RGB+深度+odom → 等所有消息到达 → 统一分析
              所有话题并行接收，无消息窗口丢失
```

如果大话题（RGB/深度）超时，工具会自动用 **BEST_EFFORT QoS**（避免 RELIABLE 重传拥塞）重试一次。若仍然超时，一般说明当前 VPN 网络状况不佳，可以稍后重试。小话题（CameraInfo、里程计）不受影响。

### 查看结果

#### 2D 地图

```bash
# 保存栅格地图 (建图过程中或结束后)
ros2 run nav2_map_server map_saver_cli -f ~/mycar_map
# 生成: mycar_map.pgm (图片) + mycar_map.yaml (元信息)
```

#### 3D 地图

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
