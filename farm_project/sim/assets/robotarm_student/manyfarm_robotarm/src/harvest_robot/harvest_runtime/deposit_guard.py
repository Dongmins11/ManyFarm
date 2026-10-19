"""Use the task's own geometric containment predicate for retained deposits."""
def still_in_box(fruit,env):
    import torch
    from harvest_rl.logic import placement_contained, mesh_settled_in_box
    position=fruit.data.root_link_pos_w-env.scene.env_origins
    velocity=torch.zeros_like(position)  # retention checks position, not settling again
    if env.settings.attachment_version==4 and env.settings.stem_response_version>=2:
        slot=next(i for i,item in enumerate(env.fruits) if item is fruit)
        return bool(mesh_settled_in_box(position,fruit.data.root_link_quat_w,velocity,
                                       env.fruit_collision_hulls[slot],env.settings)[0])
    return bool(placement_contained(position,fruit.data.root_link_quat_w,velocity,env.settings)[0])
