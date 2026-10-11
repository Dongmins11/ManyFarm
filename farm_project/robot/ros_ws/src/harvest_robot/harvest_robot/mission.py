"""공통 이동을 마친 뒤 설정된 팔 Action의 종료를 기다립니다. 팔 작업 정책은 소유하지 않습니다."""
from dataclasses import asdict
from .contract import resolve_section


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
                result = staged.navigate(resolve_section(getattr(self.goal, "section_id", None), self.node.config), xy, task.goal_pose.yaw)
            else:
                result = self.node.navigator.navigate(xy, task.goal_pose.yaw)
            self.node.check()
            arrival = asdict(result)
            self.node.arrival_result = arrival
            arm = getattr(self.node, 'arm_client', None)
            if arm is not None:
                self.node.mission_stage = 'ARM'
                self.node.arm_result = arm.execute(self.goal, self.node.check, self.node.communication.arm_feedback)
            return arrival
        except Exception:
            # 팔과 주행 종료를 각각 확인합니다. 한쪽 실패로 다른 쪽 정리를 생략하지 않습니다.
            errors = []
            arm = getattr(self.node, 'arm_client', None)
            if arm is not None and arm.has_goal:
                try:
                    terminal = arm.cancel()
                    if terminal is not None:
                        self.node.arm_result = terminal
                except Exception as error:
                    errors.append(str(error))
            try:
                executor = getattr(self.node, "staged_navigation", None) or self.node.navigator
                executor.cancel_nav()
            except Exception as error:
                errors.append(str(error))
            if errors:
                self.node.blocked = True
                raise RuntimeError('CANCEL_UNCONFIRMED: ' + '; '.join(errors))
            raise
        finally:
            if control is not None:
                control.end()
