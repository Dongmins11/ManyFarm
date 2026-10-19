"""Build a separate current-URDF preview/evaluation asset; never touch legacy teacher cache."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
from .settings import ROOT, URDF

CURRENT_CACHE=ROOT/'outputs/harvest_rl/current_robot'


def current_input_sources():
    """Same asset fingerprint as conversion; safe before SimulationApp starts."""
    paths=[URDF,ROOT/'src/harvest_robot/config/arm_appearance.json']
    for mesh in ET.parse(URDF).getroot().findall('.//mesh'):
        name=mesh.get('filename')
        path=(ROOT/'src/smartfarm_description'/name.split('package://smartfarm_description/',1)[1]
              if name.startswith('package://smartfarm_description/') else (URDF.parent/name).resolve())
        paths.append(path)
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def prepare_current_robot():
    # Import only after AppLauncher. This derivative preserves all visuals and
    # camera frames; wheels, inactive arm and lid mechanisms are fixed for preview.
    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg
    from .kinematics import ArmKinematics
    root=ET.parse(URDF)
    sources=current_input_sources()
    appearance_path=ROOT/'src/harvest_robot/config/arm_appearance.json'
    appearance=json.loads(appearance_path.read_text())
    sources[str(appearance_path.relative_to(ROOT))]=hashlib.sha256(appearance_path.read_bytes()).hexdigest()
    # Override only named arm visuals in the derivative; source URDF is untouched.
    for material in root.findall('material'):
        if material.get('name') in appearance['materials']:
            color=material.find('color')
            if color is None:color=ET.SubElement(material,'color')
            color.set('rgba',' '.join(map(str,appearance['rgba'])))
    for mesh in root.findall('.//mesh'):
        filename=mesh.get('filename')
        if filename.startswith('package://smartfarm_description/'):
            path=ROOT/'src/smartfarm_description'/filename.split('package://smartfarm_description/',1)[1]
        else:
            path=(URDF.parent/filename).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        mesh.set('filename',str(path))
        sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    for joint in root.findall('joint'):
        if joint.get('type')!='fixed' and not joint.get('name','').startswith('arm_2/'):
            joint.set('type','fixed')
            for tag in ('axis','limit','dynamics','mimic'):
                for child in joint.findall(tag):joint.remove(child)
    digest=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    destination=CURRENT_CACHE/digest[:16]
    destination.mkdir(parents=True,exist_ok=True)
    derived=destination/'harvest_current.urdf'
    if not derived.exists():root.write(derived,encoding='utf-8',xml_declaration=True)
    converter=UrdfConverter(UrdfConverterCfg(asset_path=str(derived),usd_dir=str(destination),
        usd_file_name='harvest_current.usd',force_usd_conversion=not (destination/'manifest.json').exists(),
        fix_base=True,merge_fixed_joints=True,self_collision=True,make_instanceable=False,
        collider_type='convex_decomposition',
        joint_drive=UrdfConverterCfg.JointDriveCfg(gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=25.,damping=1.5))))
    metadata=dict(source_urdf=str(URDF),source_sha256=sources[str(URDF.relative_to(ROOT))],
                  asset_input_sha256=digest,source_files=sources,usd=str(converter.usd_path),
                  note='Current robot asset, not the legacy teacher workspace. Inactive joints fixed at URDF zero.')
    (destination/'manifest.json').write_text(json.dumps(metadata,indent=2))
    return Path(converter.usd_path),ArmKinematics(URDF),metadata


def appearance_only_change(previous, current):
    """Verify unchanged source geometry/meshes AND identical derived non-material XML."""
    appearance='src/harvest_robot/config/arm_appearance.json'
    old={k:v for k,v in previous['source_files'].items() if k!=appearance}
    new={k:v for k,v in current['source_files'].items() if k!=appearance}
    if old!=new: return False
    def structural(meta):
        path=Path(meta['usd']).with_suffix('.urdf')
        # Checkpoint provenance may contain the producer's absolute path.
        # Keep metadata/hash intact; read the preserved cache in this checkout.
        marker='outputs/harvest_rl/current_robot/'
        if marker in str(path):
            relocated=ROOT/marker/str(path).split(marker,1)[1]
            if relocated.is_file():path=relocated
        if not path.is_file(): return None
        root=ET.parse(path).getroot()
        for material in list(root.findall('material')):
            if material.get('name') in ('arm_1/3d_printed','arm_2/3d_printed','arm_1/sts3215','arm_2/sts3215'):
                root.remove(material)
        return ET.tostring(root)
    a,b=structural(previous),structural(current)
    return a is not None and a==b


def wrist_mount_only_change(previous,current):
    """Allow four fixed wrist mount/body origins and arm colors ONLY, by explicit opt-in.

    Camera mass/collision placement changes and requires evaluation. This is not
    an assertion that dynamics are identical, and never permits arm/box geometry.
    """
    appearance='src/harvest_robot/config/arm_appearance.json'
    urdf=str(URDF.relative_to(ROOT))
    old={k:v for k,v in previous['source_files'].items() if k not in (appearance,urdf)}
    new={k:v for k,v in current['source_files'].items() if k not in (appearance,urdf)}
    if old!=new:return False
    names={f'arm_{arm}/{name}' for arm in (1,2) for name in ('wrist_camera_mount_link_joint','wrist_camera_joint')}
    def structural(meta):
        path=Path(meta['usd']).with_suffix('.urdf');marker='outputs/harvest_rl/current_robot/'
        if marker in str(path):
            relocated=ROOT/marker/str(path).split(marker,1)[1]
            if relocated.is_file():path=relocated
        if not path.is_file():return None
        root=ET.parse(path).getroot();found=set()
        for material in list(root.findall('material')):
            if material.get('name') in ('arm_1/3d_printed','arm_2/3d_printed','arm_1/sts3215','arm_2/sts3215'):root.remove(material)
        for joint in root.findall('joint'):
            if joint.get('name') in names:
                if joint.get('type')!='fixed':return None
                origin=joint.find('origin')
                if origin is None or set(origin.attrib)-{'xyz','rpy'}:return None
                origin.set('xyz','0 0 0');origin.set('rpy','0 0 0');found.add(joint.get('name'))
        if found!=names:return None
        return ET.tostring(root)
    a,b=structural(previous),structural(current)
    return a is not None and a==b
