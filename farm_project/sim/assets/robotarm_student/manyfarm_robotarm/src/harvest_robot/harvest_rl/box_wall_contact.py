"""Read-only fruit-to-fixed-base contacts, labelled by actual box-wall geometry."""
import numpy as np


def wall_point_forces(points, forces, walls, margin=.003):
    points=np.asarray(points).reshape(-1,3);forces=np.asarray(forces).reshape(-1)
    if len(points)!=len(forces) or not np.isfinite(points).all() or not np.isfinite(forces).all():
        raise ValueError('Invalid packed contact data')
    result=[]
    for wall in walls:
        mask=(points>=np.asarray(wall['lower'])-margin).all(-1)&(points<=np.asarray(wall['upper'])+margin).all(-1)&(forces>1e-6)
        result.append(dict(path=wall['path'],loaded_points=int(mask.sum()),normal_force_N=float(forces[mask].sum()),
            points_policy_world_m=points[mask].tolist(),normal_forces_N=forces[mask].tolist()))
    return result


def wall_geometry(env):
    from pxr import Usd,UsdGeom,UsdPhysics,Gf
    cache=UsdGeom.XformCache();origin=env.scene.env_origins[0].cpu().numpy();result=[]
    root=env.sim.stage.GetPrimAtPath('/World/envs/env_0/Robot/base_footprint')
    for prim in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
        if not prim.HasAPI(UsdPhysics.CollisionAPI) or not prim.IsA(UsdGeom.Cube):continue
        cube=UsdGeom.Cube(prim);half=float(cube.GetSizeAttr().Get())/2;transform=cache.GetLocalToWorldTransform(prim)
        points=np.array([transform.Transform(Gf.Vec3d(x,y,z)) for x in [-half,half] for y in [-half,half] for z in [-half,half]])-origin
        lo,hi=points.min(0),points.max(0);size=hi-lo;center=(hi+lo)/2
        if (.25<center[0]<.55 and abs(center[1])<.16 and .68<hi[2]<.73 and
                size[2]>.15 and min(size[:2])<.02 and max(size[:2])>.15):
            result.append(dict(path=str(prim.GetPath()),lower=lo.tolist(),upper=hi.tolist(),size=size.tolist()))
    if len(result)!=4:raise ValueError('Expected actual four box-wall cube colliders, got '+str(len(result)))
    return result


class BoxWallRecorder:
    def __init__(self,env):
        from isaacsim.core.simulation_manager import SimulationManager
        self.env=env;self.original=env.scene.update;self.last=env._sim_step_counter;self.frames=[]
        self.walls=wall_geometry(env);sim=SimulationManager.get_physics_sim_view();self.views=[]
        for fruit in env.fruits:
            pattern=fruit.root_physx_view.prim_paths[0].replace('/env_0/','/env_*/')
            view=sim.create_rigid_contact_view(pattern,
                filter_patterns=['/World/envs/env_*/Robot/base_footprint'],max_contact_data_count=128*env.num_envs)
            if view.sensor_count!=env.num_envs or view.filter_count!=1:raise ValueError('Wrong fruit/base contact view shape')
            if list(view.sensor_paths)!=list(fruit.root_physx_view.prim_paths):raise ValueError('Fruit sensor order differs')
            self.views.append(view)
        env.scene.update=self.update

    def update(self,*args,**kwargs):
        result=self.original(*args,**kwargs);env=self.env;counter=env._sim_step_counter
        if counter<=self.last:return result
        self.last=counter;target=env.target_index.cpu().tolist();origins=env.scene.env_origins.cpu().numpy()
        frames=[None]*env.num_envs
        for slot,view in enumerate(self.views):
            force,points,normals,distances,counts,starts=[v.detach().cpu().numpy() for v in view.get_contact_data(dt=env.physics_dt)]
            matrix=view.get_contact_force_matrix(dt=env.physics_dt).detach().cpu().numpy()
            complete=int(counts.sum())<len(points) and not np.any(counts<0)
            for i in range(env.num_envs):
                if target[i]!=slot:continue
                n=int(counts[i,0]);start=int(starts[i,0]);valid=complete and (n==0 or 0<=start<=len(points)-n)
                pp=points[start:start+n]-origins[i] if n and valid else np.empty((0,3))
                ff=force[start:start+n].reshape(-1) if n and valid else np.empty(0)
                frames[i]=dict(base_contact_vector_N=matrix[i,0].tolist(),base_contact_N=float(np.linalg.norm(matrix[i,0])),
                    data_complete=valid,reported_points=n,walls=wall_point_forces(pp,ff,self.walls) if valid else [])
        self.frames.append(dict(physics_step=counter,time_s=counter*env.physics_dt,rows=frames))
        return result

    def drain(self,active):
        frames=self.frames;self.frames=[]
        return [dict(physics_step=f['physics_step'],time_s=f['time_s'],env_ids=active,rows=[f['rows'][i] for i in active]) for f in frames]

    def close(self):self.env.scene.update=self.original
