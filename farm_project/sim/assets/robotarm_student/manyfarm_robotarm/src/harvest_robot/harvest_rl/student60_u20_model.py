"""U20 RGB / overhead RGB-D, three-frame history, eight absolute commands."""
import torch
from torch import nn

from .student_v3 import encoder
from .student60_model import Student60Inference

VERSION = 'student60_u20_rgb_executed_targets_v1'


class U20Student(nn.Module):
    history = 3

    def __init__(self):
        super().__init__()
        self.wrist_rgb = encoder(3)
        self.rear_rgbd = encoder(5)
        self.memory = nn.GRU(2 * 64 * 6 + 23 + 2, 128, batch_first=True)
        self.actor = nn.Sequential(nn.Linear(128, 128), nn.ELU(), nn.Linear(128, 8), nn.Tanh())

    def forward(self, rgb, depth_m, camera_valid, state):
        n, t, c, h, w, channels = rgb.shape
        if ((t, c, h, w, channels) != (3, 2, 90, 160, 3) or state.shape != (n, t, 23)
                or depth_m.shape != (n, t, c, h, w) or camera_valid.shape != (n, t, c)):
            raise ValueError('U20 observation shape/history mismatch')
        if torch.any(depth_m[:, :, 0] != 0) or not torch.isfinite(state).all():
            raise ValueError('U20 has no wrist depth; require finite state')
        mask = camera_valid.float()
        wrist = rgb[:, :, 0].float() / 255 * mask[:, :, 0, None, None, None]
        depth = depth_m[:, :, 1]
        valid = torch.isfinite(depth) & (depth > 0) & (depth <= 3)
        rear = torch.cat((rgb[:, :, 1].float() / 255,
            torch.where(valid, depth / 3, 0)[..., None], valid[..., None].float()), -1)
        rear = rear * mask[:, :, 1, None, None, None]
        features = torch.cat((
            self.wrist_rgb(wrist.reshape(n * t, h, w, 3).permute(0, 3, 1, 2)),
            self.rear_rgbd(rear.reshape(n * t, h, w, 5).permute(0, 3, 1, 2))), -1).reshape(n, t, -1)
        memory, _ = self.memory(torch.cat((features, state, mask), -1))
        return self.actor(memory[:, -1])


class U20Inference(Student60Inference):
    """Same executed-target acknowledgement protocol, distinct sensor/checkpoint family."""
    def __init__(self, checkpoint, contract, device='cpu'):
        from .student60_u20_data import require_contract
        require_contract(contract)
        saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
        if saved.get('student60_version') != VERSION or saved.get('contract') != contract:
            raise ValueError('Require matching U20 RGB schema4 checkpoint')
        self.contract = contract
        self.device = device
        self.model = U20Student().to(device).eval()
        self.model.load_state_dict(saved['student'], strict=True)
        self.reset()
