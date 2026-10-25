"""Use authored game navmesh + NVA placements; collision remains boundary evidence."""
from pathlib import Path
import sys,json,time
from config import ROOT,WORK,REF,MAP_ID,MAP,FEATURES,ASSET
from geometry import union,packed,components
import numpy as np,shapely as sh
from scipy.spatial import cKDTree
from scipy.ndimage import label as ndlabel

start=time.monotonic();all_tri=np.load(WORK/'navmesh-triangles.npy');keep=np.load(WORK/'nav-supported.npy');tri=all_tri[keep]
surface=union(tri)
# Navmesh erosion represents AI body clearance, not physical terrain boundaries.
# Keep the native authored footprint in this MVP. No automatic global dilation.
print('AUTHORED_NAV',len(tri),'area',surface.area,'polygons',len(list(components(surface))),flush=True)
ref=MAP;features=FEATURES
tree=cKDTree(tri.mean(axis=1));checks=[]
for name,pos in [(x['name'],x['pos']) for x in ref['lamps']]+[('pickup:'+str(i),x['pos']) for i,x in enumerate(features['pickups'])]:
 d,idx=tree.query(pos,k=32);near=tri[idx].reshape(-1,3);dist=np.linalg.norm(near-np.array(pos),axis=1)
 checks.append(dict(name=name,pos=pos,nearest_nav_vertex_distance=float(dist.min()),projected_distance=float(sh.distance(sh.Point(pos[0],pos[2]),surface))))

# Exact true height overlap between individual authored NVA navmesh pieces.
inv=json.loads((WORK/'navmesh-inventory.json').read_text());offset=0;patches=[]
for row in inv:
 t=all_tri[offset:offset+row['triangles']][keep[offset:offset+row['triangles']]];offset+=row['triangles']
 if len(t):patches.append((t,union(t),row))
overlaps=[]
# Detect only real vertically separated polygons, not contact at shared edges.
for a in range(len(patches)):
 ta,pa,ra=patches[a]
 for b in range(a):
  tb,pb,rb=patches[b];intersection=sh.intersection(pa,pb)
  if intersection.area<1:continue
  # Use barycentric heights at common interior representative points.
  pts=[]
  for p in components(intersection):
   rp=p.representative_point();pts.append([rp.x,rp.y])
  def local_height(t,q):
   x,z=q;v=t[:,:,[0,2]];aa=v[:,0];bb=v[:,1];cc=v[:,2];ab=bb-aa;ac=cc-aa;qq=np.array([x,z])-aa
   den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];valid=np.abs(den)>1e-7;den=np.where(valid,den,1)
   u=(qq[:,0]*ac[:,1]-qq[:,1]*ac[:,0])/den;v=(ab[:,0]*qq[:,1]-ab[:,1]*qq[:,0])/den
   hit=valid&(u>=-.001)&(v>=-.001)&(u+v<=1.001)
   ys=t[:,0,1]+u*(t[:,1,1]-t[:,0,1])+v*(t[:,2,1]-t[:,0,1])
   return float(np.median(ys[hit])) if hit.any() else None
  valid=[]
  for q in pts:
   ya=local_height(ta,q);yb=local_height(tb,q)
   if ya is not None and yb is not None and abs(ya-yb)>2.4:valid.append((q,ya,yb))
  if not valid:continue
  q,ya,yb=max(valid,key=lambda v:abs(v[1]-v[2]));upper=pa if ya>yb else pb
  # Boundary casing follows the actual upper polygon, clipped locally around
  # the true overlap; it is not a polygon made from sampled square pixels.
  lower=pb if ya>yb else pa
  window=intersection.buffer(3)
  local=sh.intersection(upper,window)
  def boundary_packed(p):
   g=packed(sh.intersection(p,window));line=sh.intersection(p.boundary,window)
   def lines(l):
    if l.geom_type=='LineString':yield l
    elif hasattr(l,'geoms'):
     for q in l.geoms:yield from lines(q)
   g['outlines']=[[[round(x,3),round(z,3)] for x,z in l.coords] for l in lines(line)]
   return g
  overlaps.append(dict(id=len(overlaps),center=q,min_y=min(ya,yb),max_y=max(ya,yb),area=float(intersection.area),
    upper_model=ra['model'] if ya>yb else rb['model'],lower_model=rb['model'] if ya>yb else ra['model'],geometry=boundary_packed(upper),lower_geometry=boundary_packed(lower)))
print('TRUE_OVERLAPS',len(overlaps),flush=True)

data=dict(schema=2,region=MAP_ID,bounds=list(surface.bounds),surface=packed(surface),supported_triangle_count=len(tri),fringe=packed(sh.difference(surface.buffer(1.1),surface)),overlaps=overlaps,
 lamps=ref['lamps'],markers=ref['markers'],pickups=features['pickups'])
np.save(ASSET/'supported-triangles.npy',tri);(ASSET/'map-offset.json').write_text((WORK/'map-offset.json').read_text())
(WORK/'navigation.json').write_text(json.dumps(data,separators=(',',':')));(ASSET/'navigation.json').write_text(json.dumps(data,separators=(',',':')))
qa=dict(source='Game authored hkaiNavMesh polygons, transformed by NVA placement followed by MSB MapOffset',map_offset=json.loads((WORK/'map-offset.json').read_text()),
 reader='Strict Havok2014 array/index/edge-loop validation; NVA v4, section v3',
 navmesh_instances=len(inv),navmesh_triangles=len(tri),navigation_area=float(surface.area),collision_support=json.loads((WORK/'nav-support-qa.json').read_text()),
 reference_floor_triangles=sum(len(l['triangles']) for l in ref['layers']),old_height_slices=len(ref['layers']),
 contour_simplification_m=.035,polygon_union_snap_m=.015,global_dilation=False,artificial_path_connections=False,
 overlap_regions=[{k:v for k,v in o.items() if k not in ('geometry','lower_geometry')} for o in overlaps],landmark_checks=checks,
 seconds=time.monotonic()-start,limitations=[
 'AI navigation mesh is authored gameplay data, but may omit player-only ladders, drops or accessible roofs.',
 'This preview preserves native AI clearance margins; collision-boundary expansion is not applied.',
 'Door states, moving objects and ladder endpoint links are not inferred.',
 'No in-game installation or gameplay acceptance performed.'],
 format_reference='https://github.com/soulsmods/SoulsFormats/blob/master/SoulsFormats/Formats/NVA.cs')
(WORK/'geometry-qa.json').write_text(json.dumps(qa,indent=2))
print('NAV_READY',len(data['surface']['triangles']),flush=True)
