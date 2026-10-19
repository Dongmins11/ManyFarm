"""Training-only exploration guard; inference/checkpoint weights remain explicit."""
import torch


def configure_exploration(policy, optimizer, reset_std=None, minimum=0.05, maximum=0.6):
    if not 0 < minimum <= maximum or (reset_std is not None and not minimum <= reset_std <= maximum):
        raise ValueError("Invalid exploration bounds/reset")
    if getattr(policy, "state_dependent_std", False) or not hasattr(policy, "std"):
        raise ValueError("Exploration guard requires scalar std policy")
    before = policy.std.detach().cpu().tolist()
    @torch.no_grad()
    def bound(*_):
        if not torch.isfinite(policy.std).all():
            raise FloatingPointError("Non-finite exploration std")
        policy.std.clamp_(minimum, maximum)
    with torch.no_grad():
        if reset_std is not None:
            policy.std.fill_(reset_std)
    bound()
    handle = optimizer.register_step_post_hook(bound)
    print(f"EXPLORATION before={before} after={policy.std.detach().cpu().tolist()} bounds=({minimum},{maximum})",flush=True)
    return handle

@torch.no_grad()
def adapt_warm_start_normalizers(policy, prior_count=8192):
    """Keep useful old scaling, but unblock new formerly constant features."""
    for name in ('actor_obs_normalizer','critic_obs_normalizer'):
        norm=getattr(policy,name,None)
        if norm is None or not hasattr(norm,'count'):
            continue
        constant=norm._std < 1e-4
        norm._mean[constant]=0
        norm._var[constant]=1
        norm._std[constant]=1
        before=int(norm.count)
        norm.count.clamp_(max=prior_count)
        print(f"NORMALIZER {name}: count {before}->{int(norm.count)}, neutralized {int(constant.sum())} constant features",flush=True)

@torch.no_grad()
def correct_unused_fruit_normalization(policy):
    """Evaluation ablation: neutralize only constant extra-fruit slots in obs82.

    Slot0/target/robot features, learned weights, sample count and exploration
    are unchanged. Does not update statistics from evaluation observations.
    """
    changed={}
    for name in ('actor_obs_normalizer','critic_obs_normalizer'):
        norm=getattr(policy,name)
        if norm._std.shape[-1] != 82:
            raise ValueError('Expected harvest observation contract of 82 features')
        selected=torch.zeros_like(norm._std,dtype=torch.bool)
        selected[...,47:68]=True  # fruit slots1..7 relative xyz
        selected[...,69:76]=True  # fruit slots1..7 masks
        selected &= norm._std < 1e-4
        norm._mean[selected]=0
        norm._var[selected]=1
        norm._std[selected]=1
        changed[name]=selected.nonzero()[:,-1].cpu().tolist()
    print(f'EVAL_FRUIT_NORMALIZATION: {changed}',flush=True)
    return changed


def freeze_normalizers(policy):
    """Stop statistics updates even when PPO switches the model to train mode."""
    for name in ('actor_obs_normalizer','critic_obs_normalizer'):
        norm=getattr(policy,name,None)
        if norm is not None and hasattr(norm,'until'):
            norm.until=0
    print('NORMALIZATION_FROZEN: actor and critic statistics will not update',flush=True)


@torch.no_grad()
def prepare_stage_normalizers(policy):
    """Preserve learned geometry scaling; only unblock newly varying stage signals."""
    changed={}
    for name in ('actor_obs_normalizer','critic_obs_normalizer'):
        norm=getattr(policy,name)
        if norm._std.shape[-1] != 82:
            raise ValueError('Expected observation contract 82')
        selected=torch.zeros_like(norm._std,dtype=torch.bool)
        selected[..., [38,40,41,43,79,80]]=True
        selected &= norm._std < 1e-4
        # Keep the mean so each feature's pre-transition value still maps to zero.
        norm._var[selected]=1
        norm._std[selected]=1
        changed[name]=selected.nonzero()[:,-1].cpu().tolist()
    freeze_normalizers(policy)
    print(f'STAGE_NORMALIZATION: {changed}',flush=True)
    return changed


@torch.no_grad()
def scale_warm_start_arm(policy, scale):
    """One-time transport transfer: scale arm output rows, preserving the gripper."""
    if not 0 <= scale <= 1:
        raise ValueError('Arm transfer scale must be between zero and one')
    head=[m for m in policy.actor.modules() if isinstance(m,torch.nn.Linear)][-1]
    if head.out_features != 6:
        raise ValueError('Expected five arm actions and one gripper action')
    head.weight[:5].mul_(scale)
    if head.bias is not None:head.bias[:5].mul_(scale)
    print('WARM_START_ARM_SCALE',scale,'gripper row preserved',flush=True)


@torch.no_grad()
def initialize_place_gripper(policy):
    """One-time place transfer; preserve all arm output rows and shared features."""
    head=[m for m in policy.actor.modules() if isinstance(m,torch.nn.Linear)][-1]
    if head.out_features != 6: raise ValueError('Expected six joint actions')
    head.weight[5].zero_()
    head.bias[5].zero_()
    print('PLACE_TRANSFER: gripper output initialized to zero; arm rows preserved',flush=True)
