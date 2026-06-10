# mycar — 小车 ROS2 工作空间

## 分布式部署

使用 Fast DDS Discovery Server 作为发现协议实现 ROS2 分布式部署。

### 架构

```
[小车端 RDK X5]              [PC 端]
├─ 驱动/IMU/EKF/相机          ├─ slam_toolbox (2D)
├─ pointcloud_to_laserscan    ├─ RTAB-Map (3D)
└─ voxel_filter (3D 模式)     └─ RViz2 (可视化)
```

### 启动步骤

```bash
# 1. 启动发现服务器 (PC 或小车上)
fastdds discovery --server-id 0

# 2. 两端都配置连接
export ROS_DISCOVERY_SERVER=<服务器ip>:11811

# 3. 启动小车端
./start_mycar.sh mapping_distributed       # 2D 建图
./start_mycar.sh mapping3d_distributed     # 3D 建图

# 4. 启动 PC 端
cd ../mycar_pc && ./start_pc.sh mapping2d  # 2D 建图 PC 端
cd ../mycar_pc && ./start_pc.sh mapping3d  # 3D 建图 PC 端
```

### 模式说明

| 模式 | 小车端启动 | PC 端启动 |
|------|-----------|----------|
| 2D 分布式建图 | `mapping_distributed` | `mapping2d` |
| 3D 分布式建图 | `mapping3d_distributed` | `mapping3d` |
