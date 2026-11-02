"""업무 실행기와 독립된 TF 수신. 조회 시각과 버퍼 정책은 호출자가 유지한다."""
from rclpy.node import Node
from rclpy.parameter import Parameter
from tf2_ros import TransformListener


class DedicatedTfReceiver:
    def __init__(self, owner, buffer):
        self.closed = False
        self.node = Node(
            owner.get_name() + '_tf_listener', namespace=owner.get_namespace(),
            context=owner.context, use_global_arguments=False,
            cli_args=['--ros-args', '-r', '/tf:=' + owner.resolve_topic_name('/tf'),
                      '-r', '/tf_static:=' + owner.resolve_topic_name('/tf_static')],
            parameter_overrides=[Parameter('use_sim_time', value=bool(
                owner.get_parameter('use_sim_time').value))],
            enable_rosout=False, start_parameter_services=False)
        # 전용 노드만 listener 소유 실행기에 등록한다. 업무 노드는 건드리지 않는다.
        self.listener = TransformListener(buffer, self.node, spin_thread=True)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.listener.unregister()
        # Jazzy TransformListener 종료 절차: 실행기 종료와 스레드 join 후 노드 해제.
        self.listener.executor.shutdown()
        self.listener.dedicated_listener_thread.join()
        self.listener.executor.remove_node(self.node)
        self.node.destroy_node()
