"""Read versioned private pack metadata, including lazy per-view manifests."""
from pathlib import Path
import hashlib,json
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_view(area,entry):
 if 'view_file' not in entry:return entry
 path=(Path(area)/entry['view_file']).resolve();path.relative_to(Path(area).resolve())
 if sha(path)!=entry['view_sha256']:raise RuntimeError('View content identity mismatch')
 v=json.loads(path.read_text())
 for k in ['layer_index','ppu','width','height','levels','world_to_image']:
  if v[k]!=entry[k]:raise RuntimeError('View/header mismatch: '+k)
 return v
def groups(view):
 for g in view['groups']:
  records=view['tile_sets'][g['tile_set']] if 'tile_set' in g else g['tiles'];tiles=[]
  for t in records:
   tiles.append(dict(lod=t[0],x=t[1],y=t[2],file='objects/'+t[3]+'.a2t',sha256=t[3]) if isinstance(t,list) else t)
  yield g,tiles
