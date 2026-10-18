"""Private final-swapchain capture through the pinned renderer's supported UI hook."""
from pathlib import Path
from collections import Counter
import hashlib,re,struct,time,zlib

def capture_ui(session,timeout=20):
    session=Path(session);qa=session/'map-qa';captures=qa/'captures';captures.mkdir(exist_ok=True);trigger=qa/'capture.trigger'
    if trigger.exists():raise RuntimeError('A private UI capture is already pending')
    before={p:p.stat().st_mtime_ns for p in captures.glob('map-ui_*.raw')};trigger.write_text('capture\n',encoding='ascii');deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        for raw in captures.glob('map-ui_*.raw'):
            if before.get(raw)==raw.stat().st_mtime_ns:continue
            match=re.search(r'_(\d+)x(\d+)\.raw$',raw.name)
            if not match:continue
            width,height=map(int,match.groups());pixels=raw.read_bytes()
            if len(pixels)!=width*height*4:continue
            # Pinpoint known opaque UI text colors before choosing PNG byte order.
            palette=Counter(tuple(pixels[at:at+3]) for at in range(0,len(pixels),16));rgba=palette[(223,214,187)];bgra=palette[(187,214,223)]
            if max(rgba,bgra)<20:raise RuntimeError('Final UI capture lacks the known Atlas control palette')
            order='BGRA' if bgra>rgba else 'RGBA'
            converted=bytearray(pixels)
            if order=='BGRA':converted[0::4],converted[2::4]=pixels[2::4],pixels[0::4]
            def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
            scan=b''.join(b'\0'+converted[y*width*4:(y+1)*width*4] for y in range(height));png=raw.with_suffix('.png');png.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan,3))+chunk(b'IEND',b''))
            return [dict(path=str(png),sha256=hashlib.sha256(png.read_bytes()).hexdigest(),capture_kind='final_swapchain_including_atlas',raw_channel_order=order,channel_order_method='Known opaque Atlas paper text color',control_palette_samples=max(rgba,bgra),private=True)]
        time.sleep(.1)
    raise TimeoutError('No final Atlas UI swapchain capture arrived')
