"""Generate private CPU previews. Never print, attach or upload these game-derived images."""
from pathlib import Path
import argparse,hashlib,json,math,struct,zlib
def png(path,w,h,pixels):
    def chunk(kind,b):return struct.pack('>I',len(b))+kind+b+struct.pack('>I',zlib.crc32(kind+b))
    scan=b''.join(b'\0'+pixels[y*w*3:(y+1)*w*3] for y in range(h))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan,6))+chunk(b'IEND',b''))
def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();records=[]
    for label in ['Area02','Area10']:
        root=a.root/label;m=json.loads((root/'manifest.json').read_text());lod=max(0,math.ceil(math.log2(max(m['width'],m['height'])/1024)));factor=2**lod;w=math.ceil(m['width']/factor);h=math.ceil(m['height']/factor);pixels=bytearray([34,32,27])*(w*h)
        for view,base in [(m['context'],root/'context'),(m['views'][m['primary']],root/('F'+str(m['primary'])))]:
            for group in view['groups']:
                for t in group['tiles']:
                    if t['lod']!=lod:continue
                    data=(base/t['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==t['sha256'];rgba=zlib.decompress(data[12:]);assert len(rgba)==260*260*4
                    for y in range(256):
                        py=t['y']*256+y
                        if py>=h:break
                        for x in range(256):
                            px=t['x']*256+x
                            if px>=w:break
                            i=((y+2)*260+x+2)*4;j=(py*w+px)*3;alpha=rgba[i+3]
                            if not alpha:continue
                            for k in range(3):pixels[j+k]=(rgba[i+k]*alpha+pixels[j+k]*(255-alpha)+127)//255
        out=root/'developer-preview.png';png(out,w,h,pixels);records.append(dict(area=label,file=str(out),width=w,height=h,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),kind='private CPU static preview; no live-game capture'))
    (a.root.parent/'private-preview-evidence.json').write_text(json.dumps(records,indent=2));print('PRIVATE_CPU_PREVIEWS_SAVED',len(records))
if __name__=='__main__':main()
