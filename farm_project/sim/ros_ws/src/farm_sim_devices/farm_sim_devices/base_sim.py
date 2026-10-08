"""USD에 존재하는 관절을 velocity target으로 구동하고 회전량을 읽습니다."""
import numpy as np
from farm_common.kinematics import wheel_targets,WheelOdometry


class BaseSim:
    def __init__(self,world,root_path,config,name='scout_drive'):
        from isaacsim.core.prims import SingleArticulation
        self.config=config
        self.world=world
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
        self.command(0.0,0.0)

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
