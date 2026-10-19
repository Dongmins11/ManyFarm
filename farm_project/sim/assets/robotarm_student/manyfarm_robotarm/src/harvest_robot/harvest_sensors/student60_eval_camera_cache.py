"""Evaluation-only memoization of constant calibrated image remap grids.

Outputs are bit-identical to the frozen preprocessing. Does not cache camera
images, depth, time, pose, measurements or detections. Original files unchanged.
"""
from functools import lru_cache
import json
from .profile import centred_render_spec as original_spec


@lru_cache(maxsize=16)
def maps(key):
    value=original_spec(json.loads(key))
    for x in value[2:]:x.setflags(write=False)
    return value


def centred_render_spec(spec):
    return maps(json.dumps(spec,sort_keys=True))


def remap_render(array,spec,depth=False):
    import cv2
    w,h,_,mx,my=centred_render_spec(spec)
    if array.shape[:2]!=(h,w):raise ValueError('Rendered image dimensions differ')
    return cv2.remap(array,mx,my,cv2.INTER_NEAREST if depth else cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,borderValue=0)


def install():
    # Module references only, scoped to this evaluation process. No source edits.
    from . import isaac_rig
    isaac_rig.centred_render_spec=centred_render_spec
    isaac_rig.remap_render=remap_render
    import cv2
    cv2.setNumThreads(1)
