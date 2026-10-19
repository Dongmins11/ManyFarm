"""Original physical success predicates with absolute-goal jaw intent semantics.

A rising goal still commands closure when it remains below measured jaw angle.
Only assessment direction changes; eight applied commands are unchanged.
"""
from .student60_eval_env import Student60EvalEnv
from harvest_runtime.student60_command_intent import jaw_drive_intent


class CameraStudentEvalEnv(Student60EvalEnv):
    def _record_assessment_inputs(self):
        self.goal_delta_jaw_direction=self.actions[:,-1].clone()
        self.actions[:,-1]=jaw_drive_intent(self.targets[:,-1],self.previous_gripper_q,
                                          self.settings.gripper_speed,self.step_dt)
        super()._record_assessment_inputs()

    def _get_rewards(self):
        value=super()._get_rewards()
        self.chain_snapshot['jaw_goal_delta_direction']=self.goal_delta_jaw_direction.clone()
        self.chain_snapshot['jaw_measured_drive_direction']=self.actions[:,-1].clone()
        return value
