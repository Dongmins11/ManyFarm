"""시뮬 설정의 태그와 PCWEB400 광학 프레임을 USD session layer에 장착합니다."""
import json
from pathlib import Path
import numpy as np


def mount_camera(stage: object, robot_path: str, config: dict) -> None:
    """논리 주행축→자산축→실제 base_link 순서로 optical 변환을 적용합니다."""
    from pxr import UsdGeom, Gf
    from farm_sim_devices.control_frame import asset_from_control
    camera = config['camera']
    if not camera.get('enabled') or 'T_base_optical' not in camera:
        return
    binding = config['scene_binding']
    cache = UsdGeom.XformCache()
    def world(relative: str) -> np.ndarray:
        prim = stage.GetPrimAtPath(robot_path+'/'+relative)
        if not prim.IsValid():
            raise ValueError(f'카메라 장착 부모 없음: {relative}')
        return np.asarray(cache.GetLocalToWorldTransform(prim), float).T
    parent = binding['camera_relative'].rsplit('/', 1)[0]
    transform = (np.linalg.inv(world(parent)) @ world(binding['articulation_relative'])
                 @ asset_from_control(binding) @ np.array(camera['T_base_optical'])
                 @ np.diag([1., -1., -1., 1.]))
    prim = UsdGeom.Camera.Define(stage, robot_path+'/'+binding['camera_relative'])
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    xform.AddTransformOp().Set(Gf.Matrix4d(*transform.T.flatten().tolist()))
    prim.CreateClippingRangeAttr(Gf.Vec2f(.01, 100.))


def install_tags(stage: object, project_root: Path, config: dict) -> int:
    """map 좌표를 world로 변환하고, 앞면만 보이는 실제 크기 평면에 PNG를 붙입니다."""
    from pxr import UsdGeom, UsdShade, Sdf, Gf
    selected = config.get('apriltag_map')
    if not selected:
        return 0
    data = json.loads((project_root/selected).read_text())
    if data['map_id'] != config['map_id']:
        raise ValueError('AprilTag 지도 ID 불일치')
    root = '/World/AprilTags'
    if stage.GetPrimAtPath(root).IsValid():
        return 0  # fleet에서 여러 로봇이 같은 배치표를 선택할 수 있습니다.
    UsdGeom.Xform.Define(stage, root)
    world_map = np.linalg.inv(np.asarray(data['T_map_world'], float))
    for tag in data['tags']:
        if not stage.GetPrimAtPath(tag['wall_prim']).IsValid():
            raise ValueError(f"태그 장착 벽 없음: {tag['wall_prim']}")
        texture = (project_root/tag['texture']).resolve()
        if not texture.is_file():
            raise FileNotFoundError(texture)
        path = f"{root}/{tag['section_id']}/Tag_{tag['id']}"
        mesh = UsdGeom.Mesh.Define(stage, path)
        width, height = tag['paper_size_m']
        center = np.asarray(tag['paper_center_map_m'])
        right = np.asarray(tag['right_map'])
        up = np.array([0., 0., 1.])
        points = [center+right*x*width/2+up*y*height/2
                  for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        mesh.CreatePointsAttr([Gf.Vec3f(*(world_map@np.r_[p,1.])[:3]) for p in points])
        mesh.CreateFaceVertexCountsAttr([4]); mesh.CreateFaceVertexIndicesAttr([0,1,2,3])
        mesh.CreateSubdivisionSchemeAttr('none'); mesh.CreateDoubleSidedAttr(False)
        uv = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, 'vertex')
        uv.Set([(0,0),(1,0),(1,1),(0,1)])
        material = UsdShade.Material.Define(stage, path+'/Material')
        shader = UsdShade.Shader.Define(stage, path+'/Material/Surface')
        shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(1.)
        shader.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(0.)
        tex = UsdShade.Shader.Define(stage, path+'/Material/Texture')
        tex.CreateIdAttr('UsdUVTexture')
        tex.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(str(texture))
        tex.CreateInput('sourceColorSpace', Sdf.ValueTypeNames.Token).Set('sRGB')
        reader = UsdShade.Shader.Define(stage, path+'/Material/UV')
        reader.CreateIdAttr('UsdPrimvarReader_float2')
        reader.CreateInput('varname', Sdf.ValueTypeNames.Token).Set('st')
        tex.CreateInput('st', Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), 'result')
        shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), 'rgb')
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
        mesh.GetPrim().CreateAttribute('apriltag:id', Sdf.ValueTypeNames.Int).Set(tag['id'])
    return len(data['tags'])
