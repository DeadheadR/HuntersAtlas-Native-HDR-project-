"""Drive only discovered, eligible destinations through the existing guarded adapter.

Attach to one isolated session. No native launch, raw memory writes, flag edits or save edits.
"""
from pathlib import Path
import argparse,json,math,time
def read(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {}
def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);p.add_argument('--max-destinations',type=int,default=128);a=p.parse_args()
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';session=a.session.resolve();session.relative_to(work.resolve());receipt=read(session/'launch.json');Path(receipt['user_dir']).resolve().relative_to(work.resolve())
    # Existing driver's control root is documented by its launch receipt/session layout.
    control=session/'control';control.mkdir(exist_ok=True)
    # Accept the existing driver's actual qa/control path; never guess a process address.
    candidates=[session/'control.txt',session/'control/control.txt',session/'qa/control.txt']
    trace_candidates=[session/'trace.json.atlas2.json',session/'control/trace.json.atlas2.json',session/'qa/trace.json.atlas2.json']
    trace=next((x for x in trace_candidates if x.is_file()),None)
    if trace is None:
        matches=list(session.rglob('trace.json.atlas2.json'))
        if len(matches)!=1:raise RuntimeError('One active Atlas2 QA trace is required')
        trace=matches[0]
    command=trace.parent/'control.txt'
    def send(text):
        if command.exists():raise RuntimeError('Previous test command is still pending')
        temp=command.with_suffix('.tmp');temp.write_text(text+'\n');temp.replace(command)
    def wait(predicate,timeout=45):
        stop=time.monotonic()+timeout
        while time.monotonic()<stop:
            value=read(trace)
            if predicate(value):return value
            time.sleep(.15)
        raise TimeoutError('Native confirmation timeout')
    initial=read(trace)
    if not initial.get('pose',{}).get('valid'):raise RuntimeError('Loaded valid copied-save player pose required')
    destinations=initial.get('safe_destinations',[])[:a.max_destinations];rows=[]
    send('atlas2-floor-auto');wait(lambda s:not command.exists())
    for destination in destinations:
        row=dict(area=destination['area'],return_point=destination['return_point'],status='unverified')
        try:
            send('atlas2-travel '+str(destination['return_point']))
            components=[int(x) for x in destination['region_id'][1:].split('_')];block=sum(v<<(24-8*i) for i,v in enumerate(components));arrival=destination['arrival_xyz']
            # Arrival must be independently observed after the native request was consumed.
            def arrived(s):
                q=s.get('pose',{})
                return not command.exists() and q.get('valid') and q.get('block')==block and math.dist([q.get(k,1e9) for k in ('x','y','z')],arrival)<=3
            value=wait(arrived,90);send('open');wait(lambda s:s.get('open') and not command.exists());send('atlas2-static');static=wait(lambda s:s.get('mode')==0 and not command.exists());send('atlas2-reference');reference=wait(lambda s:s.get('mode')==1 and 'v1_layer' in s and not command.exists());q,r=static['pose'],reference['pose'];pose_delta=math.dist([q[k] for k in ('x','y','z')],[r[k] for k in ('x','y','z')]);same=q['block']==r['block'] and pose_delta<=.05 and abs(q['yaw']-r['yaw'])<=.01
            row.update(status='pass' if same and static['layer']==reference['v1_layer'] else 'inconclusive',layer=static['layer'],v1_layer=reference['v1_layer'],matched_pose=same,pose_delta=pose_delta,arrival_delta=math.dist([q[k] for k in ('x','y','z')],arrival),projection=static.get('projection'),native_gameplay_tested=True)
        except (TimeoutError,RuntimeError) as e:row.update(status='unavailable',reason=type(e).__name__)
        rows.append(row);(session/'comparison-summary.json').write_text(json.dumps(dict(schema=1,finite_sample=True,reserved_window=a.reserved_window,results=rows),indent=2))
    if not command.exists():send('atlas2-static')
    covered={r['area'] for r in rows if r['status']=='pass'};print('ATLAS2_LIVE_COMPARISON destinations='+str(len(rows))+' areas='+str(len(covered)))
if __name__=='__main__':main()
