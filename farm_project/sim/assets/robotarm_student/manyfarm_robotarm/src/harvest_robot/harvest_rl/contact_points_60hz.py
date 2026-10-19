"""Read-only detailed contact recording, separate from the control sensors."""
import numpy as np
import torch

POINTS_PER_SENSOR_FILTER = 128
RECORDING = dict(schema='teacher60_contact_points_v2', separate_recording_view=True,
    points_per_sensor_filter=POINTS_PER_SENSOR_FILTER, control_sensor_unchanged=True,
    overflow='Mark the frame incomplete; do not fabricate points or stop the control probe.')


def recording_views(env, simulation_view=None):
    """Allocate recording storage only; never replace/mutate ContactSensor views.

    Isaac Lab defaults to four detailed points per body (128 total for 32
    environments). Mesh contacts can exceed that even though the original
    aggregate force matrix used for control remains available.
    """
    if simulation_view is None:
        from isaacsim.core.simulation_manager import SimulationManager
        simulation_view = SimulationManager.get_physics_sim_view()
    views, metadata = {}, dict(recording=RECORDING.copy(), jaws={})
    for name, sensor in [('fixed', env.fixed_contact), ('moving', env.moving_contact)]:
        original = sensor.contact_physx_view
        capacity = POINTS_PER_SENSOR_FILTER * original.sensor_count * original.filter_count
        if original.sensor_count != env.num_envs or original.filter_count != env.settings.num_fruits:
            raise ValueError('Expected one jaw body per environment and Fruit_0..Fruit_N filters')
        view = simulation_view.create_rigid_contact_view(
            sensor.cfg.prim_path.replace('.*', '*'),
            filter_patterns=[p.replace('.*', '*') for p in sensor.cfg.filter_prim_paths_expr],
            max_contact_data_count=capacity)
        if (view.sensor_count != original.sensor_count or view.filter_count != original.filter_count
                or view.sensor_paths != original.sensor_paths or view.filter_paths != original.filter_paths
                or list(view.sensor_paths) != list(sensor.body_physx_view.prim_paths)
                or view.max_contact_data_count != capacity):
            raise ValueError('Recording view paths/order/capacity differ from the control sensor')
        views[name] = view
        metadata['jaws'][name] = dict(control_buffer_capacity=original.max_contact_data_count,
            recording_buffer_capacity=capacity, sensor_paths=list(view.sensor_paths), filter_paths=view.filter_paths)
    return views, metadata


def array(value):
    return value.detach().cpu().numpy().copy() if isinstance(value, torch.Tensor) else np.array(value, copy=True)


def local_points(points, position, quat_wxyz):
    from scipy.spatial.transform import Rotation
    return (points - position) @ Rotation.from_quat(quat_wxyz[[1, 2, 3, 0]]).as_matrix()


def read_sensor(sensor, env, fruit_pos, fruit_quat, *, view=None):
    """Detailed contacts are the last physics substep, not a 20Hz mean.

    Production probes supply a separate, larger recording view. Saturation or
    invalid packed ranges mark the frame unavailable instead of indexing outside
    the buffer. Unavailable diagnostic data must not be called "no contact".
    """
    view = sensor.contact_physx_view if view is None else view
    force, points, normals, distances, counts, starts = map(array, view.get_contact_data(dt=env.physics_dt))
    transforms = array(sensor.body_physx_view.get_transforms())
    if counts.shape != (env.num_envs, env.settings.num_fruits) or starts.shape != counts.shape or transforms.shape != (env.num_envs, 7):
        raise ValueError('Expected exactly one jaw body per environment')
    target = array(env.target_index).astype(int)
    if target.shape != (env.num_envs,) or (target < 0).any() or (target >= counts.shape[1]).any():
        raise ValueError('Invalid target filter indices')
    origins = array(env.scene.env_origins)
    capacity = len(points)
    if points.shape != (capacity, 3) or normals.shape != (capacity, 3) or force.size != capacity or distances.size != capacity:
        raise ValueError('Inconsistent packed contact array lengths')
    total = sum(int(c) for c in counts.flat)
    # Check ALL pairs, including non-target filters. An overflow can invalidate
    # the whole packed buffer, even when a target's range appears in bounds.
    bad_ranges = any(int(c) < 0 or (int(c) > 0 and (int(s) < 0 or int(s)+int(c) > capacity))
        for s, c in zip(starts.flat, counts.flat))
    saturated = total >= capacity
    complete = not (saturated or bad_ranges)
    result = []
    for i in range(env.num_envs):
        start, reported_count = int(starts[i, target[i]]), int(counts[i, target[i]])
        count = reported_count if complete else 0
        if count == 0:
            start = 0  # Empty pairs need not have a valid start-index sentinel.
        selected = points[start:start+count]
        f = force[start:start+count].reshape(-1)
        norm = normals[start:start+count]
        sep = distances[start:start+count].reshape(-1)
        if not all(np.isfinite(x).all() for x in (selected, f, norm, sep, transforms[i])):
            raise ValueError('Nonfinite contact data')
        body = transforms[i]
        result.append(dict(count=count, reported_count=reported_count, data_complete=complete,
            point_data_available=complete and count > 0,
            unavailable_reason='contact_buffer_incomplete' if not complete else None,
            buffer_capacity=capacity, buffer_saturated=saturated, buffer_invalid_ranges=bad_ranges,
            points_policy_world_m=(selected - origins[i]).tolist(),
            points_jaw_local_m=local_points(selected, body[:3], body[[6, 3, 4, 5]]).tolist(),
            points_fruit_local_m=local_points(selected, fruit_pos[i], fruit_quat[i]).tolist(),
            normal_forces_N=f.tolist(), normals_world=norm.tolist(), separation_m=sep.tolist(),
            normal_force_sum_world_N=(norm * f[:, None]).sum(0).tolist() if complete else None,
            jaw_pose_policy_world_xyzw=np.r_[body[:3] - origins[i], body[3:]].tolist()))
    return result


def capture_contact_points(env, views):
    fruit = env._target_fruit().data
    pos, quat = array(fruit.root_link_pos_w), array(fruit.root_link_quat_w)
    return dict(fixed=read_sensor(env.fixed_contact, env, pos, quat, view=views['fixed']),
                moving=read_sensor(env.moving_contact, env, pos, quat, view=views['moving']))


def point_summary(env, contacts):
    """Finite trace columns; missing centroids are explicitly marked unavailable."""
    result = {}
    for name, rows in contacts.items():
        centroids = [np.mean(r['points_fruit_local_m'], axis=0) if r['count'] else np.zeros(3) for r in rows]
        result[f'{name}_point_available'] = torch.tensor([r['point_data_available'] for r in rows], device=env.device)
        result[f'{name}_point_data_complete'] = torch.tensor([r['data_complete'] for r in rows], device=env.device)
        result[f'{name}_point_count'] = torch.tensor([r['count'] for r in rows], device=env.device)
        for j, axis in enumerate('xyz'):
            result[f'{name}_point_fruit_{axis}_m'] = torch.tensor([p[j] for p in centroids], device=env.device)
        result[f'{name}_point_buffer_saturated'] = torch.tensor([r['buffer_saturated'] for r in rows], device=env.device)
    return result
