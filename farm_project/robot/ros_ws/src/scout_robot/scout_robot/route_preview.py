"""Publish separate survey-side previews; never command motion or join across beds."""
import json
import math
from pathlib import Path as FilePath
import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.qos import QoSProfile, DurabilityPolicy
from geometry_msgs.msg import Point, PoseStamped
from nav_msgs.msg import Path
from visualization_msgs.msg import Marker, MarkerArray
from scout_robot.route import load_route


class RoutePreview(Node):
    def __init__(self):
        super().__init__('route_preview')
        self.declare_parameter('route_file', '')
        self.declare_parameter('node_ids', [], ParameterDescriptor(dynamic_typing=True))
        self.declare_parameter('show_all_sections', True)
        filename = self.get_parameter('route_file').value
        graph = json.loads(FilePath(filename).read_text())
        sections = graph.get('survey_sections', {})
        if self.get_parameter('show_all_sections').value and sections:
            self.routes = {sid: load_route(filename, cfg['node_ids']) for sid, cfg in sections.items()}
        elif self.get_parameter('node_ids').value:
            self.routes = {'selected': load_route(filename, self.get_parameter('node_ids').value)}
        else:
            # 다른 환경의 노드 번호를 가정하지 않고 그래프의 각 방향 엣지를 표시합니다.
            edges = [f['properties'] for f in graph['features'] if f['geometry']['type'] in ('LineString', 'MultiLineString')]
            self.routes = {f"edge_{i}": load_route(filename, [edge['startid'], edge['endid']]) for i, edge in enumerate(edges)}
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.path_pub = self.create_publisher(Path, 'route_preview', qos)
        self.markers_pub = self.create_publisher(MarkerArray, 'route_markers', qos)
        self.timer = self.create_timer(1.0, self.publish)
        self.publish()
        self.get_logger().info(f'{len(self.routes)}개 예찰 경로 표시: 청록=진행, 노랑=왼쪽 카메라. 이동 명령은 보내지 않습니다.')

    def publish(self):
        stamp = self.get_clock().now().to_msg()
        path = Path(); path.header.frame_id = 'map'; path.header.stamp = stamp
        markers = MarkerArray()
        clear = Marker(); clear.action = Marker.DELETEALL; markers.markers.append(clear)
        for index, (sid, route) in enumerate(self.routes.items()):
            line = Marker(); line.header = path.header; line.ns = 'survey_routes'; line.id = index
            line.type = Marker.LINE_STRIP; line.action = Marker.ADD
            line.pose.orientation.w = 1.; line.scale.x = .035
            line.color.g = 1.; line.color.b = 1.; line.color.a = .8
            line.points = [Point(x=x, y=y, z=.08) for _, x, y, _ in route]
            markers.markers.append(line)
            _, x0, y0, yaw = route[0]
            label = Marker(); label.header = path.header; label.ns = 'route_labels'; label.id = index
            label.type = Marker.TEXT_VIEW_FACING; label.action = Marker.ADD
            label.pose.position = Point(x=x0, y=y0-.5*math.sin(yaw), z=.25)
            label.pose.orientation.w = 1.; label.scale.z = .25
            label.color.r = 1.; label.color.g = 1.; label.color.b = 1.; label.color.a = 1.
            label.text = sid; markers.markers.append(label)
            for point_index in (1, 4, 6):
                _, x, y, yaw = route[min(point_index, len(route)-1)]
                for side, angle, rgb in [(0, yaw, (0., 1., 1.)), (1, yaw+math.pi/2, (1., .8, 0.))]:
                    arrow = Marker(); arrow.header = path.header
                    arrow.ns = 'forward' if side == 0 else 'camera'; arrow.id = index*10+point_index
                    arrow.type = Marker.ARROW; arrow.action = Marker.ADD; arrow.pose.orientation.w = 1.
                    arrow.points = [Point(x=x, y=y, z=.1), Point(x=x+.45*math.cos(angle), y=y+.45*math.sin(angle), z=.1)]
                    arrow.scale.x = .03; arrow.scale.y = .09; arrow.scale.z = .12
                    arrow.color.r, arrow.color.g, arrow.color.b = rgb; arrow.color.a = 1.
                    markers.markers.append(arrow)
            # Retain the legacy single Path for BED_01. MarkerArray shows all routes.
            if index == 0:
                for _, x, y, yaw in route:
                    pose = PoseStamped(); pose.header = path.header
                    pose.pose.position.x = x; pose.pose.position.y = y
                    pose.pose.orientation.z = math.sin(yaw/2); pose.pose.orientation.w = math.cos(yaw/2)
                    path.poses.append(pose)
        self.path_pub.publish(path); self.markers_pub.publish(markers)


def main(args=None):
    rclpy.init(args=args); node = None
    try:
        node = RoutePreview(); rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None: node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
