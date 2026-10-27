"""실제 USD 상대 자세를 시뮬 인계 평가에만 사용한다. 주행 입력은 만들지 않는다."""
import numpy as np
from farm_sim_devices.basket_alignment import BasketAlignment


class BasketMonitor:
    def __init__(self, stage, robots: list, config: dict) -> None:
        self.evaluator=BasketAlignment(config['spec'])
        self.robots={r['cfg']['robot_id']:r for r in robots}
        self.ids=config['robots'];self.prims={};self.latest=None
        for role,rid in self.ids.items():
            frame=config['spec'][role]['frame']
            prim=stage.GetPrimAtPath(self.robots[rid]['path']+'/'+frame)
            if not prim.IsValid():raise ValueError('인계 평가 프레임 없음: '+frame)
            self.prims[role]=(frame,prim)

    def update(self, now: float) -> None:
        from pxr import UsdGeom
        cache=UsdGeom.XformCache();records={}
        for role,rid in self.ids.items():
            stamp,odom=self.robots[rid]['history'][-1]
            if abs(stamp-now)>1e-6:
                self.latest=None;return
            frame,prim=self.prims[role]
            records[role]=dict(wheel_odom=odom,T_world_evaluation_frames={
                frame:np.asarray(cache.GetLocalToWorldTransform(prim)).T.tolist()})
        self.latest=self.evaluator.sample(now,records['harvest'],records['transport'])
