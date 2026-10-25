"""Detect true overlapping walkable triangle planes, including within one mesh."""
from geometry import WORK,packed,components
import numpy as np, shapely as sh,json,time
start=time.monotonic();tri=np.load(WORK/'navmesh-triangles.npy')[np.load(WORK/'nav-supported.npy')]
polys=sh.polygons(tri[:,:,[0,2]]);tree=sh.STRtree(polys)
ai,bi=tree.query(polys,predicate='intersects');valid=ai>bi;ai,bi=ai[valid],bi[valid]
inter=sh.intersection(polys[ai],polys[bi]);valid=sh.area(inter)>.12
ai,bi,inter=ai[valid],bi[valid],inter[valid]
def height(t,points):
 x,z=points[:,0],points[:,1];a,b,c=t
 den=(b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2])
 u=((b[2]-c[2])*(x-c[0])+(c[0]-b[0])*(z-c[2]))/den
 v=((c[2]-a[2])*(x-c[0])+(a[0]-c[0])*(z-c[2]))/den
 return u*a[1]+v*b[1]+(1-u-v)*c[1]
def clip(points,d):
 result=[]
 for k in range(len(points)):
  p,q=points[k-1],points[k];a,b=d[k-1],d[k]
  if (a>=0)!=(b>=0):result.append(p+(q-p)*a/(a-b))
  if b>=0:result.append(q)
 return result
records=[]
for a,b,poly in zip(ai,bi,inter):
 for p in components(poly):
  points=np.array(p.exterior.coords)[:-1];d=height(tri[a],points)-height(tri[b],points)
  for sign in (1,-1):
   pp=clip(points,sign*d-2.4)
   if len(pp)<3:continue
   g=sh.Polygon(pp)
   if g.area<.25:continue
   records.append((g,int(a if sign==1 else b),int(b if sign==1 else a)))
if not records:
 records=[]
all_regions=sh.union_all([r[0] for r in records],grid_size=.015)
rtree=sh.STRtree([r[0] for r in records]);result=[]
def linecoords(g):
 if g.geom_type=='LineString':yield [[round(x,3),round(z,3)] for x,z in g.coords]
 elif hasattr(g,'geoms'):
  for q in g.geoms:yield from linecoords(q)
for region in components(all_regions):
 if region.area<1:continue
 rs=rtree.query(region,predicate='intersects');us=sorted({records[i][1] for i in rs});ls=sorted({records[i][2] for i in rs})
 upper=sh.union_all(polys[us],grid_size=.015);lower=sh.union_all(polys[ls],grid_size=.015);window=region.buffer(3)
 def get(g):
  data=packed(sh.intersection(g,window));data['outlines']=list(linecoords(sh.intersection(g.boundary,window)));return data
 q=region.representative_point();pp=np.array([[q.x,q.y]])
 # Height nearest the representative point, with provenance retained.
 us2=[u for u in us if sh.distance(polys[u],q)<.03];ls2=[l for l in ls if sh.distance(polys[l],q)<.03]
 if not us2 or not ls2:continue
 high=float(np.max([height(tri[u],pp)[0] for u in us2]));low=float(np.min([height(tri[l],pp)[0] for l in ls2]))
 result.append(dict(id=len(result),center=[q.x,q.y],min_y=low,max_y=high,area=region.area,
  geometry=get(upper),lower_geometry=get(lower),overlap_geometry=packed(region),upper_triangles=us,lower_triangles=ls,
  upper_surfaces=tri[us].tolist(),lower_surfaces=tri[ls].tolist()))
data=json.loads((WORK/'navigation.json').read_text());data['overlaps']=result
(WORK/'navigation.json').write_text(json.dumps(data,separators=(',',':')))
qa=json.loads((WORK/'geometry-qa.json').read_text());qa['overlap_regions']=[{k:v for k,v in r.items() if k not in ('geometry','lower_geometry','overlap_geometry','upper_triangles','lower_triangles','upper_surfaces','lower_surfaces')} for r in result]
qa['overlap_method']='Exact projected triangle intersections, plane-height clipping at 2.4m; includes self-overlaps and partitions changing height order.'
qa['overlap_triangle_pairs']=len(records);qa['overlap_seconds']=time.monotonic()-start
(WORK/'geometry-qa.json').write_text(json.dumps(qa,indent=2))
print('EXACT_OVERLAPS',len(result),'PAIRS',len(records),'SECONDS',time.monotonic()-start,flush=True)
