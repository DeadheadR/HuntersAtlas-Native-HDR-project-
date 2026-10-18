"""Attach later to one private native session; never starts a game or reserves GPU."""
from pathlib import Path
import argparse,math,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import Channel,ProtocolError,atomic_json,matched_pose

def same_view(a,b):
    if not isinstance(b.get('v1_layer'),int) or b['v1_layer']<0:return False,'v1_reference_not_confirmed'
    if not matched_pose(a.get('pose'),b.get('pose')):return False,'pose_changed'
    pa,pb=a['pose'],b['pose'];z=a.get('zoom',0)
    if not isinstance(z,(int,float)) or z<=0:return False,'view_zoom_missing'
    if math.hypot(pa['x']-pb['x'],pa['z']-pb['z'])*z>.25 or abs(pa['y']-pb['y'])>1e-4:return False,'pose_exceeds_visual_pixel_budget'
    if abs((pa['yaw']-pb['yaw']+math.pi)%(2*math.pi)-math.pi)>1e-4:return False,'facing_changed'
    for key in ['region_id','layer','ui_scale','canvas_size','viewport_size','feature_settings']:
        if key not in a or a[key]!=b.get(key):return False,'view_field_differs_'+key
    for key in ['zoom','center']:
        left=a.get(key);right=b.get(key)
        if isinstance(left,(int,float)) and isinstance(right,(int,float)):
            if not math.isclose(left,right,rel_tol=0,abs_tol=1e-5):return False,'view_field_differs_'+key
        elif isinstance(left,list) and isinstance(right,list) and len(left)==len(right):
            if any(not math.isclose(x,y,rel_tol=0,abs_tol=1e-5) for x,y in zip(left,right)):return False,'view_field_differs_'+key
        else:return False,'view_field_missing_'+key
    return True,'matched'

def pair(channel,preset,capture=None):
    before=channel.command('atlas2-static');static=channel.rendered(0,before['sequence'])
    static_images=capture() if capture else []
    before=channel.command('atlas2-reference');reference=channel.rendered(1,before['sequence'])
    reference_images=capture() if capture else []
    same,reason=same_view(static.get('render',{}),reference.get('render',{}))
    return dict(preset=preset,status='matched_view_pending_visual_review' if same else 'inconclusive',reason=reason,static=static,reference=reference,private_images=dict(static=static_images,reference=reference_images),images_attached=False,pixel_identity_claimed=False,gameplay_fps_measured=False)

def zoom_limit(channel,direction):
    last=None
    for _ in range(32):
        issued=channel.command('zoom-'+direction)
        state=channel.rendered(0,issued['sequence']);value=state['render']['zoom']
        if last is not None and math.isclose(last,value,abs_tol=1e-5,rel_tol=0):return state
        last=value
    raise ProtocolError('Zoom limit did not stabilize within bounded steps')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);p.add_argument('--capture',action='store_true',help='Keep supported frame dumps private inside this session');p.add_argument('--presets',nargs='+',choices=['default','fit','maximum_scaled','minimum_scaled'],default=['default','maximum_scaled']);a=p.parse_args()
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';session=a.session.resolve();session.relative_to(work.resolve());channel=Channel(session/'map-qa/trace.json.atlas2.json',work/'Atlas2-test/bin/bb-probe.exe');channel.command('open');issued=channel.command('atlas2-static');state=channel.rendered(0,issued['sequence']);strict=state['render'].get('strict_layer')
    if not isinstance(strict,int) or strict<0:raise ProtocolError('A confirmed current floor is required')
    channel.command('atlas2-floor '+str(strict));rows=[];capture=None
    if a.capture:
        from capture_ui import capture_ui
        def capture():
            return capture_ui(session,timeout=20)
    try:
        for preset in a.presets:
            channel.command('atlas2-static');issued=channel.command('recenter');channel.rendered(0,issued['sequence'])
            if preset=='fit':issued=channel.command('fit');channel.rendered(0,issued['sequence'])
            elif preset=='maximum_scaled':zoom_limit(channel,'in')
            elif preset=='minimum_scaled':zoom_limit(channel,'out')
            rows.append(pair(channel,preset,capture));atomic_json(session/'matching-view-comparisons.json',dict(schema=1,reserved_window=a.reserved_window,comparisons=rows,visual_acceptance='unverified',all_coordinates_claimed=False))
    finally:channel.command('atlas2-floor-auto');channel.command('atlas2-static')
    print('MATCHED_VIEW_PAIRS_RECORDED='+str(sum(r['status']=='matched_view_pending_visual_review' for r in rows)))
if __name__=='__main__':main()
