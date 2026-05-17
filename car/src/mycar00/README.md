# mycar00 — 带摄像头绑定的四驱小车模型

mycar00 是在 mycar1 基础上修改的四驱小车 URDF 模型，新增了摄像头（camera_Link）的绑定。

---

## 与 mycar1 的差异

| 特性 | mycar1 | mycar00 |
|------|--------|---------|
| 摄像头 (camera_Link) | ❌ | ✅ 新增 |
| 虚拟地面 (base_footprint) | ✅ | ✅ |
| 四轮 (fl/fr/br/bl) | ✅ | ✅ |
| IMU (imu_Link) | ✅ | ✅ |

### 新增：camera_Link

- **link**: `camera_Link`，通过 `camera_joint`（fixed）固定在 `base_link` 上
- **位置**: `xyz="0.094 -0.032 0.044"`（相对 base_link）
- **网格文件**: `meshes/camera_Link.STL`

### 虚拟地面：base_footprint

通过 `base_joint`（fixed）将 `base_footprint` 作为 `base_link` 的父级，z 偏移 `0.066m`，用于 Gazebo 仿真中保持小车在地面上方。

---

## 文件结构

```
mycar00/
├── CMakeLists.txt
├── package.xml
├── config/
│   └── joint_names_mycar00.yaml
├── launch/
│   ├── display.launch    # RViz 可视化
│   └── gazebo.launch     # Gazebo 仿真
├── meshes/
│   ├── base_link.STL
│   ├── fl_Link.STL / fr_Link.STL
│   ├── bl_Link.STL / br_Link.STL
│   ├── imu_Link.STL
│   └── camera_Link.STL
├── textures/
└── urdf/
    ├── mycar00.csv
    └── mycar00.urdf
```

---

## 快速使用

```bash
cd /home/sunrise/project/LibraryMaster/car/src

source /opt/tros/humble/setup.bash
source ./install/setup.bash

# RViz 可视化
ros2 launch mycar00 display.launch

# Gazebo 仿真
ros2 launch mycar00 gazebo.launch
```

---

## 注意事项

驱动控制与 mycar1 相同，使用 `yahboomcar_bringup` 包的四驱驱动节点。
