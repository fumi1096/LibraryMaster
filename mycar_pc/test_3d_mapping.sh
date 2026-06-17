#!/bin/bash
# ============================================================================
# test_3d_mapping.sh — 分布式3D建图数据流测试 (一键启动)
# ============================================================================
# 用法:
#   ./test_3d_mapping.sh            # 完整测试
#   ./test_3d_mapping.sh --check rgb depth   # 仅测试RGB+深度
#   ./test_3d_mapping.sh --json     # 输出JSON报告
#   ./test_3d_mapping.sh --help     # 查看帮助
#
# 前置条件:
#   车端已启动: ./start_mycar.sh mapping3d_distributed
#   VPN 已连接
# ============================================================================

SCRIPT_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" &> /dev/null && pwd)

echo ""
echo "============================================"
echo "  分布式3D建图 — 数据流测试"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# 1. 清理 ROS2 daemon 缓存，确保新诊断不被旧状态干扰
echo "🔄 清理 ROS2 daemon..."
ros2 daemon stop 2>/dev/null
sleep 1
ros2 daemon start 2>/dev/null
sleep 5
echo "✅ daemon 已重启"
echo ""

# 2. 快速检查话题发现
echo "🔄 检查话题发现..."
TOPIC_COUNT=$(ros2 topic list 2>/dev/null | wc -l)
echo "   共发现 $TOPIC_COUNT 个话题"

# 检查关键话题
MISSING=0
for t in /image_republisher/rgb_fixed \
         /image_republisher/rgb_fixed/compressed \
         /image_republisher/depth_fixed \
         /image_republisher/depth_fixed/compressedDepth \
         /image_republisher/rgb_camera_info_fixed \
         /odom /tf; do
    if ros2 topic list 2>/dev/null | grep -q "$t"; then
        echo "   ✅ $t"
    else
        echo "   ❌ $t  (缺失)"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -gt 0 ]; then
    echo ""
    echo "⚠️  有 $MISSING 个关键话题缺失，可能影响建图"
    echo "   请确认车端已启动: ./start_mycar.sh mapping3d_distributed"
    echo "   以及 VPN 已连接"
fi
echo ""

# 3. 运行 Python 诊断
echo "🔄 运行数据流测试..."
echo ""
python3 "$SCRIPT_DIR/test_3d_mapping.py" "$@"
EXIT_CODE=$?

# 4. 退出
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 所有测试通过！可以启动建图: ./start_pc.sh mapping3d_rgbd"
else
    echo "❌ 存在失败项，请检查上方红色标记"
fi

exit $EXIT_CODE
