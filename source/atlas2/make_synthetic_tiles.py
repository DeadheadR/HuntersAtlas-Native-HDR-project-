"""Create fresh numbered/color-coded tile fixtures containing no game data."""
from pathlib import Path
import argparse,hashlib,json,struct,zlib
DIGITS=['111101101101111','010110010010111','111001111100111','111001111001111','101101111001001','111100111001111','111100111101111','111001001001001','111101111101111','111101111001111']
def color(n):return [40+n*53%180,40+n*97%180,40+n*29%180,255]
def main():
 p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();root=a.output.resolve()
 if root.exists():raise RuntimeError('Fresh synthetic fixture root required')
 area=root/'Area01';area.mkdir(parents=True);sha=lambda b:hashlib.sha256(b).hexdigest()
 def write(path,j):b=json.dumps(j,sort_keys=True).encode();path.write_bytes(b);return sha(b)
 def tile(n,path):
  c=bytes(color(n));d=bytearray(c*(260*260));text=str(n);left=128-(len(text)*32-8)//2
  for k,ch in enumerate(text):
   for y in range(5):
    for x in range(3):
     if DIGITS[int(ch)][y*3+x]=='1':
      for yy in range(8):
       for xx in range(8):i=((96+y*8+yy)*260+left+k*32+x*8+xx)*4;d[i:i+4]=b'\xff\xff\xff\xff'
  b=b'A2T1'+struct.pack('<II',260,260)+zlib.compress(d,6);path.parent.mkdir(exist_ok=True);path.write_bytes(b);return sha(b)
 tiles=[]
 for y in range(16):
  for x in range(8):n=y*8+x;file=f'T{n:03}.a2t';tiles.append(dict(lod=0,x=x,y=y,file=file,sha256=tile(n,area/'F0'/file)))
 shared_hash=tile(7,area/'F1/shared.a2t');shared=[dict(t,file='shared.a2t',sha256=shared_hash) for t in tiles]
 grid_hash=write(area/'grid.json',dict(cell=8,anchors=[0,0],surfaces=[],cells=[]))
 m=dict(schema=1,region_id='synthetic_grid',vertical_axis='Y',tile_size=256,gutter=2,bounds=[0,0,256,512],ppu=8,width=2048,height=4096,levels=1,primary=0,layers=[{},{}],grid_sha256=grid_hash,context=dict(groups=[]),views=[dict(groups=[dict(requires=[],tiles=t)]) for t in (tiles,shared)])
 mh=write(area/'manifest.json',m);write(root/'atlas2-index.json',dict(schema=1,areas=[dict(area='Area01',region_id='synthetic_grid',manifest_sha256=mh)]));print('SYNTHETIC_FIXTURE_READY unique_tiles=128 shared_view_unique_tile=1 no_game_data=true')
if __name__=='__main__':main()
