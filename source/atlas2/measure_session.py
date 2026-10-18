"""Controlled, bounded present-interval and map-CPU measurements on a private copied save."""
from pathlib import Path
import argparse,json,math,statistics,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import Channel,ProtocolError,atomic_json,matched_pose,read_json,valid_pose
from live_compare import menu

def distribution(values,discard=0):
    values=values[discard:]
    if not values:return dict(samples=0)
    ordered=sorted(values)
    def quantile(p):
        at=(len(ordered)-1)*p;lo=int(at);hi=min(lo+1,len(ordered)-1);return ordered[lo]+(ordered[hi]-ordered[lo])*(at-lo)
    mean=statistics.mean(values)
    return dict(samples=len(values),mean_ms=mean,median_ms=statistics.median(values),p95_ms=quantile(.95),p99_ms=quantile(.99),min_ms=min(values),max_ms=max(values),population_variance_ms2=statistics.pvariance(values),sample_stddev_ms=statistics.stdev(values) if len(values)>1 else None,fps_from_interval_mean=1000/mean if mean else None)

def settle(channel,seconds,pose):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        s=channel.read()
        if not matched_pose(pose,s['pose']) or not s['menu_top']:raise ProtocolError('Stationary paused pose changed')
        time.sleep(.15)

def sample(channel,session,condition,seconds,pose,*,cold=False):
    reference=condition.startswith('reference');closed=condition.endswith('closed');disabled=condition=='ui_disabled'
    if cold:
        channel.command('close');issued=channel.command('atlas2-measure-open-'+('reference ' if reference else 'static ')+condition)
    else:
        channel.command('enable');channel.command('atlas2-reference' if reference else 'atlas2-static')
        if closed or disabled:
            channel.command('close')
            if disabled:channel.command('disable')
        else:
            channel.command('open');channel.command('recenter');channel.rendered(1 if reference else 0,channel.read()['sequence'])
        settle(channel,2,pose);issued=channel.command('atlas2-measure-start '+condition)
    generation=issued['ack']['measurement_generation'];started=issued
    settle(channel,seconds,pose);stopped=channel.command('atlas2-measure-stop');data=read_json(channel.trace.parent/'trace.json.measurement.json')
    if data.get('generation')!=generation or data.get('condition')!=condition or data.get('overflow'):raise ProtocolError('Measurement generation/content mismatch')
    if not matched_pose(pose,stopped['pose']):raise ProtocolError('Measured pose changed')
    target=session/'measurements'/('g'+str(generation)+'-'+condition+'.json');target.parent.mkdir(exist_ok=True);atomic_json(target,data)
    row=dict(condition=condition,generation=generation,cold=cold,cold_definition='First use of this area/render path in this process; OS file/shader caches may already be warm' if cold else None,pose=pose,pose_matched=True,native_menu_paused=True,present=distribution(data['present_interval_ms'],0 if cold else 2),map_cpu=distribution(data['map_cpu_elapsed_ms'],0 if cold else 2),setup_cpu_elapsed_ms=data['setup_cpu_elapsed_ms'],first_present_interval_ms=data['present_interval_ms'][0] if data['present_interval_ms'] else None,first_map_cpu_elapsed_ms=data['map_cpu_elapsed_ms'][0] if data['map_cpu_elapsed_ms'] else None,raw_samples=str(target),before=started,after=stopped,seconds_requested=seconds)
    row['map_cpu'].pop('fps_from_interval_mean',None)
    return row

def travel(channel,destination,pad):
    menu(channel,pad);accepted=channel.command('atlas2-travel '+str(destination['return_point']))
    if accepted['ack'].get('travel_request_result')!=1:raise ProtocolError('Guarded travel rejected')
    parts=[int(v) for v in destination['region_id'][1:].split('_')];block=sum(v<<(24-8*i) for i,v in enumerate(parts));arrival=destination['arrival_xyz']
    def arrived(s):return s.get('travel_status')==3 and valid_pose(s.get('pose')) and s['pose']['block']==block and math.dist([s['pose'][k] for k in ('x','y','z')],arrival)<=3
    observed=channel.wait(arrived,after=accepted['sequence'],timeout=75);end=time.monotonic()+2
    channel.wait(lambda s:time.monotonic()>=end and arrived(s),after=observed['sequence'],timeout=10);return menu(channel,pad)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);p.add_argument('--seconds',type=float,default=12);p.add_argument('--max-areas',type=int,default=4);p.add_argument('--resume',action='store_true');a=p.parse_args()
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';session=a.session.resolve();session.relative_to(work.resolve());receipt=read_json(session/'launch.json');Path(receipt['user_dir']).resolve().relative_to(work.resolve());c=Channel(session/'map-qa/trace.json.atlas2.json',work/'Atlas2-test/bin/bb-probe.exe',max_age=30);initial=c.read()
    if not valid_pose(initial.get('pose')) or not initial.get('measurement',{}).get('enabled'):raise ProtocolError('Loaded private pose and opt-in measurement build required')
    lock=session/'comparison-driver.lock'
    with lock.open('x') as stream:stream.write(str(c.pid))
    rows=[];areas=[];report=dict(schema=1,reserved_window=a.reserved_window,results=rows,areas=areas,complete=False,frame_clock='Native present hook interval, includes pacing; not GPU timestamps',map_cpu_clock='Elapsed wall time of complete BbMap::Draw CPU scope; excludes Vulkan render backend',startup_disabled_baseline=False,visual_features_equal=False,static_visual_differences_document='source/atlas2/VISUAL-PARITY.md',all_coordinates_claimed=False)
    if a.resume:
        report=read_json(session/'controlled-measurements.json')
        if report.get('complete') or report.get('reserved_window')!=a.reserved_window:raise ProtocolError('An incomplete matching reservation is required to resume')
        rows=report['results'];areas=report['areas']
        if rows and rows[-1]['after']['process_id']!=c.pid:raise ProtocolError('Cannot resume cold/warm series across process changes')
        report.setdefault('interruptions',[]).append(dict(reason='Transient telemetry read stopped driver; existing native samples retained',completed_conditions=len(rows)))
    try:
        menu(c,c.trace.parent/'pad.txt');initial=c.read();atomic_json(session/'destination-inventory.json',dict(native_travel_supported=initial['travel_supported'],inventory=initial['destination_inventory']))
        index=read_json(work/'packs/atlas2-index.json')['areas'];initial_block=initial['pose']['block'];current=next((e['area'] for e in index if sum(int(v)<<(24-8*i) for i,v in enumerate(e['region_id'][1:].split('_')))==initial_block),None)
        destinations={}
        for d in initial['safe_destinations']:destinations.setdefault(d['area'],d)
        order=([current] if current else [])+[x for x in destinations if x!=current]
        for area in order:
            if len(areas)>=a.max_areas:break
            if any(x['area']==area for x in areas):continue
            if area!=current:travel(c,destinations[area],c.trace.parent/'pad.txt')
            current=area;pose=c.read()['pose'];area_rows=[]
            prior=[r for r in rows if r['area']==area]
            if prior and not matched_pose(prior[-1]['pose'],pose):raise ProtocolError('Partial area pose changed; refusing mixed-pose resume')
            for condition in ('static_cold','reference_cold'):
                if any(r['condition']==condition for r in prior):continue
                row=sample(c,session,condition,5,pose,cold=True);row['area']=area;rows.append(row);area_rows.append(row);atomic_json(session/'controlled-measurements.json',report)
                print(json.dumps(dict(area=area,condition=condition,present=row['present'],map_cpu=row['map_cpu'])),flush=True)
            ordering=['static_warm_a','reference_warm_a','reference_warm_b','static_warm_b']
            if len(areas)%2:ordering=['reference_warm_a','static_warm_a','static_warm_b','reference_warm_b']
            for condition in ordering+['static_closed','reference_closed','ui_disabled']:
                if any(r['condition']==condition for r in prior):continue
                row=sample(c,session,condition,a.seconds,pose);row['area']=area;rows.append(row);area_rows.append(row);atomic_json(session/'controlled-measurements.json',report)
                print(json.dumps(dict(area=area,condition=condition,present=row['present'],map_cpu=row['map_cpu'])),flush=True)
            c.command('enable');c.command('open');issued=c.command('atlas2-static');s=c.rendered(0,issued['sequence']);issued=c.command('atlas2-reference');r=c.rendered(1,issued['sequence'])
            areas.append(dict(area=area,pose=pose,strict_layer=s['render']['strict_layer'],rendered_layer=s['render']['layer'],reference_layer=r['render']['v1_layer'],pose_matched=matched_pose(s['render']['pose'],r['render']['pose'])));atomic_json(session/'controlled-measurements.json',report)
            refreshed=c.read();atomic_json(session/'destination-inventory.json',dict(native_travel_supported=refreshed['travel_supported'],inventory=refreshed['destination_inventory']))
            for d in refreshed['safe_destinations']:
                destinations.setdefault(d['area'],d)
                if d['area'] not in order:order.append(d['area'])
        report['complete']=True
    finally:
        try:c.command('atlas2-measure-stop');c.command('enable');c.command('atlas2-static');c.command('close')
        finally:lock.unlink(missing_ok=True);atomic_json(session/'controlled-measurements.json',report)
    print('CONTROLLED_MEASUREMENT_COMPLETE areas='+str(len(areas))+' conditions='+str(len(rows)),flush=True)
if __name__=='__main__':main()
