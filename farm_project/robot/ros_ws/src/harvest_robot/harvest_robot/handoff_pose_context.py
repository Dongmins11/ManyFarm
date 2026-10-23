"""수확 실물 비교용 TF 실행 문맥. 공통 PoseProvider의 조회 계약은 그대로 사용한다."""
import threading
from typing import Any
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter
from farm_navigation.pose_provider import PoseProvider


class HarvestPoseContext:
    """전용 node는 이 객체의 executor에만 등록한다. 부모 executor에는 넣지 않는다."""
    def __init__(self, owner: Any, settings: Any) -> None:
        namespace = owner.get_namespace().rstrip('/')
        self.node = Node('harvest_navigation_tf', namespace=namespace or '/',
            context=owner.context, use_global_arguments=False,
            cli_args=['--ros-args', '-r', '/tf:='+namespace+'/tf',
                      '-r', '/tf_static:='+namespace+'/tf_static'],
            parameter_overrides=[Parameter('use_sim_time',value=owner.get_parameter('use_sim_time').value)])
        self.provider = PoseProvider(self.node, settings)
        self.executor = SingleThreadedExecutor(context=owner.context)
        self.executor.add_node(self.node)
        self.error = None
        self.closed = False
        self.worker = threading.Thread(target=self._spin,name='harvest_navigation_tf',daemon=True)
        self.worker.start()
        owner.get_logger().info('HANDOFF_TF_EXECUTOR dedicated node='+self.node.get_fully_qualified_name())

    def _spin(self) -> None:
        try:
            self.executor.spin()
        except Exception as error:
            self.error = error
            if self.node.context.ok():
                self.node.get_logger().error('전용 TF executor 종료: '+str(error))

    def close(self) -> None:
        """작업 스레드 종료 후 구독과 node를 해제한다. 반복 호출은 무해하다."""
        if self.closed:
            return
        self.executor.shutdown(timeout_sec=3.)
        self.worker.join(timeout=3.)
        if self.worker.is_alive():
            raise RuntimeError('전용 TF executor 종료 미확인')
        self.provider.close()
        self.executor.remove_node(self.node)
        self.node.destroy_node()
        self.closed=True
