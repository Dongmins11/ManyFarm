"""Separate closed-box collision proxy; keep top/visual/assets/policy unchanged."""
from .teacher_component_probe_env import TeacherComponentProbeEnv


class TeacherFloorProxyEnv(TeacherComponentProbeEnv):
    def __init__(self,*args,floor_proxy=False,**kwargs):
        self.floor_proxy_requested=bool(floor_proxy)
        super().__init__(*args,**kwargs)

    def _setup_scene(self):
        super()._setup_scene()
        if not self.floor_proxy_requested:return
        import isaaclab.sim as sim_utils
        from pxr import UsdShade,UsdPhysics
        stage=self.sim.stage
        source=stage.GetPrimAtPath('/World/envs/env_0/Robot/base_footprint/collisions/harvest_lid_lid_plus_tile_1/node_STL_BINARY_')
        if not source:raise ValueError('Expected actual cached closed-lid collider')
        material,_=UsdShade.MaterialBindingAPI(source).ComputeBoundMaterial('physics')
        # Extend below the real flat tile top0.501m only. Original tile/strap
        # collision, visible meshes and box/root poses stay in the scene.
        cfg=sim_utils.CuboidCfg(size=(.2,.2,.05),visual_material=None,physics_material=None,
            collision_props=sim_utils.CollisionPropertiesCfg(contact_offset=.001,rest_offset=0.))
        for i in range(self.cfg.scene.num_envs):
            prim=cfg.func(f'/World/envs/env_{i}/DepositFloorProxy',cfg,translation=(.4,0.,.476))
            if material:
                UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,bindingStrength=UsdShade.Tokens.strongerThanDescendants,materialPurpose='physics')
        self.floor_proxy_material=dict(resolved_source_material=str(material.GetPath()) if material else None,
            binding='Same authored original floor material if bound; otherwise same scene default')
