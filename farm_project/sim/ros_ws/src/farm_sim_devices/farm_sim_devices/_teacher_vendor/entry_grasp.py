"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def entry_state(local_center, jaw_q):
    # Local X is finger closure; TCP is 85 mm along the fixed finger.
    # Opposing pad reference rotates around URDF pivot (x=.0202,z=-.0234).
    gap=.0281*(1-torch.cos(jaw_q))+.0616*torch.sin(jaw_q)
    aligned=(local_center[:,1].abs()<=.012)&(local_center[:,2].abs()<=.012)&(local_center[:,0].abs()<=.012)
    # TCP is positioned half a nominal fruit diameter from the fixed pad.
    return aligned, gap

def entry_gate(local_center, half_width, jaw_q, previous, diameter):
    aligned,gap=entry_state(local_center,jaw_q)
    x=local_center[:,0]+diameter/2
    fits=(x-half_width>=-.002)&(x+half_width<=gap+.002)
    entered=aligned & (previous | fits)
    return entered,gap
