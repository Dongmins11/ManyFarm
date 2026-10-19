"""CPU export of the selected deterministic actors with their exact normalizers."""
import copy
import torch
from torch import nn
from tensordict import TensorDict
from rsl_rl.modules import ActorCritic
from .policy import teacher_config
from .progress_normalization import install_grasp_progress_normalization
from .progress_normalization import GraspProgressNormalization


class ExportedActor(nn.Module):
    def __init__(self,policy):
        super().__init__()
        self.actor=copy.deepcopy(policy.actor).cpu().eval()
        normalizer=policy.actor_obs_normalizer
        self.register_buffer('mean',normalizer._mean.detach().cpu().clone())
        self.register_buffer('std',normalizer._std.detach().cpu().clone())
        self.epsilon=float(normalizer.eps)
        self.identity_progress=isinstance(normalizer,GraspProgressNormalization)

    def forward(self,raw_observation):
        if raw_observation.dim()!=2 or raw_observation.size(1)!=82:
            raise RuntimeError('Teacher expects raw float32 observation[N,82]')
        normalized=(raw_observation-self.mean)/(self.std+self.epsilon)
        if self.identity_progress:normalized[:,39]=raw_observation[:,39]
        return self.actor(normalized)


def reference_policy(checkpoint,identity_progress):
    cfg=teacher_config();settings=dict(cfg['policy']);settings.pop('class_name')
    policy=ActorCritic(TensorDict({'policy':torch.zeros(1,82)},batch_size=[1]),
        cfg['obs_groups'],6,**settings)
    if identity_progress:install_grasp_progress_normalization(policy)
    state=torch.load(checkpoint,map_location='cpu',weights_only=True)['model_state_dict']
    policy.load_state_dict(state,strict=True);policy.eval()
    for p in policy.parameters():p.requires_grad_(False)
    return policy


def export_actor(checkpoint,destination,identity_progress):
    policy=reference_policy(checkpoint,identity_progress)
    scripted=torch.jit.script(ExportedActor(policy));scripted.save(str(destination))
    loaded=torch.jit.load(str(destination),map_location='cpu').eval()
    generator=torch.Generator().manual_seed(106013);maximum=0.;samples=0
    before={k:v.clone() for k,v in policy.state_dict().items()}
    with torch.inference_mode():
        for batch in (1,32,256):
            n=policy.actor_obs_normalizer
            raw=n._mean+n._std*torch.randn(batch,82,generator=generator)
            raw[:,39]=torch.linspace(0.,1.,batch)
            expected=policy.act_inference(TensorDict({'policy':raw},batch_size=[batch]))
            actual=loaded(raw);error=float((expected-actual).abs().max())
            torch.testing.assert_close(actual,expected,rtol=1e-6,atol=2e-5)
            maximum=max(maximum,error);samples+=batch
    if any(not torch.equal(v,policy.state_dict()[k]) for k,v in before.items()):
        raise ValueError('Export/validation mutated weights or normalization')
    return dict(format='torchscript',input_shape=['N',82],input_dtype='float32',
        input='raw Teacher82; normalizer is included; do not normalize twice',
        output_shape=['N',6],output='deterministic raw actor action; not torque or absolute joint position',
        recurrent=False,progress_slot39_identity=identity_progress,
        normalization_epsilon=policy.actor_obs_normalizer.eps,
        comparison_samples=samples,maximum_absolute_error=maximum,
        original_weights_and_normalizers_unchanged=True,harvest_performance_test=False)
