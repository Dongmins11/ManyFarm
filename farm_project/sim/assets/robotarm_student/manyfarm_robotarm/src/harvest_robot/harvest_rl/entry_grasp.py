"""SO101 entry-first grasp shaping. Calibrated envelope, not a mesh collision test."""
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


def entry_cost(entered, attached, distance, fixed_force, moving_force, closing,
               displacement, gap, diameter, dt):
    approaching=attached & ~entered & (distance<.10)
    contact=(fixed_force+moving_force-.10).clamp(0,3.)
    pushing=(displacement/.02).square().clamp(max=4.)
    early_close=closing.clamp(0,1)
    insufficient_open=((diameter+.004-gap)/.02).clamp(0,2.)
    return dt*approaching.float()*(2.*contact+2.*pushing+early_close+insufficient_open)


def capture_cost(attached, confirmed, distance, fixed_force, moving_force,
                 displacement, dt):
    """Until bilateral capture is confirmed, entry alone must not license pushing.

    Keep grip/contact/break tests unchanged. Thresholds are shaping parameters,
    not new physical separation conditions. No cost after confirmed capture.
    """
    unconfirmed=attached & ~confirmed & (distance<.10)
    imbalance=(fixed_force-moving_force).abs().sub(.10).clamp(0,3.)
    disturbed=((displacement-.005).clamp_min(0)/.020).square().clamp(max=4.)
    return dt*unconfirmed.float()*(2.*imbalance+4.*disturbed)
