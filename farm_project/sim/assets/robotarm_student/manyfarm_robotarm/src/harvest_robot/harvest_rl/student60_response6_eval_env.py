"""Exact active Teacher60 plant with the unchanged Student command boundary."""
from .student60_camera_eval_env import CameraStudentEvalEnv
from .env import HarvestEnv
from .student60_response6_boundary import apply_response6_plant


class Response6CameraStudentEnv(CameraStudentEvalEnv):
    def original_plant_action(self):
        # Resolve after response6_runtime.__enter__, at every actual physics tick.
        apply_response6_plant(self,HarvestEnv)
