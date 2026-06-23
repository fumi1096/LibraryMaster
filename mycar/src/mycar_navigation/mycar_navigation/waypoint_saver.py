#!/usr/bin/env python3
"""
航点保存与导航节点 — 航点与地图同目录配对
规则: 加载 xxx.yaml 地图 → 航点自动读/写 xxx_waypoints.yaml

话题 (TROS 兼容, std_msgs 替代 example_interfaces):
  /save_waypoint  (std_msgs/String) → 保存当前 AMCL 位姿
  /goto_waypoint  (std_msgs/String) → 发布 /goal_pose 导航
  /list_waypoints (std_msgs/Empty)  → 打印航点列表
  /clicked_point  (PointStamped)    → 配合 /set_waypoint_name 标点

用法: ros2 run mycar_navigation waypoint_saver --ros-args -p map_path:=/path/to/map.yaml
"""
import os, math, yaml
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Empty
from geometry_msgs.msg import PointStamped, PoseStamped, PoseWithCovarianceStamped


def _wp_path_from_map(map_path: str) -> str:
    if not map_path:
        return os.path.expanduser('~/.mycar/waypoints.yaml')
    base = os.path.splitext(map_path)[0]
    return f'{base}_waypoints.yaml'


class WaypointSaver(Node):
    def __init__(self):
        super().__init__('waypoint_saver')
        self.declare_parameter('map_path', '')
        map_path = self.get_parameter('map_path').value
        self._wp_file = _wp_path_from_map(map_path)
        os.makedirs(os.path.dirname(self._wp_file) or '.', exist_ok=True)
        if not os.path.exists(self._wp_file):
            with open(self._wp_file, 'w') as f:
                yaml.dump({}, f)

        self._waypoints = self._load()
        self._current_pose = None
        self._pending_name = None

        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self._pose_cb, 10)
        self.create_subscription(PointStamped, '/clicked_point', self._click_cb, 10)
        self.create_subscription(String, '/save_waypoint', self._save_cb, 10)
        self.create_subscription(String, '/goto_waypoint', self._goto_cb, 10)
        self.create_subscription(Empty, '/list_waypoints', self._list_cb, 10)
        self.create_subscription(String, '/set_waypoint_name', self._set_name_cb, 10)

        names = list(self._waypoints.keys())
        self.get_logger().info(f'航点文件: {self._wp_file}')
        self.get_logger().info(f'已加载 {len(names)} 个航点: {names if names else "(空)"}')

    def _pose_cb(self, msg): self._current_pose = msg

    def _click_cb(self, msg: PointStamped):
        if self._pending_name is None:
            self.get_logger().info('点击但未设名字. 先: ros2 topic pub /set_waypoint_name std_msgs/String "data: name" --once')
            return
        name = self._pending_name
        self._waypoints[name] = {'x': msg.point.x, 'y': msg.point.y, 'yaw': 0.0}
        self._save()
        self.get_logger().info(f'✅ [{name}] 已保存: ({msg.point.x:.2f}, {msg.point.y:.2f})')
        self._pending_name = None

    def _save_cb(self, msg: String):
        if not self._current_pose:
            self.get_logger().error('无 AMCL 位姿, 请先 RViz 2D Pose Estimate 定位')
            return
        name = msg.data.strip()
        p = self._current_pose.pose.pose.position
        q = self._current_pose.pose.pose.orientation
        yaw = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        self._waypoints[name] = {'x': p.x, 'y': p.y, 'yaw': float(yaw)}
        self._save()
        self.get_logger().info(f'✅ [{name}] 已保存: ({p.x:.2f}, {p.y:.2f}, yaw={yaw:.2f})')

    def _goto_cb(self, msg: String):
        name = msg.data.strip()
        if name not in self._waypoints:
            self.get_logger().error(f'无 [{name}], 可用: {list(self._waypoints)}')
            return
        wp = self._waypoints[name]
        goal = PoseStamped()
        goal.header.frame_id = 'map'
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x, goal.pose.position.y = wp['x'], wp['y']
        yaw = wp.get('yaw', 0)
        goal.pose.orientation.z = math.sin(yaw/2)
        goal.pose.orientation.w = math.cos(yaw/2)
        if not hasattr(self, '_goal_pub'):
            self._goal_pub = self.create_publisher(PoseStamped, '/goal_pose', 10)
        self._goal_pub.publish(goal)
        self.get_logger().info(f'🚀 导航到 [{name}]: ({wp["x"]:.2f}, {wp["y"]:.2f})')

    def _list_cb(self, msg: Empty):
        if not self._waypoints:
            self.get_logger().info('(无航点)'); return
        self.get_logger().info(f'=== 航点 ({len(self._waypoints)}) ===')
        for k, v in self._waypoints.items():
            self.get_logger().info(f'  {k}: ({v["x"]:.2f}, {v["y"]:.2f}, yaw={v.get("yaw",0):.2f})')

    def _set_name_cb(self, msg: String):
        self._pending_name = msg.data.strip()
        self.get_logger().info(f'已设航点名 [{self._pending_name}], RViz Publish Point 点地图保存')

    def _load(self):
        with open(self._wp_file) as f: return yaml.safe_load(f) or {}
    def _save(self):
        with open(self._wp_file, 'w') as f: yaml.dump(self._waypoints, f, allow_unicode=True)

def main():
    rclpy.init(); rclpy.spin(WaypointSaver())

if __name__ == '__main__':
    main()
