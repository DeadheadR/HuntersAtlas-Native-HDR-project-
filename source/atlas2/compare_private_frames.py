"""Local pixel comparisons only. Never emits, uploads or attaches game-derived images."""
from pathlib import Path
import argparse,hashlib,json,math,re,statistics

def load(path):
    path=Path(path).with_suffix('.raw');match=re.search(r'_(\d+)x(\d+)\.raw$',path.name)
    if not match:raise RuntimeError('Unknown private frame dimensions')
    width,height=map(int,match.groups());data=path.read_bytes()
    if len(data)!=width*height*4:raise RuntimeError('Private frame size mismatch')
    return data,width,height,hashlib.sha256(data).hexdigest()

def metric(a,b,width,height,box,step):
    x0,y0,x1,y1=map(int,box);n=0;absolute=squared=changed=large=0
    for y in range(max(0,y0),min(height,y1),step):
        for x in range(max(0,x0),min(width,x1),step):
            at=(y*width+x)*4;ds=[abs(a[at+k]-b[at+k]) for k in range(3)];absolute+=sum(ds);squared+=sum(d*d for d in ds);changed+=max(ds)>8;large+=max(ds)>32;n+=1
    return dict(sampled_pixels=n,stride=step,rgb_mae_0_255=absolute/(3*n) if n else None,rgb_rmse_0_255=math.sqrt(squared/(3*n)) if n else None,fraction_with_any_rgb_delta_over_8=changed/n if n else None,fraction_with_any_rgb_delta_over_32=large/n if n else None)

def colored_patch(a,b,width,height,px,py,radius):
    masks=[]
    for data in (a,b):
        pixels=set()
        for y in range(max(0,int(py-radius)),min(height,int(py+radius))):
            for x in range(max(0,int(px-radius)),min(width,int(px+radius))):
                rgb=data[(y*width+x)*4:(y*width+x)*4+3]
                if max(rgb)>=150 and max(rgb)-min(rgb)>=85:pixels.add((x,y))
        masks.append(pixels)
    left,right=masks;union=left|right
    centroid=lambda mask:(statistics.mean(p[0] for p in mask),statistics.mean(p[1] for p in mask)) if mask else None
    ca,cb=centroid(left),centroid(right)
    return dict(high_saturation_pixels=[len(left),len(right)],intersection_over_union=len(left&right)/len(union) if union else None,centroid_pixel_delta=math.dist(ca,cb) if ca and cb else None,semantic_alignment_verified=False,interpretation='High-saturation pixels near projected player position; pixel identity does not establish marker identity or readability')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);a=p.parse_args();session=a.session.resolve();pairs=json.loads((session/'matching-view-comparisons.json').read_text());rows=[]
    for pair in pairs['comparisons']:
        if pair['status']!='matched_view_pending_visual_review':continue
        if any(pair['private_images'][kind][0].get('capture_kind')!='final_swapchain_including_atlas' for kind in ('static','reference')):
            rows.append(dict(area=pair['static']['render']['area'],preset=pair['preset'],status='rejected_pre_overlay_game_buffer',visual_identity_pass=False));continue
        left=pair['private_images']['static'][0]['path'];right=pair['private_images']['reference'][0]['path'];aa,w,h,ha=load(left);bb,ww,hh,hb=load(right)
        if (w,h)!=(ww,hh):raise RuntimeError('Paired frame size mismatch')
        r=pair['static']['render'];scale=r['ui_scale'];ox=(w-1280*scale)/2+230*scale;oy=(h-720*scale)/2+114*scale;cw,ch=r['canvas_size'];center=r['center'];pose=r['pose'];px=ox+cw/2+(pose['x']-center[0])*r['zoom'];py=oy+ch/2-(pose['z']-center[1])*r['zoom']
        row=dict(area=r['area'],preset=pair['preset'],status='private_pixel_comparison_completed',zoom=r['zoom'],dimensions=[w,h],map_canvas=metric(aa,bb,w,h,(ox,oy,ox+cw,oy+ch),2),header_control_patch=metric(aa,bb,w,h,(0,0,w,oy-10*scale),4),player_color_patch=colored_patch(aa,bb,w,h,px,py,15*scale),private_raw_sha256=[ha,hb],visual_identity_pass=False)
        rows.append(row)
    report=dict(schema=1,method='Sampled RGB differences on private same-pose same-view native frame dumps',images_attached=False,images_uploaded=False,comparisons=rows,visual_identity_accepted=False,navigation_readability_accepted=False,limits=['Pixel differences include intentional prototype color/material/hatch/stroke differences','No subjective human navigation-readability review is represented','RGB metrics are not perceptual or semantic equivalence tests'])
    (session/'private-pixel-comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps([dict(area=r['area'],preset=r['preset'],status=r['status'],map_rgb_mae=r.get('map_canvas',{}).get('rgb_mae_0_255'),glyph_patch_iou=r.get('player_color_patch',{}).get('intersection_over_union')) for r in rows]))
if __name__=='__main__':main()
