#!/usr/bin/env python3
"""
diagnose_topics.py — 分布式3D建图数据流诊断脚本
在PC端运行，逐一检查各建图核心话题的数据格式和传输状态

用法:
  python3 diagnose_topics.py          # 执行所有检查
  python3 diagnose_topics.py --quick  # 仅检查建图核心话题
"""
import sys
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from nav_msgs.msg import Odometry
import numpy as np
import time


class TopicDiagnoser(Node):
    def __init__(self, quick=False):
        super().__init__('topic_diagnoser')
        self.quick = quick
        self.results = []
        self._received = {}

        self.get_logger().info('='*60)
        self.get_logger().info('  分布式3D建图 — 数据流诊断')
        self.get_logger().info('='*60)
        self.get_logger().info('')

    def log_result(self, phase, name, status, detail=''):
        icon = '✅' if status else '❌'
        self.get_logger().info(f'  [{phase}] {icon} {name}')
        if detail:
            self.get_logger().info(f'         {detail}')
        self.results.append((phase, name, status, detail))

    def check_rgb(self):
        """Phase 2: RGB 图像管线"""
        self.get_logger().info('--- Phase 2: RGB 图像管线 ---')

        msg = self._wait_for_msg('/image_republisher/rgb_fixed', Image, 15.0)
        if msg is None:
            self.log_result('P2', 'RGB话题', False, '15秒内未收到消息')
            return

        info = []
        info.append(f'encoding={msg.encoding}')
        info.append(f'frame_id={msg.header.frame_id}')
        info.append(f'size={msg.width}x{msg.height}')
        info.append(f'step={msg.step}')
        info.append(f'stamp.sec={msg.header.stamp.sec}')

        # Encoding check
        encoding_ok = msg.encoding in ('mono8', 'bgr8', 'rgb8')
        self.log_result('P2', f'RGB编码={msg.encoding}', encoding_ok,
                       '期望 mono8 或 bgr8' if not encoding_ok else '')

        # Frame ID
        frame_ok = msg.header.frame_id == 'camera_Link'
        self.log_result('P2', f'RGB frame_id={msg.header.frame_id}', frame_ok,
                       '期望 camera_Link' if not frame_ok else '')

        # Size
        size_ok = msg.width == 640 and msg.height == 352
        self.log_result('P2', f'RGB 分辨率={msg.width}x{msg.height}', size_ok,
                       '期望 640x352' if not size_ok else '')

        # Timestamp
        epoch_ok = msg.header.stamp.sec > 1000000000
        self.log_result('P2', f'RGB时间戳 sec={msg.header.stamp.sec}', epoch_ok,
                       '非epoch时间戳，image_republisher未修正' if not epoch_ok else '')

        # Data integrity
        data = np.frombuffer(msg.data, dtype=np.uint8)
        nonzero_ratio = (data > 0).mean()
        data_ok = nonzero_ratio > 0.01
        self.log_result('P2', f'RGB数据完整性 (非零{nonzero_ratio*100:.1f}%)', data_ok,
                       f'像素范围 {data.min()}~{data.max()}' if data_ok else '图像全黑')
        self.get_logger().info('')

    def check_depth(self):
        """Phase 3: 深度图像管线"""
        self.get_logger().info('--- Phase 3: 深度图像管线 ---')

        msg = self._wait_for_msg('/image_republisher/depth_fixed', Image, 15.0)
        if msg is None:
            self.log_result('P3', '深度话题', False, '15秒内未收到消息')
            return

        # Encoding - MOST CRITICAL
        encoding_ok = msg.encoding == '16UC1'
        self.log_result('P3', f'深度编码={msg.encoding}', encoding_ok,
                       '❌ RTAB-Map 只认 16UC1 (mm) 和 32FC1 (m)')

        # Frame ID
        frame_ok = msg.header.frame_id == 'camera_Link'
        self.log_result('P3', f'深度 frame_id={msg.header.frame_id}', frame_ok,
                       '期望 camera_Link')

        # Timestamp
        epoch_ok = msg.header.stamp.sec > 1000000000
        self.log_result('P3', f'深度时间戳', epoch_ok, '')

        # Depth values
        data = np.frombuffer(msg.data, dtype=np.uint16)
        nonzero = data[data > 0]
        if len(nonzero) > 0:
            depth_ok = len(nonzero) / len(data) > 0.05
            in_range = ((nonzero >= 300) & (nonzero <= 5000)).mean()
            self.log_result('P3', f'深度值: {len(nonzero)}有效/{len(data)}总',
                          depth_ok,
                          f'范围 {nonzero.min()}~{nonzero.max()}mm, '
                          f'0.3-5.0m内占比 {in_range*100:.1f}%')
        else:
            self.log_result('P3', '深度值', False, '❌ 全零！stereonet 未输出有效深度')
        self.get_logger().info('')

    def check_camera_info(self):
        """Phase 4: CameraInfo 管线"""
        self.get_logger().info('--- Phase 4: CameraInfo 管线 ---')

        msg = self._wait_for_msg('/image_republisher/rgb_camera_info_fixed',
                                 CameraInfo, 15.0)
        if msg is None:
            self.log_result('P4', 'CameraInfo话题', False, '15秒内未收到消息')
            return

        k = msg.k
        p = msg.p
        self.log_result('P4', f'frame_id={msg.header.frame_id}',
                       msg.header.frame_id == 'camera_Link', '')
        self.log_result('P4', f'分辨率={msg.height}x{msg.width}',
                       msg.height == 352 and msg.width == 640, '')
        self.log_result('P4', f'时间戳 epoch', 
                       msg.header.stamp.sec > 1000000000, '')
        self.log_result('P4', f'K: fx={k[0]:.2f} cx={k[2]:.2f} fy={k[4]:.2f} cy={k[5]:.2f}',
                       k[0] > 0 and k[4] > 0, '内参无效')
        self.log_result('P4', f'P: fx={p[0]:.2f} cx={p[2]:.2f} fy={p[5]:.2f} cy={p[6]:.2f}',
                       p[0] > 0, '❌ P矩阵为空！depth→3D投影将失败')
        self.get_logger().info('')

    def check_odom(self):
        """Phase 5: 里程计管线"""
        self.get_logger().info('--- Phase 5: 里程计管线 ---')

        msg = self._wait_for_msg('/odom', Odometry, 8.0)
        if msg is None:
            self.log_result('P5', '/odom话题', False, '8秒内未收到消息')
            return

        pose = msg.pose.pose
        twist = msg.twist.twist
        self.log_result('P5', f'frame_id={msg.header.frame_id}',
                       msg.header.frame_id == 'odom', '')
        self.log_result('P5', f'child_frame_id={msg.child_frame_id}',
                       msg.child_frame_id == 'base_footprint', '')
        self.log_result('P5', f'位置: ({pose.position.x:.4f}, {pose.position.y:.4f}, {pose.position.z:.1f})',
                       abs(pose.position.z) < 0.01, 'z非零→不是2D模式')
        self.log_result('P5', f'时间戳 epoch: sec={msg.header.stamp.sec}',
                       msg.header.stamp.sec > 1000000000, '')
        cov = msg.pose.covariance
        self.log_result('P5', f'协方差(x,y,yaw): [{cov[0]:.6f}, {cov[7]:.6f}, {cov[35]:.6f}]',
                       cov[0] > 0, '协方差为零→RTAB-Map过度信任里程计')
        self.get_logger().info('')

    def check_raw_topics(self):
        """检查原始StereoNetNode话题"""
        self.get_logger().info('--- 补充: 原始StereoNetNode诊断 ---')

        # camera info
        msg = self._wait_for_msg('/StereoNetNode/rectify_left_image/camera_info',
                                 CameraInfo, 10.0)
        if msg:
            self.log_result('RAW', '原始camera_info (有修正必要)',
                           msg.header.stamp.sec < 1000000000,  # 期望非epoch（boot时间）
                           f'时间戳sec={msg.header.stamp.sec} → boot时间，需修正')
        else:
            self.log_result('RAW', '原始camera_info', False, '10秒内未收到')

        # pointcloud
        from sensor_msgs.msg import PointCloud2
        msg = self._wait_for_msg('/StereoNetNode/stereonet_pointcloud2',
                                 PointCloud2, 10.0)
        if msg:
            self.log_result('RAW', f'原始点云: {msg.width}点, frame_id={msg.header.frame_id}',
                           msg.width > 0, '')

        self.get_logger().info('')

    def _wait_for_msg(self, topic, msg_type, timeout_sec):
        """等待单个消息"""
        future = self._received.setdefault(topic, {})
        data = []

        def cb(msg):
            data.append(msg)

        sub = self.create_subscription(msg_type, topic, cb, 10)
        start = time.time()
        rclpy.spin_once(self, timeout_sec=0)
        while time.time() - start < timeout_sec and not data:
            rclpy.spin_once(self, timeout_sec=0.1)
        self.destroy_subscription(sub)

        if data:
            self.get_logger().info(f'  ✅ {topic} 收到 ({time.time()-start:.1f}s)')
            return data[0]
        self.get_logger().info(f'  ⏱️  {topic} 超时 ({timeout_sec:.0f}s)')
        return None

    def run(self):
        self.check_raw_topics()
        self.check_camera_info()
        self.check_rgb()
        self.check_depth()
        self.check_odom()

        self.get_logger().info('')
        self.get_logger().info('='*60)
        self.get_logger().info('  诊断汇总')
        self.get_logger().info('='*60)
        passed = sum(1 for r in self.results if r[2])
        failed = sum(1 for r in self.results if not r[2])
        for phase, name, status, detail in self.results:
            icon = '✅' if status else '❌'
            self.get_logger().info(f'  {icon} [{phase}] {name}' +
                                  (f' | {detail}' if detail else ''))
        self.get_logger().info('')
        self.get_logger().info(f'  通过: {passed} / 失败: {failed}')
        self.get_logger().info('='*60)


def main():
    rclpy.init()
    quick = '--quick' in sys.argv
    node = TopicDiagnoser(quick)
    node.run()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
