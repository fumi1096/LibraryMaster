#!/usr/bin/env python3
"""
test_3d_mapping.py — 分布式3D建图数据流测试工具
=================================================
在 PC 端运行，自动检查车端所有建图核心话题的数据格式、传输质量。

用法:
  python3 test_3d_mapping.py              # 执行全部测试
  python3 test_3d_mapping.py --check rgb  # 仅测试 RGB 管线
  python3 test_3d_mapping.py --json       # 输出 JSON 报告
  python3 test_3d_mapping.py --help       # 查看所有选项

退出码: 0=全部通过, 1=有失败项

依赖:
  pip install numpy
"""

import argparse
import json
import sys
import time
import os
from datetime import datetime

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, PointCloud2, CompressedImage
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
import numpy as np

# ─── 色彩输出 ────────────────────────────────────────────────────────────────
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def c(color, text):
    if not sys.stdout.isatty():
        return text
    return f'{color}{text}{Colors.END}'

def green(text): return c(Colors.GREEN, text)
def red(text): return c(Colors.RED, text)
def yellow(text): return c(Colors.YELLOW, text)
def cyan(text): return c(Colors.CYAN, text)
def bold(text): return c(Colors.BOLD, text)

# ─── 测试项 ───────────────────────────────────────────────────────────────────
class TestResult:
    """单个测试结果"""
    def __init__(self, module, name):
        self.module = module
        self.name = name
        self.passed = False
        self.detail = ''
        self.duration = 0.0

    def ok(self, detail=''):
        self.passed = True
        self.detail = detail
        return self

    def fail(self, detail=''):
        self.passed = False
        self.detail = detail
        return self

    def __repr__(self):
        icon = green('✅') if self.passed else red('❌')
        detail = f" | {self.detail}" if self.detail else ''
        return f"  {icon} [{self.module}] {self.name}{detail}"


class MappingTester(Node):
    """分布式3D建图数据流测试器"""

    def __init__(self, args):
        super().__init__('mapping_tester')
        self.args = args
        self.results = []

        # 并行收集的消息缓存 {topic: [msg, elapsed]}
        self._collected = {}
        # 所有订阅句柄，用于清理
        self._subscriptions = []

        self._start_time = time.time()

    # ─── 工具 ─────────────────────────────────────────────────────────────

    def section(self, title):
        n = len(title)
        self.get_logger().info('')
        self.get_logger().info(cyan(f'─── {bold(title)} ' + '─' * max(2, 60 - n - 4)))

    def test(self, module, name):
        """创建并返回一个新的测试项"""
        r = TestResult(module, name)
        self.results.append(r)
        return r

    # ─── 并行订阅收集 ─────────────────────────────────────────────────────

    def _subscribe_all(self, topic_list, timeout_total=20.0, best_effort=False):
        """一次性订阅所有需要的话题，并行收集消息"""
        topics = {}
        for name, topic, msg_type in topic_list:
            data = []
            if best_effort:
                from rclpy.qos import QoSProfile, ReliabilityPolicy
                qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
                sub = self.create_subscription(msg_type, topic, data.append, qos)
            else:
                sub = self.create_subscription(msg_type, topic, data.append, 10)
            self._subscriptions.append(sub)
            topics[topic] = data
            self.get_logger().info(f'   订阅 {topic} {"(BEST_EFFORT)" if best_effort else ""}...')

        # 并行等待：所有话题都收到消息或者超时
        self.get_logger().info(f'   等待消息 (最长 {timeout_total}s)...')
        start = time.time()
        remaining = set(topic for _, topic, _ in topic_list)
        while remaining and (time.time() - start) < timeout_total:
            rclpy.spin_once(self, timeout_sec=0.05)
            for topic in list(remaining):
                if topics[topic]:
                    elapsed = time.time() - start
                    self._collected[topic] = (topics[topic][0], elapsed)
                    self.get_logger().info(f'    ✅ {topic} 收到 ({elapsed:.1f}s)')
                    remaining.remove(topic)

        # 对超时的话题也记录
        for topic in remaining:
            elapsed = time.time() - start
            self._collected[topic] = (None, elapsed)
            self.get_logger().info(f'    ⏱️  {topic} 超时 ({elapsed:.1f}s)')

    def _get_msg(self, topic):
        """从收集结果中取消息"""
        if topic in self._collected:
            return self._collected[topic]
        return (None, 0.0)

    # ─── Phase 1: 基础连通性 ───────────────────────────────────────────────

    def phase1_connectivity(self):
        """Phase 1: 基础网络连通性"""
        self.section('Phase 1: 网络连通性')

        required_topics = [
            '/image_republisher/rgb_fixed',
            '/image_republisher/depth_fixed',
            '/image_republisher/rgb_camera_info_fixed',
            '/odom',
        ]

        # 用 ros2 topic list 获取话题列表
        import subprocess
        try:
            result = subprocess.run(
                ['ros2', 'topic', 'list'],
                capture_output=True, text=True, timeout=10.0
            )
            topics_on_network = set(result.stdout.strip().split('\n'))
        except Exception as e:
            topics_on_network = set()

        for topic in required_topics:
            exists = topic in topics_on_network
            r = self.test('P1', f'话题可达 {topic}')
            if exists:
                r.ok()
            else:
                r.fail(f'话题未出现在 ros2 topic list 中')

        # 额外报告话题总数
        self.get_logger().info(f'            网络中共 {len(topics_on_network)} 个话题')
        if len(topics_on_network) < 20:
            self.get_logger().info(yellow('            ⚠️ 话题数偏少，可能部分节点未启动'))

    # ─── Phase 2: RGB 图像 ────────────────────────────────────────────────

    def phase2_rgb(self):
        """Phase 2: RGB 图像管线"""
        self.section('Phase 2: RGB 图像管线')

        msg, elapsed = self._get_msg('/image_republisher/rgb_fixed')
        r = self.test('P2', '消息可达')
        if msg is None:
            r.fail(f'{elapsed:.1f}s超时')
            return
        r.ok(f'{elapsed:.1f}s')

        r = self.test('P2', f'编码 = {msg.encoding}')
        r.ok() if msg.encoding in ('bgr8', 'rgb8', 'mono8') \
            else r.fail(f'RTAB-Map 不识别 {msg.encoding}')

        r = self.test('P2', f'frame_id = {msg.header.frame_id}')
        r.ok() if msg.header.frame_id == 'camera_Link' \
            else r.fail('期望 camera_Link')

        r = self.test('P2', f'分辨率 = {msg.width}x{msg.height}')
        r.ok()

        epoch = msg.header.stamp.sec
        r = self.test('P2', f'时间戳 = {epoch}')
        r.ok('epoch Unix 时间') if epoch > 1000000000 \
            else r.fail('非 epoch，未修正')

        data = np.frombuffer(msg.data, dtype=np.uint8)
        nonzero = (data > 0).mean()
        r = self.test('P2', f'数据非零 {nonzero*100:.1f}%')
        r.ok(f'像素 [{data.min()}, {data.max()}]') if nonzero > 0.01 \
            else r.fail('图像全黑或全零')

    # ─── Phase 3: 深度图像 ────────────────────────────────────────────────

    def phase3_depth(self):
        """Phase 3: 深度图像管线"""
        self.section('Phase 3: 深度图像管线')

        msg, elapsed = self._get_msg('/image_republisher/depth_fixed')
        r = self.test('P3', '消息可达')
        if msg is None:
            r.fail(f'{elapsed:.1f}s超时')
            return
        r.ok(f'{elapsed:.1f}s')

        r = self.test('P3', f'编码 = {msg.encoding}')
        r.ok('RTAB-Map 原生格式') if msg.encoding == '16UC1' \
            else r.fail(f'需要 16UC1(mm)，收到 {msg.encoding}')

        r = self.test('P3', f'frame_id = {msg.header.frame_id}')
        r.ok() if msg.header.frame_id == 'camera_Link' else r.fail('期望 camera_Link')

        r = self.test('P3', f'时间戳 = {msg.header.stamp.sec}')
        r.ok() if msg.header.stamp.sec > 1000000000 else r.fail('非 epoch')

        data = np.frombuffer(msg.data, dtype=np.uint16)
        nonzero = data[data > 0]
        ratio = len(nonzero) / len(data) if len(data) > 0 else 0
        r = self.test('P3', f'有效深度 {len(nonzero)}/{len(data)} ({ratio*100:.1f}%)')
        if ratio > 0.05:
            in_range = ((nonzero >= 300) & (nonzero <= 5000)).mean()
            r.ok(f'{nonzero.min()}~{nonzero.max()}mm, 0.3-5.0m内 {in_range*100:.1f}%')
        else:
            r.fail('有效深度比例过低' if ratio > 0 else '深度图全零!')

    # ─── Phase 4: CameraInfo ──────────────────────────────────────────────

    def phase4_camera_info(self):
        """Phase 4: CameraInfo 管线"""
        self.section('Phase 4: CameraInfo 管线')

        msg, elapsed = self._get_msg('/image_republisher/rgb_camera_info_fixed')
        r = self.test('P4', '消息可达')
        if msg is None:
            r.fail(f'{elapsed:.1f}s超时')
            return
        r.ok(f'{elapsed:.1f}s')

        k, p = msg.k, msg.p
        r = self.test('P4', f'frame_id = {msg.header.frame_id}')
        r.ok() if msg.header.frame_id == 'camera_Link' else r.fail('期望 camera_Link')
        r = self.test('P4', f'时间戳 = {msg.header.stamp.sec}')
        r.ok() if msg.header.stamp.sec > 1000000000 else r.fail('非 epoch')
        r = self.test('P4', f'K [fx={k[0]:.1f} cx={k[2]:.1f} fy={k[4]:.1f} cy={k[5]:.1f}]')
        r.ok('内参合理') if k[0] > 100 and k[4] > 100 else r.fail('内参异常')
        r = self.test('P4', f'P [fx={p[0]:.1f} cx={p[2]:.1f} fy={p[5]:.1f} cy={p[6]:.1f}]')
        r.ok('depth→3D 投影可用') if p[0] > 0 else r.fail('P矩阵为空!')

    # ─── Phase 5: 里程计 ──────────────────────────────────────────────────

    def phase5_odom(self):
        """Phase 5: 里程计管线"""
        self.section('Phase 5: 里程计管线')

        msg, elapsed = self._get_msg('/odom')
        r = self.test('P5', '消息可达')
        if msg is None:
            r.fail(f'{elapsed:.1f}s超时')
            return
        r.ok(f'{elapsed:.1f}s')

        pose = msg.pose.pose
        twist = msg.twist.twist
        cov = msg.pose.covariance

        r = self.test('P5', f'frame_id={msg.header.frame_id} → {msg.child_frame_id}')
        r.ok() if msg.header.frame_id == 'odom' and msg.child_frame_id == 'base_footprint' \
            else r.fail('期望 odom → base_footprint')

        r = self.test('P5', f'位置 ({pose.position.x:.3f}, {pose.position.y:.3f}, z={pose.position.z:.3f})')
        r.ok() if abs(pose.position.z) < 0.01 else r.fail('z≠0, 非2D模式')

        r = self.test('P5', f'时间戳 = {msg.header.stamp.sec}')
        r.ok() if msg.header.stamp.sec > 1000000000 else r.fail('非 epoch')

        # 协方差诊断
        cov_ok = cov[0] < 1.0 and cov[7] < 1.0 and cov[35] < 1.0
        r = self.test('P5', f'协方差 [{cov[0]:.4f}, {cov[7]:.4f}, {cov[35]:.4f}]')
        if cov_ok:
            r.ok('里程计置信度正常')
        elif cov[0] > 1e6:
            r.fail(f'协方差极大 ({cov[0]:.2e})，EKF 未收敛或数值异常')
        else:
            r.ok('协方差偏高但可接受')

    # ─── Phase 6: TF 树 ───────────────────────────────────────────────────

    def phase6_tf(self):
        """Phase 6: TF 树诊断"""
        self.section('Phase 6: TF 树')

        from tf2_ros import Buffer, TransformListener

        tf_buffer = Buffer()
        tf_listener = TransformListener(tf_buffer, self)
        time.sleep(0.5)  # 等待 TF 缓存填充

        # odom → base_footprint
        r = self.test('P6', 'odom → base_footprint')
        try:
            t = tf_buffer.lookup_transform('odom', 'base_footprint', rclpy.time.Time())
            r.ok(f'平移 [{t.transform.translation.x:.3f}, {t.transform.translation.y:.3f}]')
        except Exception as e:
            r.fail(str(e)[:60])

        # base_footprint → camera_Link
        r = self.test('P6', 'base_footprint → camera_Link')
        try:
            t = tf_buffer.lookup_transform('base_footprint', 'camera_Link', rclpy.time.Time())
            x, y, z = t.transform.translation.x, t.transform.translation.y, t.transform.translation.z
            r.ok(f'平移 [{x:.4f}, {y:.4f}, {z:.4f}]')
        except Exception as e:
            r.fail(str(e)[:60])

    # ─── 原始话题（补充诊断） ──────────────────────────────────────────────

    def phase_raw(self):
        """原始 StereoNetNode 话题补充诊断"""
        self.section('补充: 原始 StereoNetNode 诊断')

        msg, elapsed = self._get_msg('/StereoNetNode/rectify_left_image/camera_info')
        r = self.test('RAW', '原始 camera_info')
        if msg:
            is_boot = msg.header.stamp.sec < 1000000000
            r.ok(f't={msg.header.stamp.sec}s, {"boot时间需修正" if is_boot else "epoch"}' +
                 f' ({elapsed:.1f}s)')
        else:
            r.fail(f'{elapsed:.1f}s超时')

        msg, elapsed = self._get_msg('/StereoNetNode/stereonet_pointcloud2')
        r = self.test('RAW', '原始点云 stereonet_pointcloud2')
        if msg:
            r.ok(f'{msg.width}点, frame={msg.header.frame_id} ({elapsed:.1f}s)')
        else:
            r.fail(f'{elapsed:.1f}s超时')

    # ─── 压缩图像话题（VPN 带宽优化） ──────────────────────────────────────

    def phase_compressed(self):
        """Phase 7: 压缩图像话题"""
        self.section('Phase 7: 压缩图像话题 (VPN 带宽优化)')

        # --- 压缩 RGB ---
        msg, elapsed = self._get_msg('/image_republisher/rgb_fixed/compressed')
        r = self.test('P7', '压缩 RGB 可达')
        if msg is None:
            r.fail(f'{elapsed:.1f}s超时 (车端 opencv 未装?)')
        else:
            r.ok(f'{elapsed:.1f}s')

            r = self.test('P7', f'压缩格式 = {msg.format}')
            r.ok('JPEG 压缩') if msg.format in ('jpeg', 'jpg') \
                else r.fail(f'期望 jpeg, 收到 {msg.format}')

            r = self.test('P7', f'frame_id = {msg.header.frame_id}')
            r.ok() if msg.header.frame_id == 'camera_Link' \
                else r.fail('期望 camera_Link')

            size_kb = len(msg.data) / 1024
            r = self.test('P7', f'压缩大小 = {size_kb:.1f} KB')
            if size_kb > 0.1:
                r.ok(f'~{size_kb:.0f}KB (原始 640x352 bgr8 ≈ {640*352*3/1024:.0f}KB, '
                     f'压缩比 {640*352*3/1024/size_kb:.0f}:1)')
            else:
                r.fail('压缩数据过小/为空')

        # --- 压缩深度 ---
        msg, elapsed = self._get_msg('/image_republisher/depth_fixed/compressedDepth')
        r = self.test('P7', '压缩深度可达')
        if msg is None:
            r.fail(f'{elapsed:.1f}s超时 (车端 opencv 未装?)')
        else:
            r.ok(f'{elapsed:.1f}s')

            r = self.test('P7', f'压缩格式 = {msg.format}')
            r.ok('PNG 无损压缩') if msg.format == 'png' \
                else r.fail(f'期望 png, 收到 {msg.format}')

            r = self.test('P7', f'frame_id = {msg.header.frame_id}')
            r.ok() if msg.header.frame_id == 'camera_Link' \
                else r.fail('期望 camera_Link')

            size_kb = len(msg.data) / 1024
            r = self.test('P7', f'压缩大小 = {size_kb:.1f} KB')
            if size_kb > 0.1:
                r.ok(f'~{size_kb:.0f}KB (原始 640x352 16UC1 ≈ {640*352*2/1024:.0f}KB, '
                     f'压缩比 {640*352*2/1024/size_kb:.0f}:1)')
            else:
                r.fail('压缩数据过小/为空')

    # ─── 汇总 ──────────────────────────────────────────────────────────────

    def summary(self):
        """输出汇总报告"""
        elapsed = time.time() - self._start_time

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)

        self.get_logger().info('')
        self.get_logger().info('=' * 60)
        self.get_logger().info(bold('  📊 测试汇总'))
        self.get_logger().info('=' * 60)

        for r in self.results:
            self.get_logger().info(str(r))

        self.get_logger().info('')
        if failed == 0:
            self.get_logger().info(green(bold(f'  ✅ 全部 {passed} 项通过 ({elapsed:.1f}s)')))
        else:
            self.get_logger().info(red(bold(f'  ❌ {passed} 通过 / {failed} 失败 ({elapsed:.1f}s)')))
            # 检查是否图像话题超时
            img_fails = [r for r in self.results if not r.passed and
                         r.module in ('P2', 'P3') and '超时' in r.detail]
            if img_fails:
                self.get_logger().info(yellow('  💡 提示: 图像话题超时一般是网络抖动或 VPN 带宽不足导致的'))
                self.get_logger().info(yellow('     可以立即重试一次: python3 test_3d_mapping.py --check rgb depth'))
        self.get_logger().info('=' * 60)

        # JSON 报告
        if self.args.json:
            report = {
                'timestamp': datetime.now().isoformat(),
                'duration_sec': round(elapsed, 1),
                'passed': passed,
                'failed': failed,
                'results': [
                    {
                        'module': r.module,
                        'name': r.name,
                        'passed': r.passed,
                        'detail': r.detail,
                    }
                    for r in self.results
                ]
            }
            json_path = self.args.json if self.args.json != 'auto' \
                else f'report_3d_mapping_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(json_path, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.get_logger().info(f'报告已保存: {json_path}')

        # 退出码
        return 0 if failed == 0 else 1

    # ─── 主入口 ────────────────────────────────────────────────────────────

    def run(self):
        """执行所有启用的测试模块"""
        checks = self.args.check or [
            'raw', 'camera_info', 'rgb', 'depth', 'odom', 'tf', 'compressed'
        ]

        if 'connectivity' in checks:
            self.phase1_connectivity()

        # 需要并行订阅的话题列表 (name, topic, type)
        subscribe_list = []
        need_raw = 'raw' in checks
        need_cam = 'camera_info' in checks
        need_rgb = 'rgb' in checks
        need_depth = 'depth' in checks
        need_odom = 'odom' in checks

        if need_raw:
            subscribe_list += [
                ('RAW_cam_info', '/StereoNetNode/rectify_left_image/camera_info', CameraInfo),
                ('RAW_pointcloud', '/StereoNetNode/stereonet_pointcloud2', PointCloud2),
            ]
        if need_cam or need_rgb or need_depth:
            subscribe_list.append(
                ('cam_info', '/image_republisher/rgb_camera_info_fixed', CameraInfo))
        if need_rgb:
            subscribe_list.append(
                ('rgb', '/image_republisher/rgb_fixed', Image))
        if need_depth:
            subscribe_list.append(
                ('depth', '/image_republisher/depth_fixed', Image))
        if need_odom:
            subscribe_list.append(
                ('odom', '/odom', Odometry))

        need_compressed = 'compressed' in checks
        if need_compressed:
            subscribe_list += [
                ('rgb_compressed', '/image_republisher/rgb_fixed/compressed', CompressedImage),
                ('depth_compressed', '/image_republisher/depth_fixed/compressedDepth', CompressedImage),
            ]

        if subscribe_list:
            self.section('并行收集数据')
            self._subscribe_all(subscribe_list, timeout_total=self.args.timeout)

            # 如果大话题（rgb/depth/compressed）超时，自动重试一次（网络抖动容错）
            retry_needed = False
            for topic in ['/image_republisher/rgb_fixed', '/image_republisher/depth_fixed',
                          '/image_republisher/rgb_fixed/compressed',
                          '/image_republisher/depth_fixed/compressedDepth']:
                if topic in self._collected:
                    msg, _ = self._collected[topic]
                    if msg is None:
                        retry_needed = True
                        break

            if retry_needed:
                # 仅重试超时的话题（已收到的不再等）
                timed_out_topics = {t for t in ['/image_republisher/rgb_fixed',
                                                 '/image_republisher/depth_fixed',
                                                 '/image_republisher/rgb_fixed/compressed',
                                                 '/image_republisher/depth_fixed/compressedDepth']
                                    if t in self._collected and self._collected[t][0] is None}
                self.get_logger().info('')
                self.get_logger().info(yellow(f'   ⚠️  图像话题超时 ({", ".join(timed_out_topics)}), '
                                              f'改用 BEST_EFFORT 重试...'))
                for sub in self._subscriptions:
                    self.destroy_subscription(sub)
                self._subscriptions.clear()
                retry_list = [(n, t, ty) for n, t, ty in subscribe_list
                              if t in timed_out_topics]
                if retry_list:
                    self._subscribe_all(retry_list, timeout_total=10.0, best_effort=True)

            self.get_logger().info('')

        # 按序分析
        dispatch = {
            'raw': self.phase_raw,
            'camera_info': self.phase4_camera_info,
            'rgb': self.phase2_rgb,
            'depth': self.phase3_depth,
            'odom': self.phase5_odom,
            'tf': self.phase6_tf,
            'compressed': self.phase_compressed,
        }
        for name in checks:
            if name in dispatch:
                dispatch[name]()

        return self.summary()


# ─── 入口 ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='分布式3D建图数据流测试工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)

    parser.add_argument(
        '--check', '-c', nargs='+',
        choices=['connectivity', 'raw', 'camera_info', 'rgb', 'depth', 'odom', 'tf', 'compressed'],
        help='指定要运行的测试模块 (默认全部)')

    parser.add_argument(
        '--json', '-j', nargs='?', const='auto', default=None,
        help='输出 JSON 报告 (可选指定路径)')

    parser.add_argument(
        '--timeout', '-t', type=float, default=20.0,
        help='并行等待超时秒数 (默认 20)')

    args = parser.parse_args()

    rclpy.init()
    tester = MappingTester(args)
    exit_code = tester.run()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
