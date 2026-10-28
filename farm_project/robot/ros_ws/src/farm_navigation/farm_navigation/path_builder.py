"""그래프 계산 결과를 ROS Path로 변환합니다. 이 함수는 이동을 실행하지 않습니다."""
import math
from builtin_interfaces.msg import Time
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from .navigation_types import RoutePlan


def build_path(plan: RoutePlan, yaw: float, stamp: Time, spacing_m: float=.04, *, reverse: bool=False) -> Path:
    if not plan.points or not math.isfinite(yaw) or not math.isfinite(spacing_m) or spacing_m<=0:
        raise ValueError('경로·방향·보간 간격이 유효하지 않습니다.')
    result=Path()
    result.header.frame_id=plan.frame_id
    result.header.stamp=stamp
    def add(x: float, y: float, heading: float) -> None:
        pose=PoseStamped()
        pose.header=result.header
        pose.pose.position.x=float(x); pose.pose.position.y=float(y)
        pose.pose.orientation.z=math.sin(heading/2)
        pose.pose.orientation.w=math.cos(heading/2)
        result.poses.append(pose)
    if plan.headings is not None:
        # 제어기가 생성한 곡선/벽 경로는 점 수와 차체 방향을 그대로 보존한다.
        if (len(plan.points) < 2 or len(plan.headings) != len(plan.points)
                or not plan.frame_id or reverse
                or any(len(point) != 2 or not all(math.isfinite(v) for v in point) for point in plan.points)
                or not all(math.isfinite(v) for v in plan.headings)
                or abs(math.atan2(math.sin(plan.headings[-1]-yaw), math.cos(plan.headings[-1]-yaw))) > 1e-6):
            raise ValueError('명시적 경로의 점·방향·최종 yaw 불일치 또는 중복 후진 지정')
        for (x, y), heading in zip(plan.points, plan.headings):
            add(x, y, heading)
        return result
    for a,b in zip(plan.points,plan.points[1:]):
        count=max(1,math.ceil(math.dist(a,b)/spacing_m))
        heading=math.atan2(b[1]-a[1],b[0]-a[0]) + (math.pi if reverse else 0.)
        for i in range(count): add(a[0]+(b[0]-a[0])*i/count,a[1]+(b[1]-a[1])*i/count,heading)
    # 제자리 방향 정렬에도 두 pose를 제공하며 최종 작업 방향을 보존합니다.
    if not result.poses: add(*plan.points[-1],yaw)
    add(*plan.points[-1],yaw)
    return result
