from pathlib import Path
import sys,struct
P=Path(__file__).resolve().parent
import numpy as np
def decode(raw):
 assert raw[:8]==bytes.fromhex('57e0e05710c0c010')
 start=struct.unpack_from('<h',raw,0x3e)[0]+0x40
 ss=[struct.unpack_from('<7I',raw,start+i*64+20) for i in range(3)]
 names=ss[0][0];base,lo,gl,vi,ex,_,end=ss[2]
 fix={}
 for o in range(base+lo,base+gl-7,8):
  a,b=struct.unpack_from('<2I',raw,o)
  if a!=0xffffffff:fix[a]=b
 for o in range(base+gl,base+vi-11,12):
  a,sid,b=struct.unpack_from('<3I',raw,o)
  if a!=0xffffffff and sid==2:fix[a]=b
 nav=[]
 for o in range(base+vi,base+ex-11,12):
  a,sid,n=struct.unpack_from('<3I',raw,o)
  if a!=0xffffffff and raw[names+n:].split(b'\0',1)[0]==b'hkaiNavMesh':nav.append(a)
 assert len(nav)==1
 a=nav[0]
 def arr(off,dt,size):
  count=struct.unpack_from('<I',raw,base+a+off+8)[0];assert count<1000000
  if not count:return np.empty((0,size))
  ptr=fix[a+off];assert ptr+count*np.dtype(dt).itemsize*size<=lo
  return np.frombuffer(raw,dtype=dt,count=count*size,offset=base+ptr).reshape(count,size).copy()
 # Havok2014 hkReferencedObject size is 16 (2018 schema is 24).
 faces=arr(16,'<i2',8);edges=arr(32,'<u4',5);vertices=arr(48,'<f4',4)
 triangles=[];polygons=[]
 for f in faces:
  start,num=struct.unpack('<i',f[:2].tobytes())[0],int(f[4]);assert 3<=num<=64
  assert 0<=start<len(edges) and start+num<=len(edges)
  es=edges[start:start+num];assert (es[:,:2]<len(vertices)).all()
  assert all(int(es[k,1])==int(es[(k+1)%num,0]) for k in range(num))
  verts=vertices[es[:,0].astype(int),:3];assert np.isfinite(verts).all()
  polygons.append(verts)
  for k in range(1,len(verts)-1):triangles.append(verts[[0,k,k+1]])
 return np.array(triangles,dtype=np.float32),len(faces),float(struct.unpack_from('<f',raw,base+a+168)[0])
