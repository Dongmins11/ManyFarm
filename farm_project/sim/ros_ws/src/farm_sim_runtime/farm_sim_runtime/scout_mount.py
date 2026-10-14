"""URDF에서 생성한 장착 USD를 기존 예찰 강체에 참조하고 센서 외부 변환만 갱신합니다."""
from pathlib import Path
import numpy as np


def install_scout_mount(stage: object, project_root: Path, robot_path: str, config: dict) -> None:
    """세션 레이어에 적용. 기존 본체·구동 joint·질량과 카메라 광학 속성을 유지합니다."""
    selected = config.get('scout_mount_asset')
    if not selected:
        if config.get('tag_camera', {}).get('enabled'):
            raise ValueError('예찰 태그 카메라는 scout_mount_asset 장착이 필요합니다.')
        return
    from pxr import UsdGeom, Gf
    asset = (project_root / selected).resolve()
    if not asset.is_relative_to(project_root.resolve()) or not asset.is_file():
        raise FileNotFoundError(asset)
    binding = config['scene_binding']
    def require(relative: str) -> object:
        prim = stage.GetPrimAtPath(robot_path + '/' + relative)
        if not prim.IsValid() or not prim.IsActive():
            raise ValueError('예찰 장착 기준 prim 없음: ' + relative)
        return prim
    body = require(binding['articulation_relative'])
    parent = require(binding['base_link_relative'])
    camera = require(binding['camera_relative'])
    if not camera.IsA(UsdGeom.Camera):
        raise ValueError('기존 예찰 카메라가 USD Camera가 아닙니다.')
    if abs(float(binding.get('control_frame_yaw_rad', 0.))) > 1e-10:
        raise ValueError('이 장착 모델은 Burger의 동일 자산/주행축을 요구합니다.')
    cache = UsdGeom.XformCache()
    def matrix(prim: object) -> np.ndarray:
        return np.asarray(cache.GetLocalToWorldTransform(prim), float).T
    local = np.linalg.inv(matrix(parent)) @ matrix(body)
    if not np.allclose(local[:3,:3].T @ local[:3,:3], np.eye(3), atol=1e-6):
        raise ValueError('예찰 기준 프레임에 비단위 scale이 있습니다.')
    mount_path = str(parent.GetPath()) + '/scout_mount'
    mount = UsdGeom.Xform.Define(stage, mount_path)
    mount.GetPrim().GetReferences().SetReferences([])
    mount.GetPrim().GetReferences().AddReference(str(asset))
    if not stage.GetPrimAtPath(mount_path + '/camera_color_optical_frame').IsValid():
        raise ValueError('장착 USD의 optical 프레임이 없습니다.')
    transform = UsdGeom.Xformable(mount)
    transform.ClearXformOpOrder()
    transform.SetResetXformStack(False)
    transform.AddTransformOp().Set(Gf.Matrix4d(*local.T.flatten().tolist()))
    cache.Clear()
    optical = stage.GetPrimAtPath(mount_path + '/camera_color_optical_frame')
    camera_local = (np.linalg.inv(matrix(camera.GetParent())) @ matrix(optical)
                    @ np.diag([1., -1., -1., 1.]))
    xf = UsdGeom.Xformable(camera)
    xf.ClearXformOpOrder()
    xf.SetResetXformStack(False)
    xf.AddTransformOp().Set(Gf.Matrix4d(*camera_local.T.flatten().tolist()))
    if config.get('tag_camera', {}).get('enabled'):
        # URDF의 PiCam 광학 프레임에 실제 렌더 센서를 부착합니다. D435는 그대로 둡니다.
        optical_path = mount_path + '/picam_optical_frame'
        tag_path = robot_path + '/' + binding['tag_camera_relative']
        base_frame = config['frames']['base_link']
        prefix = base_frame.rsplit('/', 1)[0] + '/' if '/' in base_frame else ''
        if (tag_path != optical_path + '/Camera'
                or config['frames']['tag_camera_optical'] != prefix + 'picam_optical_frame'):
            raise ValueError('태그 카메라 prim/TF는 예찰 PiCam optical 장착 프레임이어야 합니다.')
        require(binding['base_link_relative'] + '/scout_mount/picam_optical_frame')
        tag_camera = UsdGeom.Camera.Define(stage, tag_path)
        tag_xf = UsdGeom.Xformable(tag_camera)
        tag_xf.ClearXformOpOrder()
        tag_xf.SetResetXformStack(False)
        tag_xf.AddTransformOp().Set(Gf.Matrix4d(1., 0., 0., 0., 0., -1., 0., 0.,
                                               0., 0., -1., 0., 0., 0., 0., 1.))
        tag_camera.CreateClippingRangeAttr(Gf.Vec2f(.01, 100.))


def scout_mount_static_tf(stage: object, robot_path: str, config: dict) -> list[dict]:
    """기존 camera_optical 발행은 유지하고 PDF의 body/optical 및 파이캠 TF를 추가합니다."""
    if not config.get('scout_mount_asset'):
        return []
    from pxr import UsdGeom, Gf
    frames = config['frames']
    base = stage.GetPrimAtPath(robot_path + '/' + config['scene_binding']['base_link_relative'])
    cache = UsdGeom.XformCache()
    inverse = np.linalg.inv(np.asarray(cache.GetLocalToWorldTransform(base), float).T)
    prefix = frames['base_link'].rsplit('/', 1)[0] + '/' if '/' in frames['base_link'] else ''
    result = []
    for name in ('bmany_camera_link', 'camera_color_optical_frame', 'picam_frame', 'picam_optical_frame'):
        prim = stage.GetPrimAtPath(str(base.GetPath()) + '/scout_mount/' + name)
        if not prim.IsValid() or not prim.IsActive():
            raise ValueError('예찰 장착 TF prim 없음: ' + name)
        relative = inverse @ np.asarray(cache.GetLocalToWorldTransform(prim), float).T
        q = Gf.Matrix4d(*relative.T.flatten().tolist()).ExtractRotationQuat()
        result.append(dict(parent=frames['base_link'], child=prefix+name,
                           translation=relative[:3,3].tolist(),
                           rotation_xyzw=[*map(float,q.GetImaginary()),float(q.GetReal())]))
    return result
