"""Inference comparison helpers; never alter frozen sources or physical flags."""
from dataclasses import asdict, dataclass
import math
import torch


def cap_preload(controller, degrees):
    """A separate instance's origin budget only; release/PD/rate unchanged."""
    if degrees not in (3.,4.) or abs(controller.budget-math.radians(4.))>1e-8:
        raise ValueError('Comparison permits only3/4 degrees below original4 degree budget')
    controller.budget=math.radians(degrees)
    return controller


@dataclass(frozen=True)
class AxialStartSpec:
    start_s: float = 2.
    duration_s: float = 1.
    lateral_fraction: float = .2
    rotation_fraction: float = .2
    max_tcp_speed_m_s: float = .015
    rotation_length_m: float = .08
    damping_m: float = .002

    def __post_init__(self):
        if any(not math.isfinite(v) for v in asdict(self).values()):
            raise ValueError('Finite axial-start parameters required')
        if self.start_s != 2. or self.duration_s <= 0:
            raise ValueError('Preserve the original two second settle')
        if not 0 <= self.lateral_fraction <= 1 or not 0 <= self.rotation_fraction <= 1:
            raise ValueError('Projection fractions must be in [0,1]')
        if min(self.max_tcp_speed_m_s, self.rotation_length_m, self.damping_m) <= 0:
            raise ValueError('Positive speeds/length/damping required')


class MatchedRestore:
    """Pin assignments before *any* bank restore, including wrapper construction.

    Use the original restoration routine and all measured q/qd/targets/history.
    Contact flags remain invalid until the existing physics update verifies them.
    The audit includes partial/autoresets; this adapter only supports one batch.
    """
    def __init__(self, restore, indices, *, pin_first=True):
        self.restore, self.indices, self.pin_first = restore, list(indices), pin_first
        if not self.indices or any(type(i) is not int or i < 0 for i in self.indices):
            raise ValueError('Complete nonnegative integer assignments required')
        self.events, self.env = [], None

    def __call__(self, bank, env, ids, *, assignments=None, arm_target='stored'):
        if env.num_envs != len(self.indices):
            raise ValueError('Matched comparison requires exactly one complete batch')
        self.env = env
        incoming_none = assignments is None
        if incoming_none and self.pin_first:
            assignments = torch.tensor(self.indices, device=env.device, dtype=torch.long)
        if assignments is not None:
            expected = torch.tensor(self.indices, device=env.device, dtype=torch.long)
            if assignments.shape != expected.shape or not torch.equal(assignments, expected):
                raise ValueError('A reset changed the requested matched assignment')
        self.restore(bank, env, ids, assignments=assignments, arm_target=arm_target)
        self.events.append(dict(ids=ids.cpu().tolist(), incoming_random=incoming_none,
            effective_indices=env.handoff_indices[ids].cpu().tolist(), arm_target=arm_target))


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


def project_axial_start(commands, elapsed, *, confirmed, release, attached,
                        qualified, jacobian, axis, action_speed, dt,
                        spec=AxialStartSpec()):
    """Constrain early commands, not contacts/forces/outcomes or elapsed time.

    Later/detached/release commands are identical to the parent. A constrained
    command is never stronger than the parent's largest arm action. No new jaw
    command. Lost qualification holds existing arm targets inside this window.
    Damped projection is approximate; actual TCP/fruit motion must be evaluated.
    """
    if action_speed <= 0 or dt <= 0:
        raise ValueError('Positive action speed and dt required')
    if commands.ndim != 2 or commands.shape[1] != 6 or not torch.isfinite(commands).all():
        raise ValueError('Finite six-dimensional command batch required')
    if jacobian.shape != (len(commands),6,5) or not torch.isfinite(jacobian).all():
        raise ValueError('Finite TCP Jacobian batch required')
    a=torch.as_tensor(axis,device=commands.device,dtype=commands.dtype)
    if a.shape != (3,) or not torch.isfinite(a).all() or a.norm()<1e-9:
        raise ValueError('Finite nonzero policy-world tension axis required')
    a=a/a.norm()
    active=confirmed & ~release & attached & (elapsed>=spec.start_s-1e-7) & (elapsed<spec.start_s+spec.duration_s-1e-7)
    blocked=active & ~qualified
    velocity=commands[:,:5].clamp(-1,1)*action_speed
    j=jacobian.clone();j[:,3:]*=spec.rotation_length_m
    wanted=(j@velocity[:,:,None]).squeeze(-1)
    axial=(wanted[:,:3]*a).sum(-1)
    desired=wanted.clone()
    desired[:,:3]=axial.clamp_min(0)[:,None]*a+spec.lateral_fraction*(wanted[:,:3]-axial[:,None]*a)
    desired[:,3:]*=spec.rotation_fraction
    eye=torch.eye(5,device=j.device,dtype=j.dtype)
    solution=torch.linalg.solve(j.transpose(1,2)@j+spec.damping_m**2*eye,j.transpose(1,2)@desired[:,:,None]).squeeze(-1)
    # Uniform scaling preserves direction; element clipping would change it.
    max_original=velocity.abs().amax(-1)
    scale=(max_original/solution.abs().amax(-1).clamp_min(1e-12)).clamp_max(1)
    predicted=(jacobian[:,:3]@solution[:,:,None]).squeeze(-1)
    scale=scale.minimum((spec.max_tcp_speed_m_s/predicted.norm(dim=-1).clamp_min(1e-12)).clamp_max(1))
    solution*=scale[:,None]
    # A near singular solve can point backwards; hold rather than adding motion.
    backwards=(((jacobian[:,:3]@solution[:,:,None]).squeeze(-1)*a).sum(-1)<-1e-8)
    blocked |= active & backwards
    result=commands.clone()
    result[active,:5]=(solution/action_speed)[active]
    result[blocked,:5]=0
    effective=(jacobian[:,:3]@(result[:,:5]*action_speed)[:,:,None]).squeeze(-1)
    diag=dict(axial_adapter_active=active,axial_adapter_blocked=blocked,
        axial_adapter_predicted_step_m=(effective*a).sum(-1)*dt,
        axial_adapter_predicted_lateral_step_m=(effective-(effective*a).sum(-1)[:,None]*a).norm(dim=-1)*dt)
    return result,diag
