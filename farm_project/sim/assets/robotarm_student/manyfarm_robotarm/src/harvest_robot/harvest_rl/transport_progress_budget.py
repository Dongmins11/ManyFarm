"""One bounded continuation for an actually progressing, qualified transport."""
import torch


def extension_eligible(timeout,scope,failed,qualified,retained,valid_detach,attached,
                       goal_error,progress_3s,force_min,already_awarded):
    return (timeout & scope & ~failed & qualified & retained & valid_detach & ~attached
            & torch.isfinite(goal_error) & torch.isfinite(progress_3s)
            & (goal_error<.08) & (progress_3s>.008) & (force_min>.5) & ~already_awarded)
