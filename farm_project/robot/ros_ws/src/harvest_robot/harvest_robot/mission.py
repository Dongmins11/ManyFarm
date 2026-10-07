"""수확 이동만 수행합니다. 팔 작업과 정답 과실 수는 성공 수량으로 사용하지 않습니다."""
from dataclasses import asdict


class MissionCanceled(Exception):
    pass


class HarvestMission:
    def __init__(self, node, goal) -> None:
        self.node, self.goal = node, goal

    def run(self) -> dict:
        task = self.goal.harvest_task
        control = getattr(self.node, 'tag_control', None)
        try:
            self.node.check()
            staged = getattr(self.node, "staged_navigation", None)
            if staged is None:
                self.node.navigator.preflight_navigation()
            if control is not None:
                control.begin()
            xy = (task.goal_pose.position.x, task.goal_pose.position.y)
            if staged is not None:
                result = staged.navigate(self.goal.section_id, xy, task.goal_pose.yaw)
            else:
                result = self.node.navigator.navigate(xy, task.goal_pose.yaw)
            self.node.check()
            return asdict(result)
        except Exception:
            # 진행 함수가 반환한 뒤 취소/정지를 확인합니다. 실패하면 다음 Goal을 거절합니다.
            try:
                executor = getattr(self.node, "staged_navigation", None) or self.node.navigator
                executor.cancel_nav()
            except Exception as error:
                self.node.blocked = True
                raise RuntimeError('CANCEL_UNCONFIRMED: ' + str(error))
            raise
        finally:
            if control is not None:
                control.end()
