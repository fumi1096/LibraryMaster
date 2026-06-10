#!/bin/bash
# ============================================================================
# mycar 数据链路诊断脚本 v2
# ============================================================================

source /opt/tros/humble/setup.bash 2>/dev/null
source /home/sunrise/project/LibraryMaster/mycar/install/setup.bash 2>/dev/null

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_topic() {
    local topic=$1
    local desc=$2
    if ros2 topic list 2>/dev/null | grep -q "$topic"; then
        local data=$(timeout 3 ros2 topic echo "$topic" --once 2>/dev/null | head -3)
        if [ -n "$data" ]; then
            echo -e "  ${GREEN}✅${NC} $desc ($topic)"
        else
            echo -e "  ${YELLOW}⚠️${NC}  $desc ($topic) — 无数据"
        fi
    else
        echo -e "  ${RED}❌${NC} $desc ($topic) — 不存在"
    fi
}

check_tf() {
    local from=$1
    local to=$2
    local desc=$3
    local out=$(timeout 2 ros2 run tf2_ros tf2_echo "$from" "$to" --once 2>&1)
    if echo "$out" | grep -q "Translation"; then
        echo -e "  ${GREEN}✅${NC} $desc ($from → $to)"
    elif echo "$out" | grep -q "waiting"; then
        echo -e "  ${YELLOW}⚠️${NC}  $desc ($from → $to) — 等待中"
    else
        echo -e "  ${RED}❌${NC} $desc ($from → $to) — 不可用"
    fi
}

echo "============================================"
echo "  mycar 数据链路诊断"
echo "============================================"
echo ""

# 1. 核心话题
echo "── 核心话题 ──"
check_topic "/cmd_vel"         "运动控制"
check_topic "/vel_raw"         "原始速度"
check_topic "/odom_raw"        "原始里程计"
check_topic "/odom"            "融合里程计 (EKF)"
check_topic "/imu/data_raw"    "IMU 原始数据"
check_topic "/imu/data"        "IMU 滤波后"
check_topic "/voltage"         "电池电压"
check_topic "/joint_states"    "关节状态"
echo ""

# 2. 相机管线
echo "── 相机管线 ──"
check_topic "/image_combine_raw"                          "双目原始图像"
check_topic "/StereoNetNode/stereonet_pointcloud2"        "双目点云"
check_topic "/scan"                                       "LaserScan"
echo ""

# 3. SLAM
echo "── SLAM ──"
check_topic "/map"              "地图"
echo ""

# 4. TF 树
echo "── TF 树 ──"
check_tf "odom" "base_footprint" "里程计 TF"
check_tf "base_footprint" "base_link" "URDF TF"
check_tf "base_link" "imu_Link" "IMU TF"
check_tf "base_link" "camera_Link" "相机 TF"
echo ""

# 5. 节点状态
echo "── 节点状态 ──"
for node in driver_node odom_node imu_filter ekf_se_odom slam_toolbox; do
    if ros2 node list 2>/dev/null | grep -q "$node"; then
        echo -e "  ${GREEN}✅${NC} $node"
    else
        echo -e "  ${YELLOW}⚠️${NC}  $node — 未运行"
    fi
done
echo ""

echo "============================================"
echo "  诊断完成"
echo "  ✅ = 正常  ⚠️ = 存在但无数据  ❌ = 缺失"
echo ""
echo "  常见问题排查:"
echo "  1. 点云/scan 无数据 → 检查相机是否连接、mipi_rotation 是否正确"
echo "  2. /odom 不存在 → EKF 未启动或 /odom_raw / /imu/data 缺失"
echo "  3. 模型不动 → TF odom→base_footprint 是否发布中"
echo "============================================"
