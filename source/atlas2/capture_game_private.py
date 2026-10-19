"""Supported pre-overlay frame capture for private gameplay/OCR checks only."""
from pathlib import Path
import argparse,hashlib,re,struct,time,zlib
from launch_session import verify_lease
from live_protocol import Channel
def capture_game(session,timeout=20):
 session=Path(session);qa=session/'map-qa';folder=qa/'captures';folder.mkdir(exist_ok=True);trigger=qa/'frame.trigger'
 if trigger.exists():raise RuntimeError('A supported game-frame request is already pending')
 files=list(folder.glob('output_*.raw'))
 if len(files)>=64:raise RuntimeError('Private gameplay capture count bound reached')
 before={p:p.stat().st_mtime_ns for p in files};trigger.write_text('capture\n',encoding='ascii');deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  for raw in folder.glob('output_*.raw'):
   if before.get(raw)==raw.stat().st_mtime_ns:continue
   match=re.search(r'_(\d+)x(\d+)\.raw$',raw.name)
   if not match:continue
   width,height=map(int,match.groups());data=raw.read_bytes()
   if len(data)!=width*height*4:continue
   def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
   scan=b''.join(b'\0'+data[y*width*4:(y+1)*width*4] for y in range(height));png=raw.with_suffix('.png');png.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan,3))+chunk(b'IEND',b''));return dict(path=str(png),sha256=hashlib.sha256(png.read_bytes()).hexdigest(),capture_kind='pre_overlay_game_frame',private=True,not_valid_for_atlas_visual_comparison=True)
  time.sleep(.1)
 raise TimeoutError('Supported game-frame capture did not arrive')
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=a.session.resolve();s.relative_to(w.resolve());verify_lease(w,a.reserved_window);Channel(s/'map-qa/trace.json.atlas2.json',w/'Atlas2-test/bin/bb-probe.exe',max_age=30).read();capture_game(s);print('PRIVATE_GAME_FRAME_CAPTURED no_upload=true')
if __name__=='__main__':main()
