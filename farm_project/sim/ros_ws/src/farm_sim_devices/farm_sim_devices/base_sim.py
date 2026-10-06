"""USD에 존재하는 관절을 velocity target으로 구동하고 회전량을 읽습니다."""
import numpy as np
from farm_common.kinematics import wheel_targets,WheelOdometry


class BaseSim:
    def __init__(self,world,root_path,config,name='scout_drive'):
        from isaacsim.core.prims import SingleArticulation
        self.config=config
        self.robot=world.scene.add(SingleArticulation(prim_path=root_path,name=name))
        self.odometry=WheelOdometry(config['wheel_radius_m'],config['wheel_separation_m'])

    def initialize(self):
        self.indices=np.array([self.robot.get_dof_index(n) for n in self.config['wheel_joints']],dtype=np.int32)
        if len(set(self.indices.tolist()))!=2:raise RuntimeError('좌우 바퀴 관절을 구분할 수 없습니다.')
        self.signs=np.asarray(self.config['wheel_signs'],dtype=float)
        self.odometry.update(self.positions(),1.0)
        self.command(0.0,0.0)

    def command(self,linear,angular):
        from isaacsim.core.utils.types import ArticulationAction
        c=self.config
        rates=wheel_targets(linear,angular,c['wheel_radius_m'],c['wheel_separation_m'],
                            c['max_linear_mps'],c['max_angular_rps'])
        self.robot.apply_action(ArticulationAction(joint_velocities=np.asarray(rates)*self.signs,
                                                   joint_indices=self.indices))

    def positions(self):
        return np.asarray(self.robot.get_joint_positions(joint_indices=self.indices))*self.signs

    def sample(self,dt):
        positions=self.positions()
        velocities=np.asarray(self.robot.get_joint_velocities(joint_indices=self.indices))*self.signs
        return self.odometry.update(positions,dt),positions.tolist(),velocities.tolist()

    def pose(self):
        return self.robot.get_world_pose()
