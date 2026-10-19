"""PPO teacher and camera/proprioception student architectures."""
import torch
from torch import nn


def teacher_config():
    return {
        "seed": 42, "num_steps_per_env": 32, "save_interval": 50, "logger": "tensorboard",
        "obs_groups": {"policy": ["policy"], "critic": ["policy"]},
        "policy": {"class_name": "ActorCritic", "init_noise_std": .6,
            "actor_obs_normalization": True, "critic_obs_normalization": True,
            "actor_hidden_dims": [256,256,128], "critic_hidden_dims": [256,256,128], "activation": "elu"},
        "algorithm": {"class_name": "PPO", "value_loss_coef": 1.0, "use_clipped_value_loss": True,
            "clip_param": .2, "entropy_coef": .008, "num_learning_epochs": 5,
            "num_mini_batches": 4, "learning_rate": 3e-4, "schedule": "adaptive",
            "gamma": .99, "lam": .95, "desired_kl": .01, "max_grad_norm": 1.0},
    }


class VisionStudent(nn.Module):
    """Three RGB frames + three proprioceptive frames; no simulator-only inputs."""
    history = 3

    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(nn.Conv2d(9,32,5,2), nn.ELU(),
            nn.Conv2d(32,64,3,2), nn.ELU(), nn.Conv2d(64,64,3,2), nn.ELU(),
            nn.AdaptiveAvgPool2d((3,4)), nn.Flatten())
        self.actor = nn.Sequential(nn.Linear(64*3*4+18*3,256), nn.ELU(),
                                   nn.Linear(256,128), nn.ELU(), nn.Linear(128,6), nn.Tanh())

    def forward(self, rgb, proprio):
        # [N, history, H, W, C] -> channels-first temporal stack
        x = rgb.permute(0,1,4,2,3).flatten(1,2).float()/255.0
        return self.actor(torch.cat((self.encoder(x), proprio.flatten(1)), dim=-1))


class History:
    def __init__(self, rgb, proprio):
        self.rgb = rgb[:,None].repeat(1,3,1,1,1).clone()
        self.proprio = proprio[:,None].repeat(1,3,1).clone()

    def update(self, rgb, proprio, done):
        self.rgb = torch.cat((self.rgb[:,1:],rgb[:,None]),1)
        self.proprio = torch.cat((self.proprio[:,1:],proprio[:,None]),1)
        self.rgb[done] = rgb[done,None].repeat(1,3,1,1,1)
        self.proprio[done] = proprio[done,None].repeat(1,3,1)
