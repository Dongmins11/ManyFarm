"""Current observation provenance check without loading Isaac or running policies."""
import json
from .settings import ROOT
from .current_robot import current_input_sources
from .visual_scene import contract as visual_contract
import hashlib


def current_observation_contract():
    from harvest_vision.workspace import load_workspace
    _,selection=load_workspace()
    sources=current_input_sources()
    return dict(robot_asset_sha256=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest(),
        camera_config=json.loads((ROOT/'src/harvest_robot/config/d435_nominal.json').read_text()),
        visual_scene_sha256=visual_contract()['sha256'],observation_geometry_schema='arm_tcp_v1',
        initial_target_workspace=selection)


def require_current_observations(contract):
    if contract.get('student_schema_version')==3:
        from .settings import URDF
        from harvest_sensors.deployment import validate_deployment,CAPTURE_CONTRACT
        expected=json.loads((ROOT/'src/harvest_robot/config/d435_deployment_20261013_overhead30.json').read_text())
        validate_deployment(expected)
        if contract['camera_config']!=expected or contract['capture_contract']!=CAPTURE_CONTRACT:
            raise ValueError('Current multimodal sensor/time contract mismatch')
        if contract.get('sensor_mount_reference_urdf_sha256')!=hashlib.sha256(URDF.read_bytes()).hexdigest():
            raise ValueError('Current sensor mount reference changed')
        if contract.get('deployment_arm_appearance_sha256')!=hashlib.sha256((ROOT/'src/harvest_robot/config/arm_appearance.json').read_bytes()).hexdigest():
            raise ValueError('Current arm appearance changed')
        if contract.get('visual_scene_sha256')!=visual_contract()['sha256']:
            raise ValueError('Current Student background changed')
        if abs(contract['control_dt']-.05)>1e-8:raise ValueError('Require20Hz controller')
        return expected
    expected=current_observation_contract()
    for k,v in expected.items():
        if contract.get(k)!=v:raise ValueError(f'Current Student data mismatch: {k}; collect new camera/background demonstrations')
    if abs(contract['control_dt']-.05)>1e-8:raise ValueError('Require existing 20 Hz policy contract')
    if abs(contract['teacher_runtime']['mass']-.009)>1e-8:raise ValueError('Require explicit 9 g demonstration contract')
    return expected
