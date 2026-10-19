"""Compact, deterministic greenhouse scenery. No rigid bodies or collision APIs.

Geometry is separate from fruit/robot/attachment assets. Importable without Isaac;
USD imports are delayed until building/spawning. Ground binding changes appearance
only: the existing ground collider and its physics material stay in place.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / 'src/smartfarm_description/config/harvest_visual_scene.json'


def configuration():
    return json.loads(CONFIG.read_text())


def contract():
    cfg = configuration()
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (CONFIG, Path(__file__), ROOT / cfg['leaf_texture'])}
    sha = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    return dict(version=cfg['version'], sha256=sha, visual_only=True,
                sources=sources, config=cfg)


def geometry(cfg=None):
    """Return four merged meshes; use a private RNG, never episode/layout RNG."""
    cfg = cfg or configuration()
    rng = random.Random(cfg['seed'])
    meshes = {name: dict(points=[], indices=[], counts=[], uv=[])
              for name in ('Bed', 'Soil', 'Trellis', 'Leaves')}

    def face(name, vertices, uv=None):
        m = meshes[name]; first = len(m['points'])
        m['points'].extend(vertices); m['indices'].extend(range(first, first + len(vertices)))
        m['counts'].append(len(vertices))
        if uv is not None: m['uv'].extend(uv)

    def box(name, lo, hi):
        x,y,z = lo; X,Y,Z = hi
        pts = [(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]
        for ids in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
            face(name,[pts[i] for i in ids])

    def rod(start, end, radius, sides=6):
        # All scenery rails are vertical or horizontal along Y (no mesh cylinders).
        dx,dy,dz = (end[i]-start[i] for i in range(3))
        length = math.sqrt(dx*dx+dy*dy+dz*dz)
        if length == 0: return
        d = (dx/length,dy/length,dz/length)
        u = (0.,1.,0.) if abs(d[2])>.99 else (0.,0.,1.)
        v = (d[1]*u[2]-d[2]*u[1], d[2]*u[0]-d[0]*u[2], d[0]*u[1]-d[1]*u[0])
        ring = []
        for origin in (start,end):
            ring.append([tuple(origin[k]+radius*(math.cos(i*2*math.pi/sides)*u[k]+math.sin(i*2*math.pi/sides)*v[k])
                               for k in range(3)) for i in range(sides)])
        for i in range(sides):
            j=(i+1)%sides;face('Trellis',[ring[0][i],ring[0][j],ring[1][j],ring[1][i]])

    front,back = cfg['bed_front_m'],cfg['bed_back_m']
    side=cfg['bed_length_m']/2; height=cfg['bed_height_m']; wall=cfg['bed_wall_m']
    box('Bed',(front,-side,0),(front+wall,side,height))
    box('Bed',(back-wall,-side,0),(back,side,height))
    for y in (-side,side-wall): box('Bed',(front,y,0),(back,y+wall,height))
    box('Soil',(front+wall,-side+wall,height-.035),(back-wall,side-wall,height-.025))
    x=cfg['trellis_front_m'];top=cfg['trellis_top_m']
    for y in (-side,-side/2,0,side/2,side): rod((x,y,height),(x,y,top),.009,8)
    for z in (height+.10,.95,top): rod((x,-side,z),(x,side,z),.008,8)
    spacing=cfg['wire_spacing_m'];r=cfg['wire_radius_m']
    for i in range(int(2*side/spacing)+1):
        y=-side+i*spacing;rod((x,y,height),(x,y,top),r,4)
    for i in range(int((top-height)/spacing)+1):
        z=height+i*spacing;rod((x,-side,z),(x,side,z),r,4)
    u0,u1,v0,v1=cfg['leaf_uv_bounds']
    for row,x in enumerate(cfg['leaf_rows_m']):
        for col in range(cfg['plant_columns']):
            y=(col-(cfg['plant_columns']-1)/2)*cfg['plant_spacing_m']+(row-1)*.07
            rod((x,y,height),(x,y,top-.02),.0035,5)
            for n in range(cfg['leaves_per_plant']):
                h0,h1=cfg['leaf_height_range_m']
                z=h0+(h1-h0)*n/(cfg['leaves_per_plant']-1)+rng.uniform(-.05,.05)
                centre=(x+rng.uniform(-.055,.055),y+(-1 if n%2 else 1)*rng.uniform(.045,.11),z)
                length=rng.uniform(*cfg['leaf_length_range_m']);width=rng.uniform(*cfg['leaf_width_range_m'])
                yaw=rng.uniform(-.75,.75);roll=rng.uniform(-.60,.60)
                # Leaf plane faces the aisle (-X), with individual curvature/tilt.
                across=(math.sin(yaw),math.cos(yaw),0)
                along=(-math.sin(roll)*math.cos(yaw),math.sin(roll)*math.sin(yaw),math.cos(roll))
                normal=(math.cos(yaw),-math.sin(yaw),0)
                vertices=[];uv=[]
                for i in range(7):
                    t=i/6;shape=max(.015,math.sin(math.pi*t)**.65)
                    for sign in (-1,1):
                        w=sign*width*.5*shape;v=(t-.5)*length;bend=.018*math.sin(math.pi*t)
                        vertices.append(tuple(centre[k]+across[k]*w+along[k]*v+normal[k]*bend for k in range(3)))
                        uv.append(((u0+u1)/2+sign*(u1-u0)*.5*shape,v0+(v1-v0)*t))
                for i in range(6):
                    for ids in ((2*i,2*i+1,2*i+3),(2*i,2*i+3,2*i+2)):
                        face('Leaves',[vertices[j] for j in ids],[uv[j] for j in ids])
    return meshes


def _material(stage,path,color,texture=None):
    from pxr import Sdf,UsdShade
    material=UsdShade.Material.Define(stage,path)
    surface=UsdShade.Shader.Define(stage,path+'/Surface');surface.CreateIdAttr('UsdPreviewSurface')
    surface.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(tuple(color))
    surface.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.92)
    surface.CreateOutput('surface',Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput().ConnectToSource(surface.ConnectableAPI(),'surface')
    if texture:
        uv=UsdShade.Shader.Define(stage,path+'/UV');uv.CreateIdAttr('UsdPrimvarReader_float2')
        uv.CreateInput('varname',Sdf.ValueTypeNames.Token).Set('st');uv.CreateOutput('result',Sdf.ValueTypeNames.Float2)
        tex=UsdShade.Shader.Define(stage,path+'/Texture');tex.CreateIdAttr('UsdUVTexture')
        tex.CreateInput('file',Sdf.ValueTypeNames.Asset).Set(texture)
        tex.CreateInput('sourceColorSpace',Sdf.ValueTypeNames.Token).Set('sRGB')
        tex.CreateInput('st',Sdf.ValueTypeNames.Float2).ConnectToSource(uv.ConnectableAPI(),'result')
        tex.CreateOutput('rgb',Sdf.ValueTypeNames.Float3);tex.CreateOutput('a',Sdf.ValueTypeNames.Float)
        surface.GetInput('diffuseColor').ConnectToSource(tex.ConnectableAPI(),'rgb')
        surface.CreateInput('opacity',Sdf.ValueTypeNames.Float).ConnectToSource(tex.ConnectableAPI(),'a')
        surface.CreateInput('opacityThreshold',Sdf.ValueTypeNames.Float).Set(.5)
    return material


def asset():
    from pxr import Usd,UsdGeom,UsdShade,Sdf
    provenance=contract();cfg=provenance['config']
    folder=ROOT/'outputs/harvest_rl/visual_scene_cache'/provenance['sha256']
    folder.mkdir(parents=True,exist_ok=True);path=folder/'greenhouse.usdc'
    if path.exists(): return path,provenance
    # Export to a temporary file then rename, so interrupted generation is not cached.
    temporary=folder/f'greenhouse_{os.getpid()}.usdc'
    stage=Usd.Stage.CreateNew(str(temporary));root=UsdGeom.Xform.Define(stage,'/Greenhouse')
    stage.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z);UsdGeom.SetStageMetersPerUnit(stage,1.)
    texture=os.path.relpath(ROOT/cfg['leaf_texture'],folder)
    colors={'Bed':cfg['bed_color'],'Soil':cfg['soil_color'],'Trellis':cfg['trellis_color'],'Leaves':(1,1,1)}
    data=geometry(cfg)
    for name,m in data.items():
        mesh=UsdGeom.Mesh.Define(stage,'/Greenhouse/'+name)
        mesh.CreatePointsAttr(m['points']);mesh.CreateFaceVertexCountsAttr(m['counts']);mesh.CreateFaceVertexIndicesAttr(m['indices'])
        mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDoubleSidedAttr(True)
        mesh.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(mesh.GetPointsAttr().Get()))
        if m['uv']:
            UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,'vertex').Set(m['uv'])
        material=_material(stage,'/Greenhouse/Looks/'+name,colors[name],texture if name=='Leaves' else None)
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    root.GetPrim().SetCustomDataByKey('visualOnly',True)
    root.GetPrim().SetCustomDataByKey('sourceHash',provenance['sha256'])
    stage.GetRootLayer().Save();temporary.replace(path)
    (folder/'manifest.json').write_text(json.dumps(dict(**provenance,
        meshes={k:dict(vertices=len(v['points']),faces=len(v['counts'])) for k,v in data.items()}),indent=2))
    return path,provenance


def spawn(stage,path,world_from_crop):
    from pxr import Gf,UsdGeom
    usd,provenance=asset()
    root=UsdGeom.Xform.Define(stage,path);root.GetPrim().GetReferences().AddReference(str(usd))
    # Gf uses row vectors; input is the usual robotics column-vector transform.
    matrix=Gf.Matrix4d(*[float(world_from_crop[j][i]) for i in range(4) for j in range(4)])
    root.AddTransformOp().Set(matrix);root.GetPrim().SetInstanceable(True)
    return dict(**provenance,world_from_crop=[[float(x) for x in row] for row in world_from_crop])


def gray_ground(stage,path='/World/Ground'):
    from pxr import Usd,UsdGeom,UsdShade
    material=_material(stage,path+'/Looks/HarvestGrayFloor',configuration()['floor_color'])
    for prim in Usd.PrimRange(stage.GetPrimAtPath(path)):
        if prim.IsA(UsdGeom.Mesh):
            # All-purpose visual binding leaves the physics-purpose binding untouched.
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,bindingStrength=UsdShade.Tokens.strongerThanDescendants)
