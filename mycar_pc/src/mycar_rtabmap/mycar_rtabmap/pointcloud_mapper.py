#!/usr/bin/env python3
"""
pointcloud_mapper.py — 轻量 3D 点云地图构建

基于里程计位姿累积下采样后的点云，生成全局 3D 地图。
不依赖 RTAB-Map C++ 库，纯 Python + open3d 实现。

订阅:
  /voxel_filter/filtered   — 下采样后的点云 (camera_Link 帧)
  /odom                     — 融合里程计
  TF: camera_Link → base_footprint → odom

发布:
  /pointcloud_map           — 累积的全局点云地图 (odom 帧)

用法:
  ros2 run mycar_rtabmap pointcloud_mapper
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from nav_msgs.msg import Odometry
from tf2_ros import Buffer, TransformListener
import numpy as np
import open3d as o3d


class PointCloudMapper(Node):
    def __init__(self):
        super().__init__('pointcloud_mapper')

        # TF 缓冲
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        # 全局地图点云
        self._global_map = o3d.geometry.PointCloud()
        self._frame_count = 0
        self._skip_frames = 3  # 每 3 帧处理 1 帧

        # 发布累积地图
        self._map_pub = self.create_publisher(PointCloud2, '/pointcloud_map', 10)

        # 订阅下采样点云 + 里程计
        self._cloud_sub = self.create_subscription(
            PointCloud2, '/voxel_filter/filtered', self._cloud_callback, 10)
        self._odom_sub = self.create_subscription(
            Odometry, '/odom', self._odom_callback, 10)

        self._latest_odom = None
        self.get_logger().info('PointCloudMapper 启动 (每 %d 帧处理 1 帧)', self._skip_frames)

    def _odom_callback(self, msg: Odometry):
        self._latest_odom = msg

    def _cloud_callback(self, msg: PointCloud2):
        self._frame_count += 1
        if self._frame_count % self._skip_frames != 0:
            return  # 跳帧降负载

        if self._latest_odom is None:
            return

        # 解析点云
        pts = self._ros_to_o3d(msg)
        if len(pts.points) < 10:
            return

        # 变换: camera_Link → base_footprint → odom
        try:
            # camera_Link → base_footprint
            t1 = self._tf_buffer.lookup_transform(
                'base_footprint', 'camera_Link', rclpy.time.Time())
            # base_footprint → odom
            t2 = self._tf_buffer.lookup_transform(
                'odom', 'base_footprint', rclpy.time.Time())

            # 构建 4x4 变换矩阵
            T_cam_base = self._tf_to_matrix(t1)
            T_base_odom = self._tf_to_matrix(t2)
            T = T_base_odom @ T_cam_base

            pts.transform(T)
        except Exception:
            return

        # 累积到全局地图
        self._global_map += pts

        # 定期下采样全局地图（控制内存）
        if self._frame_count % 30 == 0 and len(self._global_map.points) > 10000:
            self._global_map = self._global_map.voxel_down_sample(0.02)

        # 发布
        out = self._o3d_to_ros(self._global_map, 'odom')
        self._map_pub.publish(out)

    def _ros_to_o3d(self, msg: PointCloud2) -> o3d.geometry.PointCloud:
        offsets = {f.name: f.offset for f in msg.fields if f.name in ('x', 'y', 'z')}
        if len(offsets) != 3:
            return o3d.geometry.PointCloud()

        data = np.frombuffer(msg.data, dtype=np.uint8)
        count = msg.width * msg.height
        pts = np.zeros((count, 3), dtype=np.float32)
        for i in range(count):
            base = i * msg.point_step
            pts[i, 0] = np.frombuffer(data, np.float32, 1, base + offsets['x'])[0]
            pts[i, 1] = np.frombuffer(data, np.float32, 1, base + offsets['y'])[0]
            pts[i, 2] = np.frombuffer(data, np.float32, 1, base + offsets['z'])[0]

        valid = np.isfinite(pts).all(axis=1)
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts[valid])
        return pcd

    def _tf_to_matrix(self, t) -> np.ndarray:
        """TransformStamped → 4x4 numpy array"""
        q = t.transform.rotation
        trans = t.transform.translation
        R = o3d.geometry.get_rotation_matrix_from_quaternion([q.w, q.x, q.y, q.z])
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = [trans.x, trans.y, trans.z]
        return T

    def _o3d_to_ros(self, pcd: o3d.geometry.PointCloud, frame_id: str) -> PointCloud2:
        pts = np.asarray(pcd.points, dtype=np.float32)
        msg = PointCloud2()
        msg.header.frame_id = frame_id
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.height = 1
        msg.width = len(pts)
        msg.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
        ]
        msg.point_step = 12
        msg.row_step = msg.point_step * msg.width
        msg.is_bigendian = False
        msg.is_dense = True
        msg.data = pts.tobytes()
        return msg


def main():
    rclpy.init()
    try:
        rclpy.spin(PointCloudMapper())
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()
