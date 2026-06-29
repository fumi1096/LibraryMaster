# mycar — 小车嵌入式端工作空间

## 项目概述

基于 RDK X5 的四驱差速轮小车 3D/2D 建图系统（嵌入式端）。

**硬件平台**: RDK X5 + Yahboom Rosmaster 驱动板 + 双目深度相机
**软件栈**: TROS Humble (ROS2) + Fast-DDS + hobot_stereonet BPU 推理
**新增**: Nav2 自主导航 (地图加载 + AMCL 定位 + 规划 + 控制)

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 系统 | TROS Humble (Ubuntu 22.04) | RDK X5 官方 ROS2 发行版 |
| 通信 | Fast-DDS Simple Discovery | ROS 2 默认 DDS，UDP 组播 |
| 跨机器 | OpenVPN + `ROS_DOMAIN_ID=42` | VPN 隧道透传 DDS 流量 |
| 相机 | hobot_stereonet V2.4_int16 | BPU 深度推理，双目立体匹配 |
| 驱动 | Rosmaster_Lib (串口) | MCU 编码器/IMU/电压 读写 |
| 定位 | robot_localization (EKF) | 编码器+IMU 融合 → `/odom` |
| 2D 建图 | slam_toolbox | 在线异步建图 (本地 RDK X5) |
| 3D 建图 | RTAB-Map | 3D RGB-D / ICP (PC端) |
| 导航 | Nav2 | 地图加载 + AMCL + 路径规划 + 控制 |

### 架构

```
[mycar — 小车端 RDK X5]                    [mycar_pc — PC 端]
                                      
┌─ mycar_driver ─────────────────────────┐       ┌─ mycar_rtabmap ───────────────┐
│ driver_node     串口→MCU               │       │                               │
│ sensor_publisher IMU/编码器            │       │  【2D 分布式】                 │
│ odom_node       速度积分               │  VPN  │  slam_toolbox                 │
│ ekf_se_odom     融合定位→/odom         │ ←───→ │    /scan + /odom → /map       │
│                                        │       │  RViz2: Map+Scan+TF+RobotModel│
│ hobot_stereonet 双目BPU推理            │       │                               │
│  → /rectify_left_image (bgr8)         │       │  【3D 分布式】                 │
│  → /stereonet_depth (mono16)          │       │  RTAB-Map RGB-D               │
│  → /stereonet_pointcloud2 (realtime)  │       │    ORB特征 + 深度投影          │
│                                        │       │    词袋回环 + ICP              │
│ pointcloud_republisher                │       │    → /cloud_map               │
│  时间戳 realtime→epoch                │       │    → /grid_map                │
│  绕 X 轴旋转 180° (倒置修正)          │       │    → /mapGraph                │
│  → /pointcloud_fixed (epoch)          │       └──────────────────────────────┘
│                                        │       ┌─ mycar_f ────────────────────┐
│ pointcloud_to_laserscan               │       │ robot_state_pub (URDF TF 树)  │
│  → /scan (LaserScan, 1°分辨率, 2Hz)   │       └──────────────────────────────┘
│                                        │       keyboard_control → /cmd_vel
│ image_republisher (3D 模式)           │
│  时间戳 + 编码修正 + JPEG压缩          │
│                                        │
│ mycar_slam (本地 2D, 仅 mapping 模式)  │
│  slam_toolbox: /scan + /odom → /map   │
└────────────────────────────────────────┘
```

### 包结构

| 包 | 类型 | 职责 |
|----|------|------|
| `mycar_driver` | Python | 驱动节点、里程计、点云修正、图像修正、键盘遥控 |
| `mycar_f` | CMake | SolidWorks URDF 模型 (7 links, STL meshes) |
| `mycar_slam` | CMake | slam_toolbox 2D 在线异步建图 (本地模式) |
| `mycar_rtabmap` | Python | RTAB-Map ICP 3D 建图 + 体素滤波 (本地模式) |
| `mycar_navigation` | CMake+Python | Nav2 自主导航 + 点位标记 + REST API |

### 启动模式

| 模式 | 命令 | 节点 |
|------|------|------|
| driver | `./start_mycar.sh driver` | 驱动 + 里程计 |
| embedded | `./start_mycar.sh embedded` | 驱动 + EKF + 相机 + LaserScan |
| **mapping** | `./start_mycar.sh mapping` | **embedded + slam_toolbox 2D** |
| mapping3d | `./start_mycar.sh mapping3d` | embedded + RTAB-Map ICP |
| mapping_distributed | `./start_mycar.sh mapping_distributed` | embedded (SLAM 在 PC) |
| mapping3d_distributed | `./start_mycar.sh mapping3d_distributed` | embedded + image_republisher (RGB-D 在 PC) |
| **navigate** | `./start_mycar.sh navigate` | **embedded + Nav2 导航** |
| **waypoint_navigation** | `./start_mycar.sh waypoint_navigation` | **navigate + 点位标记 + REST API** |

---

## 自主导航：基于已有地图

### 前提

已完成 2D 建图并保存地图到 `map/mycar_map.pgm` + `.yaml`。

### 导航管线

```
map_server (加载已有地图)
    │
    ▼
AMCL (蒙特卡洛定位, /scan + /odom + /map → 定位)
    │
    ▼
SmacPlanner2D (全局路径, /map + TF → /plan)
    │
    ▼
Pure Pursuit (路径跟随, /plan + TF → /cmd_vel)
    │
    ▼
driver_node → MCU → 电机
```

### 6 步快速上手

```bash
# 1. 启动导航 (小车端)
./start_mycar.sh waypoint_navigation /dev/ttyUSB0

# 2. PC 端远程监控
cd ../mycar_pc && ./start_pc.sh monitor

# 3. RViz: "2D Pose Estimate" → 标小车位置+朝向
# 4. RViz: "Nav2 Goal" → 点目标位置 → 观察绿色路径

# 5. 或通过 REST API 调用
curl -X POST http://localhost:5000/navigate \
  -H "Content-Type: application/json" \
  -d '{"x": 1.5, "y": 2.0, "yaw": 0.0}'
curl http://localhost:5000/status          # 查询状态
curl -X POST http://localhost:5000/cancel   # 取消导航
```

### 带宽优化

导航模式下点云降采样 8× 并关闭图像发布，DDS 带宽 ~40→~3 MB/s。

---

## 2D 建图：从摄像头到地图

### 数据转换链路

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 双目相机 (硬件)                                                   │
│    MIPI 双目摄像头, 640×352@30fps                                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ 左右目图像
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. hobot_stereonet V2.4_int16 (BPU 推理)                           │
│    算法: 双目立体匹配 (Stereo Matching)                              │
│    - 在 BPU (伯特处理器) 上运行深度神经网络推理                       │
│    - 输入: 左右目矫正图像                                            │
│    - 输出: 视差图 → 深度图 → 点云 (每个像素 (u,v) → 3D (x,y,z))     │
│                                                                     │
│    话题输出:                                                        │
│    /StereoNetNode/stereonet_pointcloud2  (PointCloud2, realtime时钟)│
│    /StereoNetNode/rectify_left_image      (bgr8, 矫正左图)          │
│    /StereoNetNode/stereonet_depth         (mono16, 深度图)          │
└────────────────────────────┬────────────────────────────────────────┘
                             │ 点云 frame_id=camera_Link, 倒置(相机倒装)
                             │ 时间戳=系统启动秒数(realtime, 与epoch不兼容)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. pointcloud_republisher (时间戳 + 旋转修正)                       │
│    算法: 直接内存变换 (numpy 向量化)                                 │
│    - 时间戳修正: realtime → ROS epoch (self.get_clock().now())      │
│    - 绕 X 轴旋转 180°: x→x, y→-y, z→-z (修正倒置安装)              │
│                                                                     │
│    话题输出:                                                        │
│    /pointcloud_republisher/pointcloud_fixed  (PointCloud2, epoch)   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ 正向点云, epoch时间戳
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. pointcloud_to_laserscan (3D→2D 降维)                            │
│    算法: 高度切片投影                                                │
│    - 按高度 [0.05m, 1.5m] 过滤点云 (去除地面和天花板)               │
│    - 将 3D 点云投影到水平面, 取每个角度扇区内最近点的距离            │
│    - 参数: ±90°范围, 1°分辨率(~181线), 2Hz, 0.1~5m测距              │
│                                                                     │
│    话题输出:                                                        │
│    /scan  (sensor_msgs/LaserScan, frame_id=base_footprint, epoch)   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ /scan + /odom + TF
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. slam_toolbox (online_async, Ceres Solver)                        │
│    算法: 扫描匹配 + 位姿图优化 + 回环检测                            │
│    - 扫描匹配: 将当前 /scan 与已有关键帧做 ICP 对齐                  │
│    - 关键帧: 移动 20cm 或旋转 0.1rad 时创建                          │
│    - 位姿图: Ceres 非线性优化, 融合里程计约束 + 扫描匹配约束         │
│    - 回环: 当前帧与历史帧搜索匹配, 检测到回环后全局优化               │
│                                                                     │
│    话题输出:                                                        │
│    /map           (nav_msgs/OccupancyGrid, 5cm分辨率栅格地图)       │
│    /map_metadata  (地图尺寸/原点等元信息)                            │
│    /tf (map→odom) (回环修正的全局位姿)                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 关键话题一览

| 话题 | 类型 | 时钟 | 说明 |
|------|------|:--:|------|
| `/StereoNetNode/stereonet_pointcloud2` | `PointCloud2` | realtime | BPU 双目深度原始点云 |
| `/pointcloud_republisher/pointcloud_fixed` | `PointCloud2` | epoch | 时间戳修正 + 旋转后的点云 |
| `/scan` | `LaserScan` | epoch | 2D 激光扫描 (1°分辨率) |
| `/odom` | `Odometry` | epoch | EKF 融合里程计 (编码器+IMU) |
| `/map` | `OccupancyGrid` | epoch | 2D 栅格建图结果 |

### 快速启动

```bash
# ===== 本地模式 (全部在 RDK X5 上运行) =====
# 2D 建图 (slam_toolbox + RViz2 都在小车上)
./start_mycar.sh mapping

# ===== 分布式模式 (推荐: 算力卸载到 PC) =====
# 2D 分布式建图 (小车端: 仅数据采集)
./start_mycar.sh mapping_distributed
# → PC 端: cd ../mycar_pc && ./start_pc.sh mapping2d

# 3D 分布式建图 (小车端: 数据采集 + 图像修正)
./start_mycar.sh mapping3d_distributed
# → PC 端: cd ../mycar_pc && ./start_pc.sh mapping3d_rgbd
```

---

## 保存地图

### 2D 建图 (slam_toolbox)

建图完成后，在 **PC 端**（分布式）或小车端（本地模式）执行：

```bash
# 保存栅格地图 (生成 mycar_map.pgm + mycar_map.yaml)
ros2 run nav2_map_server map_saver_cli -f ~/mycar_map

# 指定保存路径
ros2 run nav2_map_server map_saver_cli -f /path/to/my_map
```

保存后得到两个文件：
- `mycar_map.pgm` — 栅格地图图片 (0=空闲, 100=占据, 205=未知)
- `mycar_map.yaml` — 地图元信息 (分辨率、原点、阈值)

### 3D 建图 (RTAB-Map)

RTAB-Map 建图结束后数据库自动保存在 `~/.ros/rtabmap.db`。

```bash
# 查看 3D 地图
rtabmap-databaseViewer ~/.ros/rtabmap.db

# 导出 2D 栅格地图 (用于 Nav2 导航)
ros2 run nav2_map_server map_saver_cli -f ~/mycar_map
```

---

## 里程计标定

建图质量高度依赖里程计精度。如果发现直行或旋转漂移大，请先标定。

### 一键标定 / 验证

```bash
# 仅标定
./calibrate_odom.sh

# 仅验证（标定后检查效果）
./verify_odom.sh

# 标定 + 验证（一步完成）
./calibrate_and_verify.sh

# 指定串口
./calibrate_odom.sh /dev/ttyUSB1
./verify_odom.sh /dev/ttyUSB1
```

### 标定流程

1. 脚本自动编译、启动驱动 + 里程计
2. **直行标定（3次取平均）**：小车以 0.12m/s 前进 ~1m，你用量具实测距离后输入
3. **旋转标定（3次取平均）**：小车以 0.4rad/s 旋转 ~360°，你实测角度后输入
4. 自动将 `linear_scale` / `angular_scale` 写入 `src/mycar_driver/launch/driver.launch.py`
5. 重新编译后生效

### 标定验证

标定完成后，运行验证程序检查效果：

```bash
# 一键验证
./verify_odom.sh

# 或手动启动（两个终端）
ros2 launch mycar_driver driver.launch.py       # 终端1: 驱动
ros2 run mycar_driver verify_odom                # 终端2: 验证
```

验证程序自动执行前进 1m → 后退 1m → 旋转 360°，输出对比表格：

```
╔══════════════════════════════════════════════════════════════╗
║              里程计标定验证结果                             ║
╠══════════════╤══════════╤══════════╤══════════╤════════════╣
║  运动        │ 目标     │ 里程计   │ 误差     │ 状态       ║
╠══════════════╪══════════╪══════════╪══════════╪════════════╣
║ 前进 1m      │     1.0  │     1.0  │  +1.2%  │ ✓ 良好    ║
║ 后退 1m      │     1.0  │     1.0  │  -1.5%  │ ✓ 良好    ║
║ 旋转 360°    │   360.0  │   358.2  │  -0.5%  │ ✓ 良好    ║
╚══════════════╧══════════╧══════════╧══════════╧════════════╝
```

| 误差 | 状态 |
|:---|:---|
| < 2% | ✓ 良好 |
| 2% ~ 5% | ⚠ 一般，可重新标定 |
| > 5% | ✗ 需重新标定 |

### 标定原理

```
new_scale = old_scale × (实测距离 / 里程计距离)
```

里程计通过 `/vel_raw`（MCU 编码器上报的实际速度）积分得到位移。`linear_scale` / `angular_scale` 在积分前乘以速度值，用于补偿轮径、减速比等硬件差异。

### 可调参数（高级）

```bash
ros2 run mycar_driver calibrate_odom --ros-args \
  -p linear_distance:=1.0 \
  -p angular_degrees:=360.0 \
  -p trials:=5 \
  -p linear_speed:=0.12 \
  -p angular_speed:=0.4

ros2 run mycar_driver verify_odom --ros-args \
  -p linear_distance:=2.0 \
  -p angular_degrees:=180.0
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `linear_distance` | 1.0 | 直行距离 (m) |
| `linear_speed` | 0.12 | 直行速度 (m/s)，慢速减少打滑 |
| `angular_degrees` | 360.0 | 旋转角度 (°) |
| `angular_speed` | 0.4 | 旋转速度 (rad/s) |
| `trials` | 3 | 标定测试次数（取平均） |
