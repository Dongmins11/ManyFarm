"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import math

import torch

def readiness_potential(distance, orientation_error, weight=8., distance_scale=.035,
                        angle_scale_deg=35.):
    # horizontal_grasp_alignment returns a sine projection, not radians.
    angle = torch.asin(orientation_error.clamp(0., 1.))
    return weight*torch.exp(-(distance/distance_scale).square()
                           -(angle/math.radians(angle_scale_deg)).square())
