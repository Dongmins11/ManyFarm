"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

class TensorGraspKinematics:
    """Cached-URDF FK/Jacobian for the existing five arm joints, in policy world.

    Uses the same gripper-link TCP as ArmKinematics and env._tcp. No per-frame
    CPU transfer/FK loop and no simulator-only Jacobian layout assumptions.
    """
    def __init__(self, path, diameter, *, device='cpu', dtype=torch.float32):
        from .kinematics import ArmKinematics, origin
        kin = ArmKinematics(path)
        by_child = {j.find('child').get('link'): j for j in kin.root.findall('joint')}
        chain, link = [], 'arm_2/gripper_link'
        while link in by_child:
            j = by_child[link]; chain.append(j); link = j.find('parent').get('link')
        self.chain = []
        controlled = []
        for j in reversed(chain):
            name = j.get('name')
            index = kin.names.index(name) if name in kin.names else None
            if index is not None and index >= 5:
                raise ValueError('TCP chain must not depend on the moving jaw')
            if index is None and j.get('type') != 'fixed':
                raise ValueError('Uncontrolled movable joint in cached TCP chain')
            axis_node = j.find('axis')
            axis = ([float(v) for v in axis_node.get('xyz').split()]
                    if index is not None and axis_node is not None else [0., 0., 0.])
            a = torch.tensor(axis, device=device, dtype=dtype)
            if index is not None:
                if a.norm() < 1e-9: raise ValueError('Nonzero controlled axis required')
                a = a/a.norm(); controlled.append(index)
            self.chain.append((torch.as_tensor(origin(j.find('origin')),device=device,dtype=dtype), index, a))
        if sorted(controlled) != list(range(5)):
            raise ValueError('Expected each of the five controlled joints once')
        self.offset = torch.tensor([-.0079+diameter/2, -.000218121, -.085], device=device,dtype=dtype)

    def pose_and_jacobian(self, q):
        if q.ndim != 2 or q.shape[1] != 6 or not torch.isfinite(q).all():
            raise ValueError('Finite batch of six measured joint angles required')
        n = len(q)
        t = torch.eye(4,device=q.device,dtype=q.dtype).repeat(n,1,1)
        positions, axes = {}, {}
        eye = torch.eye(3,device=q.device,dtype=q.dtype)
        for base, index, axis in self.chain:
            t = t @ base
            if index is None: continue
            positions[index] = t[:,:3,3].clone()
            axes[index] = (t[:,:3,:3] @ axis).clone()
            x,y,z = axis.unbind()
            k = torch.stack([torch.stack([x*0,-z,y]),torch.stack([z,y*0,-x]),torch.stack([-y,x,z*0])])
            angle=q[:,index,None,None]
            rotation=eye+torch.sin(angle)*k+(1-torch.cos(angle))*(k@k)
            moved=torch.eye(4,device=q.device,dtype=q.dtype).repeat(n,1,1)
            moved[:,:3,:3]=rotation
            t=t@moved
        p=t[:,:3,3]+(t[:,:3,:3]@self.offset)
        angular=torch.stack([axes[i] for i in range(5)],dim=-1)
        linear=torch.stack([torch.linalg.cross(axes[i],p-positions[i],dim=-1) for i in range(5)],dim=-1)
        return p,t[:,:3,:3],torch.cat([linear,angular],dim=1)
