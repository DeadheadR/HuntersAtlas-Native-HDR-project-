"""Bounded live comparison through discovered destinations and the guarded adapter."""
from pathlib import Path
import argparse,math,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import Channel,ProtocolError,atomic_json,classify_comparison,read_json,valid_pose

def menu(channel,pad):
    state=channel.read()
    if state.get('open'):state=channel.command('close')
    if not state.get('menu_top'):
        if not pad.is_file():raise ProtocolError('Private logical input file unavailable')
        try:pad.write_text('options',encoding='ascii');time.sleep(.35)
        finally:pad.write_text('',encoding='ascii')
        state=channel.wait(lambda s:s.get('menu_top') and s.get('menu_supported'),after=state['sequence'])
    return state

def one_destination(channel,destination,pad):
    menu(channel,pad);accepted=channel.command('atlas2-travel '+str(destination['return_point']))
    if accepted['ack'].get('travel_request_result')!=1:return dict(status='unavailable',reason='native_guard_rejected',gameplay_observed=False)
    arrival=destination['arrival_xyz'];parts=[int(x) for x in destination['region_id'][1:].split('_')];block=sum(v<<(24-8*i) for i,v in enumerate(parts))
    def arrived(s):
        pose=s.get('pose',{});status=s.get('travel_status')
        if status in (-1,-2):raise ProtocolError('Native travel failed after acceptance')
        return status==3 and valid_pose(pose) and pose['block']==block and math.dist([pose[k] for k in ('x','y','z')],arrival)<=3
    observed=channel.wait(arrived,after=accepted['sequence'],timeout=75)
    arrival_evidence=dict(arrival_confirmed=True,native_travel_status=observed['travel_status'],arrival_delta=math.dist([observed['pose'][k] for k in ('x','y','z')],arrival),arrival_pose=observed['pose'],gameplay_observed=True)
    try:
        # The travel monitor may finish before the native loading fade accepts input.
        settled=channel.clock()+2
        channel.wait(lambda s:channel.clock()>=settled and arrived(s),after=observed['sequence'],timeout=8)
        menu(channel,pad);channel.command('open');channel.command('atlas2-floor-auto');issued=channel.command('atlas2-static');static=channel.rendered(0,issued['sequence']);issued=channel.command('atlas2-reference');reference=channel.rendered(1,issued['sequence'])
    except ProtocolError as exc:return dict(status='unverified',reason=str(exc),**arrival_evidence)
    result=classify_comparison(static,reference);result.update(**arrival_evidence,pose=static['render']['pose'],reference_pose=reference['render']['pose'],static_frame=static['render']['frame'],reference_frame=reference['render']['frame'],static_cache={k:static.get(k) for k in ('visible_tiles','backend_ready_tiles','resident_slots','integrity_failures')})
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);p.add_argument('--max-destinations',type=int,default=2);p.add_argument('--maximum-seconds',type=int,default=300);a=p.parse_args()
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';session=a.session.resolve();session.relative_to(work.resolve());receipt=read_json(session/'launch.json');Path(receipt['user_dir']).resolve().relative_to(work.resolve());traces=list(session.rglob('trace.json.atlas2.json'))
    if len(traces)!=1:raise ProtocolError('Exactly one initialized native trace required')
    channel=Channel(traces[0],work/'Atlas2-test/bin/bb-probe.exe');initial=channel.read()
    if not valid_pose(initial.get('pose')):raise ProtocolError('Loaded copied-save player pose required')
    lock=session/'comparison-driver.lock'
    with lock.open('x',encoding='ascii') as stream:stream.write(str(channel.pid))
    rows=[];stop=time.monotonic()+a.maximum_seconds
    channel.deadline=stop
    try:
        channel.command('atlas2-floor-auto');channel.command('open');initial=channel.wait(lambda s:s.get('safe_destinations') is not None,after=channel.read()['sequence']);destinations=initial['safe_destinations'][:max(0,min(128,a.max_destinations))]
        for d in destinations:
            if time.monotonic()>=stop:break
            row=dict(area=d['area'],destination_id=d['return_point'])
            try:row.update(one_destination(channel,d,traces[0].parent/'pad.txt'))
            except ProtocolError as exc:row.update(status='unverified',reason=str(exc),gameplay_observed=False);rows.append(row);break
            rows.append(row);atomic_json(session/'comparison-summary.json',dict(schema=2,finite_sample=True,reserved_window=a.reserved_window,results=rows,completed=False))
            if row['status']=='unverified':break
    finally:
        lock.unlink(missing_ok=True);atomic_json(session/'comparison-summary.json',dict(schema=2,finite_sample=True,reserved_window=a.reserved_window,results=rows,completed=True,all_coordinates_claimed=False,performance_measured=False))
    print('ATLAS2_LIVE_COMPARISON destinations='+str(len(rows))+' matches='+str(sum(r['status']=='pass' for r in rows))+' mismatches='+str(sum(r['status']=='mismatch' for r in rows)))
if __name__=='__main__':main()
