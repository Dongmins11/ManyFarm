"""Closed floor proxy, respecting clone inheritance and hiding render geometry."""
from .teacher_component_probe_env import TeacherComponentProbeEnv


class TeacherFloorProxyEnv(TeacherComponentProbeEnv):
    def __init__(self,*args,floor_proxy=False,**kwargs):
        self.floor_proxy_requested=bool(floor_proxy)
        super().__init__(*args,**kwargs)

    def _setup_scene(self):
        super()._setup_scene()
        if not self.floor_proxy_requested:return
        import isaaclab.sim as sim_utils
        from pxr import UsdShade,UsdGeom,UsdPhysics
        stage=self.sim.stage
        source=stage.GetPrimAtPath('/World/envs/env_0/Robot/base_footprint/collisions/harvest_lid_lid_plus_tile_1/node_STL_BINARY_')
        if not source:raise ValueError('Expected actual cached closed-lid collider')
        material,_=UsdShade.MaterialBindingAPI(source).ComputeBoundMaterial('physics')
        cfg=sim_utils.CuboidCfg(size=(.2,.2,.05),visual_material=None,physics_material=None,
            collision_props=sim_utils.CollisionPropertiesCfg(contact_offset=.001,rest_offset=0.))
        for i in range(self.cfg.scene.num_envs):
            path=f'/World/envs/env_{i}/DepositFloorProxy'
            # copy_from_source=False makes later environments inherit env0's
            # newly added prim. Never spawn a second prim at an inherited path.
            if stage.GetPrimAtPath(path):continue
            prim=cfg.func(path,cfg,translation=(.4,0.,.476))
            UsdGeom.Imageable(prim).CreateVisibilityAttr().Set('invisible')
            if material:
                UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,bindingStrength=UsdShade.Tokens.strongerThanDescendants,materialPurpose='physics')
        # The original tiles are rigidly fused into base_footprint. A new
        # static slab must not create static/base self-overlap constraints;
        # keep its interactions with fruit and separately articulated arms.
        for i in range(self.cfg.scene.num_envs):
            prim=stage.GetPrimAtPath(f'/World/envs/env_{i}/DepositFloorProxy')
            UsdPhysics.FilteredPairsAPI.Apply(prim).CreateFilteredPairsRel().AddTarget(
                f'/World/envs/env_{i}/Robot/base_footprint')
        self.floor_proxy_material=dict(resolved_source_material=str(material.GetPath()) if material else None,
            binding='Same authored original floor material if bound; otherwise same scene default')
