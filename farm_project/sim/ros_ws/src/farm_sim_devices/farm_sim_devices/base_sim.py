"""USD에 존재하는 관절을 velocity target으로 구동하고 회전량을 읽습니다."""
import numpy as np
from farm_common.kinematics import wheel_targets,WheelOdometry


class BaseSim:
    def __init__(self,world,root_path,config,name='scout_drive'):
        from isaacsim.core.prims import SingleArticulation
        self.config=config
        self.world=world
        self._wheel_drive_gains = None
        self._hold_positions = None
        self.robot=world.scene.add(SingleArticulation(prim_path=root_path,name=name))
        self.odometry=WheelOdometry(config['wheel_radius_m'],config['wheel_separation_m'])

    def initialize(self) -> None:
        self.indices=np.array([self.robot.get_dof_index(n) for n in self.config['wheel_joints']],dtype=np.int32)
        if len(set(self.indices.tolist()))!=2:raise RuntimeError('좌우 바퀴 관절을 구분할 수 없습니다.')
        self.signs=np.asarray(self.config['wheel_signs'],dtype=float)
        self.odometry.update(self.positions(),1.0)
        self.encoder_positions = np.asarray(self.robot.get_joint_positions(joint_indices=self.indices)).copy()
        self.encoder_time = float(self.world.current_time)
        self.servo = None
        if self.config.get('wheel_velocity_servo'):
            from .wheel_servo import WheelVelocityServo
            self.servo = WheelVelocityServo(self.config['wheel_velocity_servo'])
        if self.config.get('wheel_position_hold', False):
            if self._wheel_drive_gains is None:
                kp, kd = self.robot.get_articulation_controller().get_gains()
                self._wheel_drive_gains = (np.asarray(kp)[self.indices].copy(),
                                           np.asarray(kd)[self.indices].copy())
            self._set_wheel_hold(False)
        self._hold_positions = None
        self.command(0.0,0.0)

    def _set_wheel_hold(self, enabled: bool) -> None:
        """바퀴 관절만 제동 전환한다. 팔 gain과 차체 pose는 변경하지 않는다."""
        kp, kd = self._wheel_drive_gains
        # 정지 위치 복원 시간상수 1초의 joint drive. 주행에는 원래 gain 복원.
        self.robot._articulation_view.set_gains(
            kps=(kd if enabled else kp)[None, :], kds=kd[None, :],
            joint_indices=self.indices)

    def command(self, linear: float, angular: float) -> None:
        from isaacsim.core.utils.types import ArticulationAction
        c=self.config
        rates=wheel_targets(linear,angular,c['wheel_radius_m'],c['wheel_separation_m'],
                            c['max_linear_mps'],c['max_angular_rps'])
        targets = np.asarray(rates)*self.signs
        if self.servo is not None:
            positions = np.asarray(self.robot.get_joint_positions(joint_indices=self.indices))
            now = float(self.world.current_time)
            dt = now-self.encoder_time
            delta = positions-self.encoder_positions
            measured = np.arctan2(np.sin(delta),np.cos(delta))/dt if dt>1e-8 else np.zeros(2)
            self.encoder_positions, self.encoder_time = positions.copy(), now
            targets = self.servo.command(targets, measured)
        self.last_joint_targets = targets.copy()
        if self.config.get('wheel_position_hold', False):
            if np.all(np.abs(rates)<1e-8):
                if self._hold_positions is None:
                    self._hold_positions = np.asarray(
                        self.robot.get_joint_positions(joint_indices=self.indices)).copy()
                    self._set_wheel_hold(True)
                self.robot.apply_action(ArticulationAction(
                    joint_positions=self._hold_positions, joint_velocities=targets,
                    joint_indices=self.indices))
                return
            if self._hold_positions is not None:
                self._set_wheel_hold(False)
                self._hold_positions = None
        self.robot.apply_action(ArticulationAction(joint_velocities=targets,
                                                   joint_indices=self.indices))

    def positions(self):
        return np.asarray(self.robot.get_joint_positions(joint_indices=self.indices))*self.signs

    def sample(self,dt):
        positions=self.positions()
        velocities=np.asarray(self.robot.get_joint_velocities(joint_indices=self.indices))*self.signs
        return self.odometry.update(positions,dt),positions.tolist(),velocities.tolist()

    def pose(self):
        return self.robot.get_world_pose()
