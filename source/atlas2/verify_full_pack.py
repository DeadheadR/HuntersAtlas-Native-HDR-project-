"""Offline validation of every declared improved view; no native game or images."""
from pathlib import Path
from collections import OrderedDict
import argparse,hashlib,json,math,struct,time,zlib
from pack_format import sha,load_view,groups
def require(ok,why):
 if not ok:raise RuntimeError(why)
def main():
 p=argparse.ArgumentParser();p.add_argument('--pack-root',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--expected',type=int,default=602);a=p.parse_args();root=a.pack_root.resolve();index=json.loads((root/'atlas2-index.json').read_text());checked={};cache=OrderedDict();rows=[];began=time.monotonic();total_centroids=total_anchors=neighbors=degenerate=0
 def pixels(path,expected):
  path=path.resolve();path.relative_to(root)
  if path in checked:require(checked[path]==expected,"Conflicting identity for one tile path")
  if path in cache:cache.move_to_end(path);return cache[path]
  b=path.read_bytes()
  if path not in checked:require(hashlib.sha256(b).hexdigest()==expected,'Tile content identity');require(b[:12]==b'A2T1'+struct.pack('<II',260,260),'Tile dimensions');checked[path]=expected
  d=zlib.decompress(b[12:]);require(len(d)==260*260*4,'Decoded tile length');cache[path]=d
  if len(cache)>64:cache.popitem(last=False)
  return d
 for entry in index['areas']:
  area=root/entry['area'];mfile=area/'manifest.json';require(sha(mfile)==entry['manifest_sha256'],'Manifest identity');m=json.loads(mfile.read_text());base=json.loads((a.baseline/entry['area']/'manifest.json').read_text());source_path=a.assets/'maps'/(entry['region_id']+'.json');require(sha(source_path)==m['source_sha256']==base['source_sha256'],'Geometry identity');require(sha(area/'grid.json')==m['grid_sha256']==base['grid_sha256'],'Lookup grid changed');source=json.loads(source_path.read_text());require(m['bounds']==source['bounds'] and m['vertical_axis']=='Y' and m['layers']==base['layers'],'Area orientation/bounds/layer semantics');centroids=anchor_count=views=records=0
  for layer,header in enumerate(m['views']):
   if 'view_file' not in header:continue
   v=load_view(area,header);require(v['layer_index']==layer and v['source_sha256']==m['source_sha256'],'Floor identity');require(v['ppu']==16 and v['orientation']=='+X right, +Z up' and v['units']=='native-game-world-units' and v['vertical_axis']=='Y','Floor transform convention');require(v['world_bounds']==source['bounds'],'Floor world bounds');l=source['layers'][layer];require(abs(v['anchor']-l['anchor'])<.0005 and abs(v['span']-l['span'])<.0005,'Floor height semantics');b=m['bounds'];matrix=[16,0,-b[0]*16,0,-16,b[3]*16];require(v['world_to_image']==matrix,'Explicit transform matrix');require(v['width']==math.ceil((b[2]-b[0])*16) and v['height']==math.ceil((b[3]-b[1])*16),'Image dimensions');require(v['height_extent'][0]<=v['height_extent'][1],'Vertical extent');visible=None
   for g,tiles in groups(v):
    if g['shaded']==1 and g['fog_mode'] in ['off','any']:visible={(t['lod'],t['x'],t['y']):t for t in tiles}
    seen=set()
    for t in tiles:
     key=t['lod'],t['x'],t['y'];require(key not in seen,'Duplicate tile coordinate');seen.add(key);require(0<=t['lod']<v['levels'] and 0<=t['x']<math.ceil(v['width']/(256*2**t['lod'])) and 0<=t['y']<math.ceil(v['height']/(256*2**t['lod'])),'Tile coordinate bounds');pixels(area/t['file'],t['sha256']);records+=1
   require(visible is not None,'Normal material variant missing');line=v['line_overlay'];require(sha(area/line['file'])==line['sha256'],'Line index integrity');lines=json.loads((area/line['file']).read_text());require(len(lines['lines'])<=16384 and len(lines['cells'])<=16384,'Line index bound')
   require(len(l['triangles'])==len(l['heights']),'Per-vertex height count')
   if l['triangles']:
    extent=[min(min(t[0::2]) for t in l['triangles']),min(min(t[1::2]) for t in l['triangles']),max(max(t[0::2]) for t in l['triangles']),max(max(t[1::2]) for t in l['triangles'])];require(all(abs(x-y)<.0005 for x,y in zip(extent,v['valid_extent'])),'Per-floor valid extent');height_extent=[min(min(h) for h in l['heights']),max(max(h) for h in l['heights'])];require(all(abs(x-y)<.0005 for x,y in zip(height_extent,v['height_extent'])),'Per-floor vertical extent')
   else:require(v['valid_extent'] is None,'Empty floor extent')
   expected_lines=[]
   for ring in l['outlines']:
    for i,p0 in enumerate(ring):
     p1=ring[(i+1)%len(ring)]
     if math.hypot(p1[0]-p0[0],p1[1]-p0[1])>=1e-8:expected_lines.append([1,[*p0,*p1]])
   for wall in l['walls']:
    if math.hypot(wall[2]-wall[0],wall[3]-wall[1])>=1e-8:expected_lines.append([0,wall])
   require(len(expected_lines)==len(lines['lines']),'Line completeness')
   for expected_line,actual_line in zip(expected_lines,lines['lines']):require(expected_line[0]==actual_line[0] and all(abs(x-y)<.0005 for x,y in zip(expected_line[1],actual_line[1])),'Line geometry agreement')
   referenced=set()
   for cx,cz,ids in lines['cells']:
    for line_id in ids:
     require(0<=line_id<len(lines['lines']),'Line cell index');referenced.add(line_id)
   require(referenced==set(range(len(lines['lines']))),'Unindexed line segment')
   for t in l['triangles']:
    triangle_area=abs((t[2]-t[0])*(t[5]-t[1])-(t[4]-t[0])*(t[3]-t[1]))*.5
    if triangle_area<1e-8:degenerate+=1;continue
    x=(t[0]+t[2]+t[4])/3;z=(t[1]+t[3]+t[5])/3;u=(x-b[0])*16;vv=(b[3]-z)*16;require(math.hypot(b[0]+u/16-x,b[3]-vv/16-z)<1e-8,'Transform roundtrip');found=False
    for radius in [0,1,2]:
     for dy in range(-radius,radius+1):
      for dx in range(-radius,radius+1):
       px,py=math.floor(u)+dx,math.floor(vv)+dy;tx,ty=px//256,py//256;record=visible.get((0,tx,ty))
       if record:
        d=pixels(area/record['file'],record['sha256']);at=((py-ty*256+2)*260+px-tx*256+2)*4
        if d[at+3]:found=True;break
      if found:break
     if found:
      if radius:neighbors+=1
      break
    require(found,'Walkable centroid has no nearby raster coverage');centroids+=1
   views+=1
  poses=json.loads((area/'anchors.json').read_text())['poses']
  for x,y,z in poses:
   u=(x-m['bounds'][0])*16;vv=(m['bounds'][3]-z)*16;require(abs(m['bounds'][0]+u/16-x)<1e-8 and abs(m['bounds'][3]-vv/16-z)<1e-8,'Anchor roundtrip');anchor_count+=1
  rows.append(dict(area=entry['area'],improved_views=views,triangle_centroids=centroids,anchors=anchor_count,tile_records=records));total_centroids+=centroids;total_anchors+=anchor_count;print('FULL_PACK_VALIDATED '+json.dumps(rows[-1]),flush=True)
 count=sum(r['improved_views'] for r in rows);require(count==a.expected,'Exact improved-view count');report=dict(schema=1,pass_=True,areas=len(rows),improved_views=count,unique_tile_files_checked=len(checked),triangle_centroids=total_centroids,centroids_needing_neighbor_pixel=neighbors,degenerate_triangles_skipped=degenerate,anchor_roundtrips=total_anchors,pixel_cache_bound=64,seconds=time.monotonic()-began,areas_detail=rows,native_gameplay_tested=False,scope='Declared-file integrity, transforms and finite source-triangle centroid coverage; not every world coordinate or navigation readability');report['pass']=report.pop('pass_');a.report.write_text(json.dumps(report,indent=2));print('FULL_PACK_VALIDATION_PASS views='+str(count),flush=True)
if __name__=='__main__':main()
