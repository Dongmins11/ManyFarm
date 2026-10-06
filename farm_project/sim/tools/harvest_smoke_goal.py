"""설정의 수확 경로 내부에 이동 시험용 Goal을 생성합니다. 실제 예찰 검출 결과가 아닙니다."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section', default='SEC01')
    parser.add_argument('--fraction', type=float, default=.313)
    parser.add_argument('--expected-count', type=int, default=0)
    args = parser.parse_args()
    if not 0 < args.fraction < 1 or args.expected_count < 0:
        parser.error('fraction은 0~1 사이, expected-count는 0 이상이어야 합니다.')
    root = Path(__file__).resolve().parents[2]
    base = root/'sim/ros_ws/src/farm_sim_config'
    task = yaml.safe_load((base/'config/task.yaml').read_text())
    section = task['sections'][args.section]
    graph = json.loads((base/'maps/harvest_graph.geojson').read_text())
    points = {f['properties']['id']:f['geometry']['coordinates'] for f in graph['features'] if f['geometry']['type']=='Point'}
    route = section['harvest_route']
    start,end = points[route['entry_node_id']],points[route['exit_node_id']]
    xy = [a+(b-a)*args.fraction for a,b in zip(start,end)]
    segment = section['observations'][0]['segment_id']
    goal = dict(robot_id='harvest_01',map_id=task['map_id'],timestamp=datetime.now(timezone.utc).isoformat(),
        harvest_task=dict(task_id='smoke_'+uuid.uuid4().hex[:12],
            window_id=segment+'_W99',expected_count=args.expected_count,
            goal_pose=dict(frame_id='map',position=dict(x=xy[0],y=xy[1],z=0.),yaw=route['heading_rad'])))
    # JSON은 ros2 CLI의 YAML Goal 입력으로도 유효합니다.
    print(json.dumps(goal))


if __name__=='__main__':main()
