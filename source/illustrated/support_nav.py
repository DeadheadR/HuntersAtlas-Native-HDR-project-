"""Reject authored AI proxy surfaces without physical ground support."""
from geometry import WORK
import numpy as np,json
from scipy.spatial import cKDTree
import shapely as sh
raw=np.load(WORK/'collision.npy');nav=np.load(WORK/'navmesh-triangles.npy')
n=np.cross(raw[:,1]-raw[:,0],raw[:,2]-raw[:,0]);length=np.linalg.norm(n,axis=1)
floors=raw[(n[:,1]>.45*length)&(length>1e-8)]
tree=sh.STRtree(sh.polygons(floors[:,:,[0,2]]))
samples=np.concatenate([nav.mean(axis=1)[:,None,:],nav],axis=1).reshape(-1,3)
errors=[]
for begin in range(0,len(samples),4000):
 p=samples[begin:begin+4000];pi,idx=tree.query(sh.points(p[:,[0,2]]),predicate='dwithin',distance=.08);t=floors[idx]
 a=t[:,0];b=t[:,1]-a;c=t[:,2]-a;q=p[pi]-a
 den=b[:,0]*c[:,2]-b[:,2]*c[:,0];good=np.abs(den)>1e-8;den=np.where(good,den,1)
 u=(q[:,0]*c[:,2]-q[:,2]*c[:,0])/den;v=(b[:,0]*q[:,2]-b[:,2]*q[:,0])/den
 y=a[:,1]+u*b[:,1]+v*c[:,1]
 error=np.full(len(p),np.inf);np.minimum.at(error,pi,np.where(good,np.abs(y-p[pi,1]),np.inf))
 errors.extend(error.tolist())
error=np.array(errors).reshape(-1,4)
# A face must have supported center and at least two supported vertices.
keep=(error[:,0]<1.2)&((error[:,1:]<1.2).sum(axis=1)>=2)
np.save(WORK/'nav-supported.npy',keep)
np.save(WORK/'nav-support-errors.npy',error)
report=dict(nav_triangles=len(nav),supported=int(keep.sum()),rejected=int((~keep).sum()),height_tolerance=1.2,
 method='Centroid and >=2 vertices must lie on collision floor within 1.2m; exhaustive spatial triangle lookup within 0.08m of projected support, barycentric interpolation.',
 finite_error_median=float(np.median(error[np.isfinite(error)])),rejected_by_support_criterion=True)
(WORK/'nav-support-qa.json').write_text(json.dumps(report,indent=2))
print(report,flush=True)
