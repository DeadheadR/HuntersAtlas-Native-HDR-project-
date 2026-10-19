"""Read versioned private pack metadata, including lazy per-view manifests."""
from pathlib import Path
import hashlib,json,os
def shared_open(path):
 """Allow the owning writer to atomically replace this path during a read."""
 if os.name!='nt':return Path(path).open('rb')
 import ctypes,msvcrt
 kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p];kernel.CreateFileW.restype=ctypes.c_void_p;kernel.CloseHandle.argtypes=[ctypes.c_void_p]
 handle=kernel.CreateFileW(str(Path(path).resolve()),0x80000000,7,None,3,0x80,None)
 if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
 try:fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
 except BaseException:kernel.CloseHandle(handle);raise
 return os.fdopen(fd,'rb')
def shared_read(path):
 with shared_open(path) as stream:return stream.read()
def sha(path):return hashlib.sha256(shared_read(path)).hexdigest()
def load_view(area,entry):
 if 'view_file' not in entry:return entry
 path=(Path(area)/entry['view_file']).resolve();path.relative_to(Path(area).resolve())
 data=shared_read(path)
 if hashlib.sha256(data).hexdigest()!=entry['view_sha256']:raise RuntimeError('View content identity mismatch')
 v=json.loads(data)
 for k in ['layer_index','ppu','width','height','levels','world_to_image']:
  if v[k]!=entry[k]:raise RuntimeError('View/header mismatch: '+k)
 return v
def groups(view):
 for g in view['groups']:
  records=view['tile_sets'][g['tile_set']] if 'tile_set' in g else g['tiles'];tiles=[]
  for t in records:
   tiles.append(dict(lod=t[0],x=t[1],y=t[2],file='objects/'+t[3]+'.a2t',sha256=t[3]) if isinstance(t,list) else t)
  yield g,tiles
