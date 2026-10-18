"""Private numerical raster-to-final-swapchain check; never emits game images."""
from pathlib import Path
import argparse,json,math,zlib

def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--pack-root',type=Path,required=True);a=p.parse_args();pairs=json.loads((a.session/'matching-view-comparisons.json').read_text());rows=[]
    for pair in pairs['comparisons']:
        state=pair['static'];r=state['render'];image=pair['private_images']['static'][0];raw=Path(image['path']).with_suffix('.raw').read_bytes();width,height=map(int,r['viewport_size']);m=json.loads((a.pack_root/r['area']/'manifest.json').read_text());v=m['views'][r['layer']];lod=state['lod'];density=v['ppu']/2**lod
        # This fixture has one revealed rule, confirmed by the unchanged native V1 canvas.
        groups=[g for g in v['groups'] if g['shaded']==1 and g['fog_mode']=='on' and g['requires']==[0] and not g['forbids']]
        if len(groups)!=1:continue
        tiles={(t['x'],t['y']):t for t in groups[0]['tiles'] if t['lod']==lod};decoded={};scale=r['ui_scale'];ox=(width-1280*scale)/2+230*scale;oy=(height-720*scale)/2+114*scale;cw,ch=r['canvas_size'];cx,cz=r['center'];count=close=0;absolute=0
        for sy in range(int(oy)+8,int(oy+ch)-8,8):
            for sx in range(int(ox)+8,int(ox+cw)-8,8):
                wx=cx+(sx+.5-ox-cw/2)/r['zoom'];wz=cz-(sy+.5-oy-ch/2)/r['zoom'];u=(wx-m['bounds'][0])*density;vv=(m['bounds'][3]-wz)*density;tx,ty=math.floor(u/256),math.floor(vv/256);t=tiles.get((tx,ty))
                if not t:continue
                key=t['file']
                if key not in decoded:decoded[key]=zlib.decompress((a.pack_root/r['area']/key).read_bytes()[12:])
                data=decoded[key];px=u-tx*256+2-.5;py=vv-ty*256+2-.5;ix,iy=math.floor(px),math.floor(py)
                if not 0<=ix<259 or not 0<=iy<259:continue
                samples=[data[(y*260+x)*4:(y*260+x)*4+4] for y in (iy,iy+1) for x in (ix,ix+1)]
                if any(c[3]!=255 for c in samples):continue
                if any(max(c[k] for c in samples)-min(c[k] for c in samples)>5 for k in range(3)):continue
                ax,ay=px-ix,py-iy;predicted=[samples[0][k]*(1-ax)*(1-ay)+samples[1][k]*ax*(1-ay)+samples[2][k]*(1-ax)*ay+samples[3][k]*ax*ay for k in range(3)];rgb=list(raw[(sy*width+sx)*4:(sy*width+sx)*4+3])
                if image['raw_channel_order']=='BGRA':rgb.reverse()
                delta=[abs(rgb[k]-predicted[k]) for k in range(3)];absolute+=sum(delta);close+=max(delta)<=8;count+=1
        rows.append(dict(preset=pair['preset'],opaque_samples=count,within_8=close,fraction_within_8=close/count if count else None,rgb_mae=absolute/(3*count) if count else None,limits='Includes vector lines, icons, edge fades and tooltips drawn above base tiles; not a semantic equivalence test'))
    report=dict(schema=1,images_private=True,results=rows);(a.session/'tile-projection-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(rows))
if __name__=='__main__':main()
