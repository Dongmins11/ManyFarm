"""Pure target selection for sequential harvesting; green is never eligible."""
import torch


def fruit_colors(count, sequential):
    return [("Red", "Yellow", "Green")[i % 3] if sequential else ("Red" if i == 0 else "Green") for i in range(count)]


def next_target(positions, tcp, ripe, collected):
    eligible = ripe & ~collected
    distances = (positions-tcp[:,None,:]).norm(dim=-1)
    distances = distances.masked_fill(~eligible,float("inf"))
    return distances.argmin(-1), eligible.any(-1)


def forbidden_detach(attached, collected, target):
    indices = torch.arange(attached.shape[1],device=attached.device)[None,:]
    return ((~attached) & ~collected & (indices != target[:,None])).any(-1)


def sample_color_ids(num_envs, num_fruits, device):
    """Uniform RGB-class draws conditioned on at least one harvestable fruit.

    0=red, 1=yellow, 2=green. Counts and slot assignments vary independently by env.
    """
    colors = torch.randint(3,(num_envs,num_fruits),device=device)
    empty = (colors == 2).all(-1)
    while bool(empty.any()):
        colors[empty] = torch.randint(3,(int(empty.sum()),num_fruits),device=device)
        empty = (colors == 2).all(-1)
    return colors


def target_elapsed(episode_steps, target_start, per_fruit):
    return episode_steps-target_start if per_fruit else episode_steps


def random_target(ripe, collected):
    eligible = ripe & ~collected
    scores = torch.rand(eligible.shape,device=eligible.device).masked_fill(~eligible,-1.)
    return scores.argmax(-1), eligible.any(-1)


def sample_separated(candidates, count, picked, spacing, chunk_size=256):
    """Uniform choice among eligible bank points per row; bounded GPU scratch."""
    if count == 0:
        return candidates.new_empty((0,3))
    result=[]
    for start in range(0,count,chunk_size):
        end=min(start+chunk_size,count)
        available=torch.ones((end-start,len(candidates)),dtype=torch.bool,device=candidates.device)
        for previous in picked:
            available &= (candidates[None]-previous[start:end,None]).norm(dim=-1) > spacing
        if not bool(available.any(-1).all()):
            raise RuntimeError('Fruit packing failed; reduce --num-fruits or increase --curriculum')
        indices=torch.multinomial(available.float(),1).squeeze(-1)
        result.append(candidates[indices])
    return torch.cat(result)
