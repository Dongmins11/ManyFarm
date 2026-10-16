"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from .teacher_bridge_pull_risk_env import TeacherBridgePullRiskEnv


class TeacherBridgePullGuardedEnv(TeacherBridgePullRiskEnv):

    def _pre_physics_step(self,proposed):
        previous=self.targets[:,:5].clone()
        super()._pre_physics_step(proposed)
        holding=self.pull_active & self.valid_detach & ~self._t(self.attached) & ~self.release_intent
        # Preserve loaded targets, not measured q. Qualification, natural contact
        # motion, the finite pull clock and actual0.5s retention still run.
        self.targets[holding,:5]=previous[holding]
        self.actions[holding,:5]=0.
        self.path_diagnostics['retention_target_hold']=holding
