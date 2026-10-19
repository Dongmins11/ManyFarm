"""Separate sensor reference / preview cache for the opt-in U20 URDF."""
import hashlib,json
from pathlib import Path
from .u20_deployment import reference_urdf

def prepare_deployment_robot(previous,config):
    from .deployment_asset import prepare_deployment_robot as preserve_teacher
    from harvest_rl.kinematics import ArmKinematics
    usd,_,metadata=preserve_teacher(previous,config)
    path=reference_urdf(config)
    frozen_urdf=Path(previous['usd']).with_suffix('.urdf')
    if not frozen_urdf.is_file():raise ValueError('Missing original frozen URDF for merged left camera matching')
    metadata.update(source_urdf=str(path),sensor_mount_reference_urdf_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        frozen_visual_reference_urdf=str(frozen_urdf),frozen_visual_reference_urdf_sha256=hashlib.sha256(frozen_urdf.read_bytes()).hexdigest(),
        sensor_variant=config['revision'],
        note='Teacher physics retained unchanged; both wrist CAD visuals and right camera FK use the separate U20 URDF. New URDF camera masses/collisions are not silently substituted into the frozen Teacher physics.')
    return usd,ArmKinematics(path),metadata

def prepare_preview_robot(config):
    import xml.etree.ElementTree as ET
    from isaaclab.sim.converters import UrdfConverter,UrdfConverterCfg
    from harvest_rl.kinematics import ArmKinematics
    from harvest_rl.settings import ROOT
    path=reference_urdf(config);root=ET.parse(path);sources={str(path):hashlib.sha256(path.read_bytes()).hexdigest()}
    for mesh in root.findall('.//mesh'):
        name=mesh.get('filename')
        file=ROOT/'src/smartfarm_description'/name.split('package://smartfarm_description/',1)[1] if name.startswith('package://smartfarm_description/') else (path.parent/name).resolve()
        sources[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest();mesh.set('filename',str(file))
    for joint in root.findall('joint'):
        if joint.get('type')!='fixed' and not joint.get('name','').startswith('arm_2/'):
            joint.set('type','fixed')
            for tag in ('axis','limit','dynamics','mimic'):
                for child in joint.findall(tag):joint.remove(child)
    key=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    dest=ROOT/'outputs/harvest_rl/u20_preview_assets'/key[:16];dest.mkdir(parents=True,exist_ok=True)
    derived=dest/'harvest_u20.urdf'
    if not derived.exists():root.write(derived,encoding='utf-8',xml_declaration=True)
    converter=UrdfConverter(UrdfConverterCfg(asset_path=str(derived),usd_dir=str(dest),usd_file_name='harvest_u20.usd',
        force_usd_conversion=not (dest/'manifest.json').exists(),fix_base=True,merge_fixed_joints=True,
        self_collision=True,make_instanceable=False,collider_type='convex_decomposition',
        joint_drive=UrdfConverterCfg.JointDriveCfg(gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=25.,damping=1.5))))
    meta=dict(source_urdf=str(path),source_files=sources,asset_input_sha256=key,usd=str(converter.usd_path),preview_only=True)
    (dest/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    return Path(converter.usd_path),ArmKinematics(path),meta
