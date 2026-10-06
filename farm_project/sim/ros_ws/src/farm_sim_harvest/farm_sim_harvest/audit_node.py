"""공통 서버의 종료 이벤트를 구독해 Isaac 과실 비교만 수행하는 시뮬 전용 노드."""
import json
from pathlib import Path
import re
import uuid
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String
from .evaluation import SceneEvaluator, evaluate_record


class HarvestAudit(Node):
    def __init__(self) -> None:
        super().__init__('harvest_workspace_audit')
        self.declare_parameter('project_root', '')
        self.declare_parameter('audit_config', '')
        root = Path(self.get_parameter('project_root').value).expanduser().resolve()
        path = (root/self.get_parameter('audit_config').value).resolve()
        if not path.is_relative_to(root/'sim'):
            raise ValueError('평가 설정은 sim 내부에 있어야 합니다.')
        config = json.loads(path.read_text())
        for value in (config['output_dir'], config['evaluation']['snapshot_file']):
            if not (root/value).resolve().is_relative_to(root/'sim'):
                raise ValueError('시뮬 평가 입력·출력은 sim 내부에 있어야 합니다.')
        self.robot_id, self.map_id = config['robot_id'], config['map_id']
        self.evaluator = SceneEvaluator(config['evaluation'],root)
        self.output = root/config['output_dir']/uuid.uuid4().hex[:12]
        self.seen = set()
        self.subscription = self.create_subscription(String,'task_events',self.on_record,QoSProfile(
            depth=100,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.TRANSIENT_LOCAL))

    def on_record(self, message: String) -> None:
        try:
            record = json.loads(message.data)
            if record['robot_id'] != self.robot_id or record['map_id'] != self.map_id:
                raise ValueError('평가 이벤트 robot/map 불일치')
            if record['event_id'] in self.seen:
                return
            record = evaluate_record(record,self.evaluator)
            self.output.mkdir(parents=True,exist_ok=True)
            name = re.sub(r'[^A-Za-z0-9_.-]', '_', record['task_id'])[:100]
            path = self.output/(name+'_'+record['event_id']+'.json')
            path.write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
            self.seen.add(record['event_id'])
            self.get_logger().info('workspace audit: '+json.dumps(record['evaluation'],ensure_ascii=False))
        except Exception as error:
            self.get_logger().error('시뮬 과실 평가/로그 실패: '+str(error))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = HarvestAudit()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
