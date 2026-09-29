"""Deterministic, non-destructive USD scene composition. Units: metres, Z-up.
Build-only requires numpy + usd-core; Isaac Sim already supplies them.
Extra foliage: one additional Part_1 copy per tree by default, with varied
rotation, height and uniform scale. No vertical squash or fixed-height band.
Leaves remain inside Bed_Edge fruit rows; density target varies 72..110 cm.
Set extra_foliage_copies_per_tree to change the copy count (default 1).
Original trees and fruit placement are unchanged; only added foliage is fitted.
Optional config.json keys (also supported in bed_overrides):
  "extra_foliage_enabled": true,
  "extra_foliage_angles_deg": [120.0, 240.0]
Fruit CENTER placement: left/right Bed_Edge OUTER face +/- 0.05 m; vicpinky deck TOP -0.10..+0.35 m.
Fixed numeric height: deck top = 0.73 m above ground datum (world Z=0).
Fruit centers use world Z=0.63..1.08 m. No robot/deck lookup is performed.
Legacy fruit_center_height_above_soil_m and wire_clearance_m do not set fruit
positions anymore. Ranges constrain fruit centers, not the entire fruit mesh.
Copies are permanent USD content under Tree_XXX/ExtraFoliage, not Session Layer.
Run the normal build command once; --open-only does not regenerate foliage.
"""
import hashlib
import itertools
import json
import math
import os
import re
from pathlib import Path
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt
ROOT=Path(__file__).resolve().parent
COLORS={'green':'Pepper_Green','red':'Pepper_Red','yellow':'Pepper_Yellow'}

def relative(path, directory):
    return os.path.relpath(path,directory).replace(os.sep,'/')

def bounds(cache,prim):
    r=cache.ComputeLocalBound(prim).ComputeAlignedRange()
    return np.array(r.GetMin()),np.array(r.GetMax())

def transform_points(points,matrix):
    points=np.asarray(points,dtype=float)
    homogeneous=np.column_stack((points,np.ones(len(points)))) @ np.array(matrix)
    return homogeneous[:,:3]/homogeneous[:,3:4]


def bed_edge_limits(stage, cache, bed_prim, matrix, soil_local):
    """Match the two longitudinal Bed_Edge objects to this bed in bed space.
    Use the left object's MIN X and right object's MAX X, not their origins.
    Transform the bound exactly once (BBox range + BBox matrix).
    """
    soil_lo, soil_hi = soil_local.min(axis=0), soil_local.max(axis=0)
    mid_x = (soil_lo[0]+soil_hi[0])/2
    soil_length = soil_hi[1]-soil_lo[1]
    choices = {-1: [], 1: []}
    for edge in stage.Traverse():
        if not re.search(r'bed_edge', edge.GetName(), re.I):
            continue
        # A named parent already encompasses its named child geometry.
        ancestor = edge.GetParent()
        nested = False
        while ancestor and not ancestor.IsPseudoRoot():
            if re.search(r'bed_edge', ancestor.GetName(), re.I):
                nested = True
                break
            ancestor = ancestor.GetParent()
        if nested:
            continue
        bb = cache.ComputeWorldBound(edge)
        extent = bb.GetRange()
        if extent.IsEmpty():
            continue
        corners = np.array(list(itertools.product(*zip(extent.GetMin(), extent.GetMax()))))
        pts = transform_points(corners, bb.GetMatrix()*matrix.GetInverse())
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        overlap = min(hi[1],soil_hi[1])-max(lo[1],soil_lo[1])
        if soil_length <= 0 or overlap < 0.5*soil_length:
            continue
        # Match longitudinal side walls, not the short head/end walls.
        if hi[1]-lo[1] <= hi[0]-lo[0]:
            continue
        center_x = (lo[0]+hi[0])/2
        side = -1 if center_x < mid_x else 1
        if lo[0] <= mid_x <= hi[0]:
            continue
        target_x = soil_lo[0] if side < 0 else soil_hi[0]
        score = (abs(center_x-target_x)
                 + abs((lo[1]+hi[1]-soil_lo[1]-soil_hi[1])/2))
        choices[side].append((score, str(edge.GetPath()), float(lo[0]), float(hi[0])))
    result = {}
    for side, label in [(-1,'left'),(1,'right')]:
        ordered = sorted(choices[side])
        if not ordered:
            raise ValueError(f'{bed_prim.GetPath()}: no matching {label} Bed_Edge. No trellis fallback.')
        if len(ordered)>1 and abs(ordered[0][0]-ordered[1][0]) < 1e-6:
            raise ValueError(f'{bed_prim.GetPath()}: ambiguous {label} Bed_Edge: {ordered[:2]}')
        _, path, lo_x, hi_x = ordered[0]
        result[label+'_edge_x'] = lo_x if side < 0 else hi_x
        result[label+'_edge_path'] = path
    print(f"Bed {bed_prim.GetPath()}: LEFT {result['left_edge_path']} outer X={result['left_edge_x']:.4f}, "
          f"RIGHT {result['right_edge_path']} outer X={result['right_edge_x']:.4f} (bed local metres)")
    return result

def find_beds(stage,cfg):
    if UsdGeom.GetStageUpAxis(stage)!='Z' or abs(UsdGeom.GetStageMetersPerUnit(stage)-1)>1e-8:
        raise ValueError('Background must use Z-up and metres, as supplied.')
    cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render'])
    xf=UsdGeom.XformCache();beds=[]
    for p in stage.Traverse():
        match=re.fullmatch(r'Trellis_Frame_(\d+)',p.GetName())
        if not match or p.GetTypeName()!='Xform':continue
        i=int(match[1]);matrix=xf.GetLocalToWorldTransform(p)
        # Rigid XY rotation/translation is supported; reject non-unit scales or tilt.
        a=np.array(matrix)[:3,:3]
        if not np.allclose(a@a.T,np.eye(3),atol=1e-5) or not np.allclose(a[2],[0,0,1],atol=1e-5):
            raise ValueError(f'{p.GetPath()}: tilted/scaled beds require adaptation')
        lo,hi=bounds(cache,p);soil=stage.GetPrimAtPath(p.GetParent().GetPath().AppendChild(f'Soil_Surface_{i}'))
        if not soil:raise ValueError(f'Missing Soil_Surface_{i}')
        soil_bb=cache.ComputeWorldBound(soil)
        sl,sh=soil_bb.GetRange().GetMin(),soil_bb.GetRange().GetMax()
        corners=np.array(list(itertools.product(*zip(sl,sh))))
        soil_local=transform_points(corners,soil_bb.GetMatrix()*matrix.GetInverse())
        soil_z=float(soil_local[:,2].max())
        edges=bed_edge_limits(stage,cache,p,matrix,soil_local)
        beds.append({'id':i,'path':str(p.GetPath()),'matrix':matrix,'x':float((lo[0]+hi[0])/2),
            'y0':float(lo[1]+cfg['trellis_pipe_radius_m']),
            'y1':float(hi[1]-cfg['trellis_pipe_radius_m']),
            'soil_z':soil_z, **edges})
    beds.sort(key=lambda b:b['id'])
    if not beds:raise ValueError('No Trellis_Frame_XX + Soil_Surface_N found in background')
    return beds


def validate(cfg):
    for key in ['plants_per_bed','max_attempts_per_fruit']:
        if type(cfg[key])!=int or cfg[key]<1:raise ValueError(key+' must be a positive integer')
    for key in ['tree_height_m','fruit_scale_range']:
        a,b=cfg[key]
        if not 0<a<=b:raise ValueError(key+' must be [positive min, max]')
    for key in ['canopy_width_m','canopy_length_m','trellis_pipe_radius_m','stem_radius_m','max_connector_length_m']:
        if cfg[key]<=0:raise ValueError(key+' must be positive')
    for key in ['wire_clearance_m','fruit_gap_m','plant_end_margin_m','root_bury_m']:
        if cfg[key]<0:raise ValueError(key+' must be nonnegative')
    if cfg['fruit_sides'] not in ['both','left','right']:raise ValueError('fruit_sides: both / left / right')
    for color,n in cfg['fruit_counts_per_bed'].items():
        if color not in COLORS or type(n)!=int or n<0:raise ValueError('Invalid fruit count or color')
    if not cfg['tree_variants']:raise ValueError('tree_variants cannot be empty')
    if type(cfg.get('extra_foliage_enabled', True)) is not bool:
        raise ValueError('extra_foliage_enabled must be true or false')
    copies=cfg.get('extra_foliage_copies_per_tree', 1)
    if type(copies) is not int or copies < 0:
        raise ValueError('extra_foliage_copies_per_tree must be a nonnegative integer')
    angles=cfg.get('extra_foliage_angles_deg', [120.0,240.0])
    if not isinstance(angles,(list,tuple)) or any(type(a) not in (int,float) or not math.isfinite(a) for a in angles):
        raise ValueError('extra_foliage_angles_deg must be a list of finite numbers')

def ref_asset(stage,path,asset,position,scale,yaw,output):
    xf=UsdGeom.Xform.Define(stage,path)
    xf.AddTranslateOp().Set(Gf.Vec3d(*position))
    xf.AddRotateZOp().Set(float(yaw))
    xf.AddScaleOp().Set(Gf.Vec3f(*scale))
    model=stage.DefinePrim(path+'/Model','Xform')
    model.GetReferences().AddReference(relative(asset,output.parent))
    model.SetInstanceable(True)
    return xf.GetPrim()

def branch_material(stage):
    mat=UsdShade.Material.Define(stage,'/World/Vegetation/Looks/Stem')
    sh=UsdShade.Shader.Define(stage,str(mat.GetPath())+'/Surface');sh.CreateIdAttr('UsdPreviewSurface')
    sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.075,.19,.028))
    sh.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.8)
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface')
    return mat

def connector(stage,path,start,end,radius,mat):
    # Mesh tube, rather than a viewport-only line/curve.
    d=end-start;d/=np.linalg.norm(d)
    u=np.cross(d,[0,0,1])
    if np.linalg.norm(u)<1e-6:u=np.cross(d,[0,1,0])
    u/=np.linalg.norm(u);v=np.cross(d,u)
    pts=[p+radius*(math.cos(t)*u+math.sin(t)*v) for p in [start,end] for t in np.arange(8)*math.pi/4]
    faces=[[i,(i+1)%8,(i+1)%8+8,i+8] for i in range(8)]
    faces += [list(reversed(range(8))),list(range(8,16))]
    m=UsdGeom.Mesh.Define(stage,path)
    m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(np.array(pts,dtype=np.float32)))
    m.CreateFaceVertexCountsAttr([len(f) for f in faces]);m.CreateFaceVertexIndicesAttr([i for f in faces for i in f])
    m.CreateSubdivisionSchemeAttr('none');UsdShade.MaterialBindingAPI.Apply(m.GetPrim()).Bind(mat)

def foliage_pivot(stage, source, cache, time):
    path = source.GetPath().GetParentPath().AppendChild('Part_0')
    trunk = stage.GetPrimAtPath(path)
    if not trunk or not trunk.IsA(UsdGeom.Mesh):
        raise RuntimeError('Part_0 Mesh not found; cannot build extra foliage.')
    points = UsdGeom.Mesh(trunk).GetPointsAttr().Get(time)
    if not points:
        raise RuntimeError('Part_0 has no vertices; cannot estimate trunk centre.')
    world = cache.GetLocalToWorldTransform(trunk)
    points = [world.Transform(Gf.Vec3d(p)) for p in points]
    axis = 1 if UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y else 2
    low, high = min(p[axis] for p in points), max(p[axis] for p in points)
    base = [p for p in points if p[axis] <= low + (high-low)*.10 + 1e-8]
    pivot = Gf.Vec3d(*(sum(p[i] for p in base)/len(base) for i in range(3)))
    pivot[axis] = low
    return pivot

def foliage_material_bindings(source):
    # Sub-root references do not necessarily retain material targets located
    # outside Part_1 (e.g. sibling Looks). Capture resolved bindings explicitly,
    # including face subsets and renderer-specific purposes.
    result = []
    for prim in Usd.PrimRange(source, Usd.TraverseInstanceProxies()):
        for purpose in (UsdShade.Tokens.allPurpose, UsdShade.Tokens.preview, UsdShade.Tokens.full):
            mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(purpose)
            if mat:
                result.append((prim.GetPath().MakeRelativePath(source.GetPath()), purpose, mat))
    return result

def copy_foliage_mesh(stage, source, destination, time):
    """Snapshot composed geometry, including instance proxies, without editing
    or de-instancing the source. Preserve UV metadata and per-face subsets.
    Materials remain bound to the original resolved material prims.
    """
    clone = UsdGeom.Mesh.Define(stage, destination).GetPrim()
    geometry_names = set(str(n) for n in UsdGeom.Mesh.GetSchemaAttributeNames())
    subset_names = set(str(n) for n in UsdGeom.Subset.GetSchemaAttributeNames())
    for src in Usd.PrimRange(source, Usd.TraverseInstanceProxies()):
        if src == source:
            dst, names = clone, geometry_names
        elif src.IsA(UsdGeom.Subset):
            relative = src.GetPath().MakeRelativePath(source.GetPath())
            dst = UsdGeom.Subset.Define(stage, destination.AppendPath(relative)).GetPrim()
            names = subset_names
        else:
            continue
        for attr in src.GetAttributes():
            name = attr.GetName()
            if name.startswith('xformOp:') or name == 'xformOpOrder':
                continue
            if name not in names and not name.startswith(('primvars:', 'subsetFamily:')):
                continue
            value = attr.Get(time)
            if value is None:
                continue
            target = dst.CreateAttribute(name, attr.GetTypeName(),
                                         custom=attr.IsCustom(), variability=attr.GetVariability())
            target.Set(value)
            for key in ('interpolation', 'elementSize', 'unauthoredValuesIndex'):
                if attr.HasMetadata(key):
                    target.SetMetadata(key, attr.GetMetadata(key))
    # Freeze resolved inherited visibility/purpose/primvars for this static trial.
    src_imageable = UsdGeom.Imageable(source)
    dst_imageable = UsdGeom.Imageable(clone)
    dst_imageable.CreateVisibilityAttr(src_imageable.ComputeVisibility(time))
    dst_imageable.CreatePurposeAttr(src_imageable.ComputePurpose())
    for pv in UsdGeom.PrimvarsAPI(source).FindPrimvarsWithInheritance():
        value = pv.ComputeFlattened(time)
        if value is None:
            continue
        dst_pv = UsdGeom.PrimvarsAPI(clone).CreatePrimvar(pv.GetPrimvarName(),
                    pv.GetTypeName(), pv.GetInterpolation(), pv.GetElementSize())
        dst_pv.Set(value)
        # Snapshot flattened values; copied source indices must not apply twice.
        dst_pv.BlockIndices()
    return clone



def fit_foliage_band(points, inside_left, inside_right, soil_z, bed_world_z,
                     target_world_z=.855, preferred_scale=.85, x_fraction=.5, y_offset=0.0):
    """Translate and UNIFORMLY scale added foliage; never squash height.
    Target height is a soft density-center target, not a clipping band.
    Soil and interior clearance take precedence over the height target.
    """
    points = np.asarray(points, dtype=float)
    lo, hi = points.min(axis=0), points.max(axis=0)
    if inside_left >= inside_right:
        raise ValueError('Bed interior too narrow for foliage behind fruit rows')
    scale = min(preferred_scale, (inside_right-inside_left)/max(hi[0]-lo[0],1e-9))
    free_width = max(0.0, inside_right-inside_left-scale*(hi[0]-lo[0]))
    tx = inside_left + x_fraction*free_width - scale*lo[0]
    center_z = float(np.median(points[:,2]))
    tz = max(target_world_z-bed_world_z-scale*center_z,
             soil_z+.02-scale*lo[2])
    center_y = (lo[1]+hi[1])/2
    matrix = np.eye(4)
    matrix[0,0] = matrix[1,1] = matrix[2,2] = scale
    matrix[3,:3] = [tx, center_y*(1-scale)+y_offset, tz]
    return matrix

def add_extra_foliage(stage, tree, cfg, bed, fruit_radius_max):
    """Author permanent visual-only foliage under the non-instanced tree Xform.
    Model stays instanceable. Geometry/UVs are composed snapshots; materials
    retain their original bindings. Build's root-layer Save persists everything.
    Separate per-tree RNG: existing tree/fruit random sequence is untouched.
    """
    if not cfg.get('extra_foliage_enabled', True):
        return 0
    angles = cfg.get('extra_foliage_angles_deg', [120.0, 240.0])
    if not angles:
        return 0
    # Existing angle settings are candidates; default to ONE extra copy per tree.
    seed_text = str(cfg['seed']) + ':' + str(tree.GetPath())
    seed = int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:8], 'little')
    foliage_rng = np.random.default_rng(seed)
    count = min(cfg.get('extra_foliage_copies_per_tree', 2), len(angles))
    selected = foliage_rng.permutation(len(angles))[:count]
    angles = [float(angles[int(i)]) + float(foliage_rng.uniform(-25,25)) for i in selected]
    if not angles:
        return 0
    source = stage.GetPrimAtPath(tree.GetPath().AppendPath('Model/Part_1'))
    if not source or not source.IsA(UsdGeom.Mesh):
        raise ValueError(str(tree.GetPath()) + ': Model/Part_1 Mesh not found')
    time = Usd.TimeCode.Default()
    cache = UsdGeom.XformCache(time)
    source_world = cache.GetLocalToWorldTransform(source)
    tree_world = cache.GetLocalToWorldTransform(tree)
    if abs(tree_world.GetDeterminant()) < 1e-15:
        raise ValueError(str(tree.GetPath()) + ': singular tree transform')
    tree_inverse = tree_world.GetInverse()
    pivot = foliage_pivot(stage, source, cache, time)
    bindings = foliage_material_bindings(source)
    source_points = np.asarray(UsdGeom.Mesh(source).GetPointsAttr().Get(time), dtype=float)
    if source_points.size == 0:
        raise ValueError('Part_1 foliage mesh has no points')
    # +/-5 cm fruit-center offset, full fruit radius, plus 2 cm clearance.
    inset = .05 + fruit_radius_max + .02
    inside_left = bed['left_edge_x'] + inset
    inside_right = bed['right_edge_x'] - inset
    bed_inverse = bed['matrix'].GetInverse()
    folder = tree.GetPath().AppendChild('ExtraFoliage')
    existing = stage.GetPrimAtPath(folder)
    if existing:
        if existing.GetCustomDataByKey('foliageOwner') != 'placement_extra_foliage_v1':
            raise ValueError('ExtraFoliage path occupied by unrelated content: '+str(folder))
        stage.RemovePrim(folder)
    group = UsdGeom.Xform.Define(stage, folder).GetPrim()
    group.SetCustomDataByKey('foliageOwner', 'placement_extra_foliage_v1')
    for index, angle in enumerate(angles, 1):
        dest = folder.AppendChild('Leaves_%02d' % index)
        clone = copy_foliage_mesh(stage, source, dest, time)
        rotation = Gf.Matrix4d(1).SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1), float(angle)))
        before = Gf.Matrix4d(1).SetTranslate(-pivot)
        after = Gf.Matrix4d(1).SetTranslate(pivot)
        # Rotate existing copy, then move and uniformly scale it in the BED frame.
        rotated_bed = source_world * before * rotation * after * bed_inverse
        points_bed = transform_points(source_points, rotated_bed)
        fit = fit_foliage_band(points_bed, inside_left, inside_right,
                               bed['soil_z'], float(bed['matrix'].ExtractTranslation()[2]),
                               target_world_z=float(foliage_rng.uniform(.72,1.10)),
                               preferred_scale=float(foliage_rng.uniform(.80,.95)),
                               x_fraction=float(foliage_rng.uniform(.2,.8)),
                               y_offset=float(foliage_rng.uniform(-.08,.08)))
        matrix = rotated_bed * Gf.Matrix4d(*fit.flatten().tolist()) * bed['matrix'] * tree_inverse
        final_points = transform_points(points_bed, Gf.Matrix4d(*fit.flatten().tolist()))
        assert final_points[:,0].min() >= inside_left-1e-7
        assert final_points[:,0].max() <= inside_right+1e-7
        assert final_points[:,2].min() >= bed['soil_z']+.02-1e-7
        clone.SetCustomDataByKey('foliagePlacement', 'natural_staggered_interior_v3')
        xf = UsdGeom.Xformable(clone)
        xf.ClearXformOpOrder()
        xf.AddTransformOp(UsdGeom.XformOp.PrecisionDouble, 'extraFoliage').Set(matrix)
        xf.SetResetXformStack(False)
        for relative_path, purpose, material in bindings:
            target = stage.GetPrimAtPath(dest.AppendPath(relative_path))
            if target:
                UsdShade.MaterialBindingAPI.Apply(target).Bind(material,
                    bindingStrength=UsdShade.Tokens.weakerThanDescendants,
                    materialPurpose=purpose)
    return len(angles)

def build(config_path=None):
    config_path=Path(config_path or ROOT/'config.json').resolve()
    cfg=json.loads(config_path.read_text(encoding='utf-8'));validate(cfg)
    bg=(ROOT/cfg['background']).resolve();output=(ROOT/cfg['output']).resolve()
    if output==bg:raise ValueError('Output must not overwrite background')
    if output.suffix not in ['.usd','.usda','.usdc']:raise ValueError('Output must have USD extension')
    meta=json.loads((ROOT/'assets/manifest.json').read_text())
    for v in cfg['tree_variants']:
        if v not in meta or 'stem_points' not in meta[v]:raise ValueError('Unknown tree '+v)
    background=Usd.Stage.Open(str(bg));beds=find_beds(background,cfg)
    deck_top_z = 0.73  # metres; frame 0.52 + lower chassis 0.21
    deck_source = 'fixed:0.73m (ground world Z=0)'
    ids={str(b['id']) for b in beds}
    if set(cfg.get('bed_overrides',{}))-ids:raise ValueError('Unknown bed_overrides ID')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.stem+'.building'+output.suffix)
    if temporary.exists():temporary.unlink()
    stage=Usd.Stage.CreateNew(str(temporary));stage.GetRootLayer().subLayerPaths=[relative(bg,output.parent)]
    UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1)
    stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
    UsdGeom.Xform.Define(stage,'/World/Vegetation');mat=branch_material(stage)
    rng=np.random.default_rng(cfg['seed']);trees=[];fruits=[];warnings=[]
    try:
        if cfg['missing_hdri_fallback']:
            for p in stage.Traverse():
                a=p.GetAttribute('inputs:texture:file')
                if p.GetTypeName()=='DomeLight' and a:
                    val=a.Get()
                    if val and val.path and not val.resolvedPath:
                        a.Set(Sdf.AssetPath(''))
                        warnings.append(f'Missing HDRI {val.path}; used untextured dome light.')
        for bed in beds:
            local=dict(cfg);local.update(cfg.get('bed_overrides',{}).get(str(bed['id']),{}));validate(local)
            if local['trellis_pipe_radius_m']!=cfg['trellis_pipe_radius_m']:
                raise ValueError('trellis_pipe_radius_m is global only')
            for v in local['tree_variants']:
                if v not in meta or 'stem_points' not in meta[v]:raise ValueError('Unknown tree '+v)
            # Bed transforms are rigid and Z-up: world Z = local Z + translation Z.
            zmin = 0.63 - float(bed['matrix'].ExtractTranslation()[2])
            zmax = 1.08 - float(bed['matrix'].ExtractTranslation()[2])
            base=f"/World/Vegetation/Bed_{bed['id']:02d}"

            UsdGeom.Xform.Define(stage,base).AddTransformOp().Set(bed['matrix'])
            y0=bed['y0']+local['plant_end_margin_m'];y1=bed['y1']-local['plant_end_margin_m']
            if y0>=y1:raise ValueError('End margins consume bed')
            n=local['plants_per_bed'];ys=np.array([(y0+y1)/2]) if n==1 else np.linspace(y0,y1,n)
            candidates=[]
            for k,y in enumerate(ys):
                variant=local['tree_variants'][int(rng.integers(len(local['tree_variants'])))];m=meta[variant]
                size=np.diff(np.array(m['bounds']),axis=0)[0]
                scale=np.array([local['canopy_width_m']/size[0],local['canopy_length_m']/size[1],rng.uniform(*local['tree_height_m'])/size[2]])
                yaw=float(rng.choice([0,180]));sign=1 if yaw==0 else -1
                position=np.array([bed['x'],y,bed['soil_z']-local['root_bury_m']])
                path=base+f'/Trees/Tree_{k+1:03d}'
                tree_prim=ref_asset(stage,path,ROOT/'assets'/m['file'],position,scale,yaw,output)
                fruit_radius_max=max(meta[COLORS[c]]['radius'] for c in COLORS)*max(local['fruit_scale_range'])
                leaf_copies=add_extra_foliage(stage,tree_prim,local,bed,fruit_radius_max)
                stem=np.array(m['stem_points'])*scale*np.array([sign,sign,1])+position
                # Keep all stem points; choose an anchor near the sampled fruit height.
                if len(stem):candidates.append((path,stem))
                trees.append({'path':path,'variant':variant,'bed':bed['id'],'position_world':transform_points([position],bed['matrix'])[0].tolist(),'scale':scale.tolist(),'yaw_deg':yaw,'extra_foliage_copies':leaf_copies})
            labels=[c for c,count in local['fruit_counts_per_bed'].items() for _ in range(count)];rng.shuffle(labels)
            if labels and not candidates:raise ValueError('No tree stems in requested fruit height range')
            accepted=[]
            for index,color in enumerate(labels):
                m=meta[COLORS[color]]
                for attempt in range(local['max_attempts_per_fruit']):
                    treepath,stem=candidates[int(rng.integers(len(candidates)))]
                    side=int(rng.choice([-1,1])) if local['fruit_sides']=='both' else (-1 if local['fruit_sides']=='left' else 1)
                    scale=float(rng.uniform(*local['fruit_scale_range']));radius=m['radius']*scale
                    yaw=float(rng.uniform(-180,180));angle=math.radians(yaw)
                    rot=np.array([[math.cos(angle),-math.sin(angle),0],[math.sin(angle),math.cos(angle),0],[0,0,1]])
                    # Prefer outer branches, not interior trunk, as the attachment source.
                    outer=stem[side*(stem[:,0]-bed['x'])>=np.quantile(side*(stem[:,0]-bed['x']),.65)]
                    offset=rot@(np.array(m['attachment'])*scale)
                    target_z=float(rng.uniform(zmin,zmax))
                    # Signed offset: negative = inward, positive = outward from outer edge.
                    edge_offset=float(rng.uniform(-0.05,0.05))
                    edge_x=bed['left_edge_x'] if side < 0 else bed['right_edge_x']
                    target_x=edge_x+side*edge_offset
                    errors=(outer[:,0]-(target_x+offset[0]))**2+(outer[:,2]-(target_z+offset[2]))**2
                    nearest=np.argsort(errors)[:min(8,len(outer))]
                    anchor=outer[int(rng.choice(nearest))].copy()
                    center=np.array([target_x,anchor[1]-offset[1],target_z])
                    if not zmin<=center[2]<=zmax:continue
                    if not bed['y0']+radius<=center[1]<=bed['y1']-radius:continue
                    endpoint=center+offset
                    if np.linalg.norm(endpoint-anchor)>local['max_connector_length_m']:continue
                    if any(np.linalg.norm(center-prev)<radius+rr+local['fruit_gap_m'] for prev,rr in accepted):continue
                    break
                else:
                    raise RuntimeError(f"Bed {bed['id']}: cannot place {len(labels)} fruits with current spacing/heights. Reduce counts / fruit size, or adjust tree stems / max_connector_length_m. Required +/-5 cm and deck-relative height limits are not relaxed. Existing output preserved.")
                path=base+f'/Fruits/Pepper_{index+1:04d}_{color}'
                prim=ref_asset(stage,path,ROOT/'assets'/m['file'],center,[scale]*3,yaw,output)
                for key,value in [('color',color),('sourceTree',treepath)]:prim.CreateAttribute('crop:'+key,Sdf.ValueTypeNames.String,custom=True).Set(value)
                prim.CreateAttribute('crop:bedId',Sdf.ValueTypeNames.Int,custom=True).Set(bed['id'])
                if local['connect_stems'] and np.linalg.norm(endpoint-anchor)>1e-6:
                    connector(stage,base+f'/Connectors/Stem_{index+1:04d}',anchor,endpoint,local['stem_radius_m'],mat)
                accepted.append((center,radius))
                fruits.append({'path':path,'tree':treepath,'bed':bed['id'],'color':color,'center_local':center.tolist(),
                    'center_world':transform_points([center],bed['matrix'])[0].tolist(),'radius_m':radius,'scale':scale,
                    'yaw_deg':yaw,'side':side,'bed_edge_surface_clearance_lower_bound_m':float(side*(center[0]-edge_x)-radius),
                    'bed_edge_offset_m':float(side*(center[0]-edge_x)),
                    'bed_edge_reference_path':bed['left_edge_path'] if side < 0 else bed['right_edge_path'],
                    'bed_edge_reference_x_local_m':edge_x,
                    'height_above_harvest_deck_m':float(transform_points([center],bed['matrix'])[0][2]-deck_top_z),
                    'connector_length_m':float(np.linalg.norm(endpoint-anchor))})
        # Verify every accepted center before replacing the existing output.
        for fruit in fruits:
            assert -0.050000001 <= fruit['bed_edge_offset_m'] <= 0.050000001
            assert -0.100000001 <= fruit['height_above_harvest_deck_m'] <= 0.350000001
        # Author a useful review camera without changing background camera settings.
        cam=UsdGeom.Camera.Define(stage,'/World/Vegetation/ReviewCamera')
        cam.CreateFocalLengthAttr(25);cam.CreateClippingRangeAttr(Gf.Vec2f(.05,200))
        view=Gf.Matrix4d().SetLookAt(Gf.Vec3d(-.15,-11.5,2.1),Gf.Vec3d(-2,-5,1.2),Gf.Vec3d(0,0,1))
        cam.AddTransformOp().Set(view.GetInverse())
        stage.GetRootLayer().Save()
        report={'background':relative(bg,ROOT),'output':relative(output,ROOT),'seed':cfg['seed'],
            'harvest_deck_top_world_z_m':deck_top_z,'harvest_deck_source':deck_source,
            'fruit_edge_offset_range_m':[-0.05,0.05],'fruit_height_above_deck_range_m':[-0.10,0.35],
            'bed_count':len(beds),'tree_count':len(trees),'fruit_count':len(fruits),'warnings':warnings,
            'extra_foliage_mesh_count':sum(t['extra_foliage_copies'] for t in trees),
            'trees':trees,'fruits':fruits}
        report_temp=output.with_suffix('.report.building.json')
        report_temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        # Drop stage/layer references before replacing the file (also works on Windows).
        stage=None
        os.replace(temporary,output)
        os.replace(report_temp,output.with_suffix(".report.json"))
        print(f"Saved {output} | beds={len(beds)}, trees={len(trees)}, fruits={len(fruits)}")
        for warning in warnings:print("NOTICE:",warning)
    except Exception:
        stage=None
        if temporary.exists():temporary.unlink()
        raise
    return output
