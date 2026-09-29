"""One-time conversion of the two supplied GLBs. Preconverted assets are included.
Optional rebuild: python prepare_assets.py --source /path/to/TreePlacement
Requires numpy, usd-core. No Blender, mesh decimation, or texture resizing.
"""
import argparse
import json
import struct
from pathlib import Path
import numpy as np
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt

ROOT = Path(__file__).resolve().parent

class GLB:
    def __init__(self, path):
        raw = Path(path).read_bytes()
        magic, version, total = struct.unpack_from('<III', raw)
        assert magic == 0x46546c67 and version == 2 and total == len(raw)
        offset = 12
        while offset < total:
            size, kind = struct.unpack_from('<II', raw, offset)
            chunk = raw[offset+8:offset+8+size]
            if kind == 0x4e4f534a: self.j = json.loads(chunk)
            elif kind == 0x004e4942: self.binary = chunk
            offset += size + 8
    def array(self, index):
        a = self.j['accessors'][index]
        if 'sparse' in a: raise ValueError('Sparse accessor unsupported')
        v = self.j['bufferViews'][a['bufferView']]
        dt = np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1',5122:'<i2',5120:'i1'}[a['componentType']])
        n = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]
        result = np.ndarray((a['count'],n), dtype=dt, buffer=self.binary,
            offset=v.get('byteOffset',0)+a.get('byteOffset',0),
            strides=(v.get('byteStride',dt.itemsize*n),dt.itemsize)).copy()
        if a.get('normalized') and dt.kind in 'iu':
            result = np.maximum(result.astype(float)/np.iinfo(dt).max,-1)
        return result
    def images(self, folder, prefix):
        result=[]
        for i,im in enumerate(self.j.get('images',[])):
            v=self.j['bufferViews'][im['bufferView']]
            suffix={'image/png':'.png','image/jpeg':'.jpg'}[im['mimeType']]
            path=folder/f'{prefix}_{i}{suffix}'
            path.write_bytes(self.binary[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])
            result.append('textures/'+path.name)
        return result

def zup(a):
    a=np.asarray(a)
    return np.column_stack((a[:,0],-a[:,2],a[:,1])).astype(np.float32)

def material(stage, path, spec, glb, images):
    mat=UsdShade.Material.Define(stage,path)
    surf=UsdShade.Shader.Define(stage,path+'/Surface'); surf.CreateIdAttr('UsdPreviewSurface')
    mat.CreateSurfaceOutput().ConnectToSource(surf.ConnectableAPI(),'surface')
    reader=UsdShade.Shader.Define(stage,path+'/UV');reader.CreateIdAttr('UsdPrimvarReader_float2')
    reader.CreateInput('varname',Sdf.ValueTypeNames.Token).Set('st')
    reader.CreateOutput('result',Sdf.ValueTypeNames.Float2)
    def tex(info,label,space='raw',scale=None,bias=None):
        t=UsdShade.Shader.Define(stage,path+'/'+label);t.CreateIdAttr('UsdUVTexture')
        image=images[glb.j['textures'][info['index']]['source']]
        t.CreateInput('file',Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(image))
        t.CreateInput('sourceColorSpace',Sdf.ValueTypeNames.Token).Set(space)
        t.CreateInput('st',Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(),'result')
        for k in ('wrapS','wrapT'): t.CreateInput(k,Sdf.ValueTypeNames.Token).Set('repeat')
        if scale is not None:t.CreateInput('scale',Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(*scale))
        if bias is not None:t.CreateInput('bias',Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(*bias))
        for channel in ('r','g','b','a'):t.CreateOutput(channel,Sdf.ValueTypeNames.Float)
        t.CreateOutput('rgb',Sdf.ValueTypeNames.Float3)
        return t
    def inp(name,typ,val): return surf.CreateInput(name,typ).Set(val)
    pbr=spec.get('pbrMetallicRoughness',{});base=pbr.get('baseColorFactor',[1,1,1,1])
    inp('diffuseColor',Sdf.ValueTypeNames.Color3f,Gf.Vec3f(*base[:3]))
    inp('roughness',Sdf.ValueTypeNames.Float,pbr.get('roughnessFactor',1))
    inp('metallic',Sdf.ValueTypeNames.Float,pbr.get('metallicFactor',1))
    inp('opacity',Sdf.ValueTypeNames.Float,base[3])
    if 'baseColorTexture' in pbr:
        t=tex(pbr['baseColorTexture'],'BaseColor','sRGB',base)
        surf.GetInput('diffuseColor').ConnectToSource(t.ConnectableAPI(),'rgb')
        if spec.get('alphaMode','OPAQUE')!='OPAQUE':surf.GetInput('opacity').ConnectToSource(t.ConnectableAPI(),'a')
    if spec.get('alphaMode')=='MASK':inp('opacityThreshold',Sdf.ValueTypeNames.Float,spec.get('alphaCutoff',.5))
    if 'metallicRoughnessTexture' in pbr:
        t=tex(pbr['metallicRoughnessTexture'],'ORM',scale=[1,pbr.get('roughnessFactor',1),pbr.get('metallicFactor',1),1])
        surf.GetInput('roughness').ConnectToSource(t.ConnectableAPI(),'g')
        surf.GetInput('metallic').ConnectToSource(t.ConnectableAPI(),'b')
    if 'normalTexture' in spec:
        k=spec['normalTexture'].get('scale',1)
        t=tex(spec['normalTexture'],'Normal',scale=[2*k,2*k,2,1],bias=[-k,-k,-1,0])
        surf.CreateInput('normal',Sdf.ValueTypeNames.Normal3f).ConnectToSource(t.ConnectableAPI(),'rgb')
    if 'occlusionTexture' in spec:
        t=tex(spec['occlusionTexture'],'Occlusion')
        surf.CreateInput('occlusion',Sdf.ValueTypeNames.Float).ConnectToSource(t.ConnectableAPI(),'r')
    return mat

def convert(glb,node,images,out):
    name=node['name'];parts=glb.j['meshes'][node['mesh']]['primitives']
    # Node translations are presentation-grid offsets, deliberately excluded.
    if 'matrix' in node or 'rotation' in node or 'scale' in node:raise ValueError('Unexpected source transform')
    points=[zup(glb.array(p['attributes']['POSITION'])) for p in parts]
    allpoints=np.concatenate(points);lo=allpoints.min(0);hi=allpoints.max(0)
    center=(lo+hi)/2 if name.startswith('Pepper_') else np.array([0,0,lo[2]])
    stage=Usd.Stage.CreateNew(str(out/(name+'.usdc')))
    root=UsdGeom.Xform.Define(stage,'/Asset');stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1)
    stem=[]
    for i,(p,pts) in enumerate(zip(parts,points)):
        assert p.get('mode',4)==4
        pts=pts-center
        mesh=UsdGeom.Mesh.Define(stage,f'/Asset/Part_{i}')
        mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(pts.astype(np.float32)))
        idx=glb.array(p['indices']).reshape(-1).astype(np.int32)
        mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(idx))
        mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(len(idx)//3,3,dtype=np.int32)))
        mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDoubleSidedAttr(True)
        mesh.CreateExtentAttr([Gf.Vec3f(*pts.min(0).tolist()),Gf.Vec3f(*pts.max(0).tolist())])
        attrs=p['attributes']
        if 'NORMAL' in attrs:
            mesh.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(zup(glb.array(attrs['NORMAL']))))
            mesh.SetNormalsInterpolation('vertex')
        if 'TEXCOORD_0' in attrs:
            uv=glb.array(attrs['TEXCOORD_0']).astype(np.float32);uv[:,1]=1-uv[:,1]
            UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,'vertex').Set(Vt.Vec2fArray.FromNumpy(uv))
        spec=glb.j['materials'][p['material']]
        mat=material(stage,f'/Asset/Looks/Material_{i}',spec,glb,images)
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
        if spec['name']=='Stem':stem.append(pts)
    stage.GetRootLayer().Save()
    meta={'file':name+'.usdc','bounds':[(lo-center).tolist(),(hi-center).tolist()]}
    if stem:
        v=np.unique(np.round(np.concatenate(stem),5),axis=0)
        meta['stem_points']=v[::max(1,len(v)//5000)].tolist()
    else:
        v=allpoints-center
        # The topmost source stem vertex is a geometric attachment anchor.
        meta['attachment']=v[np.argmax(v[:,2])].tolist()
        meta['radius']=float(np.max(np.linalg.norm(v,axis=1)))
    return meta

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);args=ap.parse_args()
    out=ROOT/'assets';out.mkdir(exist_ok=True);(out/'textures').mkdir(exist_ok=True)
    meta={}
    for filename,prefix in [('Pepper_Separated.glb','tree'),('Pepper_Green_Red_Yellow/Pepper_RGB_Textured.glb','fruit')]:
        glb=GLB(args.source/filename);images=glb.images(out/'textures',prefix)
        for node in glb.j['nodes']:
            if node['name'].startswith(('Tree_','Pepper_')):
                meta[node['name']]=convert(glb,node,images,out)
                print('Converted',node['name'])
    # Remove extracted textures unused by the selected tree/fruit assets.
    used=set()
    for f in out.glob('*.usdc'):
        s=Usd.Stage.Open(str(f))
        for p in s.Traverse():
            for a in p.GetAttributes():
                if a.GetTypeName()==Sdf.ValueTypeNames.Asset and a.Get():used.add(a.Get().path)
    for f in (out/'textures').iterdir():
        if 'textures/'+f.name not in used:f.unlink()
    (out/'manifest.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
if __name__=='__main__':main()
