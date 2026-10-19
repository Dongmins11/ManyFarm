"""Preserve the staged expert's exact physics asset for sensor-only collection."""
import copy,hashlib,json
from pathlib import Path


def prepare_deployment_robot(previous, config):
    from pxr import Usd
    from harvest_rl.kinematics import ArmKinematics
    from harvest_rl.settings import ROOT,URDF
    base=Path(previous['usd'])
    if not base.is_file():raise ValueError('Missing preserved Teacher USD; do not substitute current geometry')
    stage=Usd.Stage.Open(str(base))
    sources={str(Path(layer.realPath)):hashlib.sha256(Path(layer.realPath).read_bytes()).hexdigest()
        for layer in stage.GetUsedLayers() if layer.realPath}
    profile_hash=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    key=hashlib.sha256((profile_hash+json.dumps(sources,sort_keys=True)).encode()).hexdigest()
    directory=ROOT/'outputs/harvest_rl/student_deployment_assets'/key[:16]
    directory.mkdir(parents=True,exist_ok=True)
    usd=directory/'harvest_current.usda'
    layer='#usda 1.0\n(\n defaultPrim = "'+stage.GetDefaultPrim().GetName()+'"\n upAxis = "Z"\n metersPerUnit = 1\n subLayers = [@'+str(base.resolve())+'@]\n)\n'
    if not usd.exists():usd.write_text(layer)
    elif usd.read_text()!=layer:raise ValueError('Deployment asset layer changed')
    metadata=copy.deepcopy(previous)
    metadata.update(usd=str(usd),source_urdf=str(URDF),deployment_physics_source=str(base),
        preserved_usd_layers=sources,sensor_mount_reference_urdf_sha256=hashlib.sha256(URDF.read_bytes()).hexdigest(),
        deployment_arm_appearance_sha256=hashlib.sha256((ROOT/'src/harvest_robot/config/arm_appearance.json').read_bytes()).hexdigest(),
        note='Preserved staged Teacher physics USD through read-only sublayer. Current composed URDF is sensor FK only; current box/mount geometry is not substituted.')
    return usd,ArmKinematics(URDF),metadata
