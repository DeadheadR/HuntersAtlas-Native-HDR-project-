from pathlib import Path
import sys,struct
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P))
from config import MAP_ID,WORK,SRC
sys.path.insert(0,str(SRC))
import numpy as np
import pipeline_context as c
from config import GAME_DIR
c.configure(GAME_DIR,WORK/'extract')
import soulstruct_local_config
sys.modules['soulstruct.config']=soulstruct_local_config
from soulstruct.containers import Binder
from soulstruct.dcx import decompress
from generate_navigation_maps import transformed
from navmesh_reader import decode
import hashlib

def read_map_offset(path):
 raw=decompress(path.read_bytes())[0]
 def text(o):
  end=o
  while end+2<=len(raw) and raw[end:end+2]!=b"\0\0": end+=2
  return raw[o:end].decode("utf-16le")
 lists={};off=16;visited=set()
 while off:
  if off in visited: raise ValueError("Cyclic MSB")
  visited.add(off);_,count,nameoff=struct.unpack_from("<iiq",raw,off)
  offsets=struct.unpack_from(f"<{count}q",raw,off+16);lists[text(nameoff)]=offsets[:-1];off=offsets[-1]
 rows=[]
 for entry in lists.get("EVENT_PARAM_ST",[]):
  subtype=struct.unpack_from("<i",raw,entry+12)[0]
  if subtype!=9: continue
  name=text(entry+struct.unpack_from("<q",raw,entry)[0]);dataoff=struct.unpack_from("<q",raw,entry+32)[0]
  translate=struct.unpack_from("<3f",raw,entry+dataoff);rotation=struct.unpack_from("<f",raw,entry+dataoff+12)[0]
  rows.append({"name":name,"translation":list(translate),"rotation_y_degrees":rotation})
 if len(rows)>1: raise ValueError(f"Expected at most one MapOffset event, got {len(rows)}")
 return rows[0] if rows else {"name":None,"translation":[0.,0.,0.],"rotation_y_degrees":0.}

path=c.GAME_DATA/f'map/{MAP_ID}/{MAP_ID}.nvmhktbnd.dcx'
nva=decompress((c.GAME_DATA/f'map/{MAP_ID}/{MAP_ID}.nva.dcx').read_bytes())[0]
assert nva[:4]==b'NVMA' and struct.unpack_from('<I',nva,4)[0]==4
sec,version,length,count=struct.unpack_from('<4I',nva,16);assert sec==0 and version==3 and count<10000
placements=[]
map_offset=read_map_offset(c.GAME_DATA/f"map/mapstudio/{MAP_ID}.msb.dcx")
angle=np.radians(map_offset["rotation_y_degrees"]);cy,sy=np.cos(angle),np.sin(angle)
map_rot=np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]],dtype=np.float64)
for i in range(count):
 o=32+i*144;pos=struct.unpack_from('<3f',nva,o);rot=struct.unpack_from('<3f',nva,o+16);scale=struct.unpack_from('<3f',nva,o+32);name,model=struct.unpack_from('<2i',nva,o+48)
 placements.append(dict(name=name,model=model,pos=pos,rot=list(np.degrees(rot)),scale=scale))
b=Binder.from_path(path);lookup={}
for e in b.entries:
 t,n,er=decode(e.get_uncompressed_data());lookup[int(e.name.rsplit('_',1)[1].split('.')[0])]=(t,n)
meshes=[];rows=[]
for part in placements:
 if part['model'] not in lookup: continue
 t,n=lookup[part['model']]
 if not len(t): continue
 t=transformed(t,part);t=(t@map_rot.T+np.asarray(map_offset['translation'])).astype(np.float32);meshes.append(t);rows.append(dict(name=part['name'],model=part['model'],placement=part,faces=n,triangles=len(t),bounds=[t.min(axis=(0,1)).tolist(),t.max(axis=(0,1)).tolist()]))
if not meshes: raise RuntimeError('NVA placements resolved to no navmesh triangles')
t=np.concatenate(meshes);np.save(WORK/'navmesh-triangles.npy',t)
(WORK/'navmesh-inventory.json').write_text(__import__('json').dumps(rows,indent=2))
(WORK/'map-offset.json').write_text(__import__('json').dumps({'map_id':MAP_ID,'event':map_offset,'msb_sha256':hashlib.sha256((c.GAME_DATA/f'map/mapstudio/{MAP_ID}.msb.dcx').read_bytes()).hexdigest(),'application':'NVA placement transform, then MSB MapOffset yaw and translation'},indent=2))
print('NAVMESH',MAP_ID,len(rows),len(t),flush=True)
