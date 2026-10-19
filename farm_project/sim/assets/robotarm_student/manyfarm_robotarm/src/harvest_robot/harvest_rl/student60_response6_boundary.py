"""Dispatch the active response6 plant dynamically, never a pre-context method."""


def apply_response6_plant(env,plant_type):
    callback=plant_type._apply_action
    if (callback.__module__!='harvest_rl.attachment_60hz_runtime'
            or callback.__qualname__!='response6_runtime.<locals>.apply'
            or env.settings.stem_response_version!=6):
        raise RuntimeError('Student must execute the active Teacher response6 physical plant')
    # The adapter itself checks that one coupled wrench was evaluated for every
    # fruit. This call retains the Student command and invokes no Teacher actor.
    callback(env)
    env.response6_physics_calls=getattr(env,'response6_physics_calls',0)+1
