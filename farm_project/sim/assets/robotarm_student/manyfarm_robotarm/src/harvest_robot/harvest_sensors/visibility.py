"""Memory-bounded CPU exact-triangle ray sampling via perspective rasterization.

Outputs are audit masks only. Not a learned perception or a grasp detector.
"""
import numpy as np
from numba import njit


@njit(cache=False)
def triangle_visibility(triangles, labels, optical_from_gripper, k, native_width, native_height,
                        width=160, height=90, near=.01):
    depth=np.full((height,width),np.inf)
    semantic=np.zeros((height,width),np.int32)
    for face in range(len(triangles)):
        tri=triangles[face]@optical_from_gripper[:3,:3].T+optical_from_gripper[:3,3]
        # Clip each exact triangle against the near plane before projection.
        clipped=np.zeros((6,3)); count=0
        previous=tri[2]; prev_inside=previous[2]>=near
        for i in range(3):
            current=tri[i]; inside=current[2]>=near
            if inside != prev_inside:
                t=(near-previous[2])/(current[2]-previous[2])
                clipped[count]=previous+t*(current-previous); count+=1
            if inside:
                clipped[count]=current; count+=1
            previous=current; prev_inside=inside
        for fan in range(1,count-1):
            polygon=np.empty((3,3)); polygon[0]=clipped[0]; polygon[1]=clipped[fan]; polygon[2]=clipped[fan+1]
            u=(polygon[:,0]/polygon[:,2]*k[0,0]+k[0,2]+.5)*width/native_width-.5
            v=(polygon[:,1]/polygon[:,2]*k[1,1]+k[1,2]+.5)*height/native_height-.5
            denominator=(v[1]-v[2])*(u[0]-u[2])+(u[2]-u[1])*(v[0]-v[2])
            if abs(denominator)<1e-12: continue
            xlo=max(0,int(np.floor(np.min(u)))); xhi=min(width-1,int(np.ceil(np.max(u))))
            ylo=max(0,int(np.floor(np.min(v)))); yhi=min(height-1,int(np.ceil(np.max(v))))
            for y in range(ylo,yhi+1):
                for x in range(xlo,xhi+1):
                    a=((v[1]-v[2])*(x-u[2])+(u[2]-u[1])*(y-v[2]))/denominator
                    b=((v[2]-v[0])*(x-u[2])+(u[0]-u[2])*(y-v[2]))/denominator
                    c=1-a-b
                    if a>=-1e-9 and b>=-1e-9 and c>=-1e-9:
                        z=1/(a/polygon[0,2]+b/polygon[1,2]+c/polygon[2,2])
                        if z>=near-1e-8 and z<depth[y,x]:
                            depth[y,x]=z; semantic[y,x]=labels[face]
    return depth.reshape(-1),semantic.reshape(-1)
