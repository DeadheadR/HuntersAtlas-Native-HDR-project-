"""Independent read-only PID-scoped ETW captures. Run in the same account as the private game."""
from pathlib import Path
import argparse,csv,datetime,hashlib,json,math,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import atomic_json,verified_private_image
from launch_session import verify_lease
from measure_session import distribution
TOOL_HASH='b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af'
def summarize(path,pid):
    with path.open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
    rows=[r for r in rows if int(r.get('ProcessID',0))==pid]
    if not rows:raise RuntimeError('No target PID frames captured; no timing accepted')
    chains={}
    for row in rows:chains.setdefault(row['SwapChainAddress'],[]).append(row)
    chain=max(chains,key=lambda k:len(chains[k]));selected=chains[chain][2:];metrics={}
    for key in ['MsBetweenPresents','MsBetweenDisplayChange','MsCPUBusy','MsCPUWait','MsGPUTime','MsGPUBusy','MsGPUWait','MsRenderPresentLatency']:
        values=[]
        for row in selected:
            try:value=float(row.get(key,''))
            except ValueError:continue
            if math.isfinite(value) and value>=0:values.append(value)
        metrics[key]=distribution(values)
        if key!='MsBetweenPresents':metrics[key].pop('fps_from_interval_mean',None)
    return dict(raw_rows=len(rows),selected_rows=len(selected),swapchain_count=len(chains),selection='Largest target-PID swapchain; first two rows excluded',metrics=metrics)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);p.add_argument('--pid',type=int,required=True);p.add_argument('--variant',choices=['stock','atlas2'],required=True);p.add_argument('--prefix',required=True);p.add_argument('--seconds',type=int,default=20);p.add_argument('--repetitions',type=int,default=3);p.add_argument('--reserved-window',required=True);a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=a.session.resolve();s.relative_to(w.resolve());verify_lease(w,a.reserved_window)
    if not 1<=a.seconds<=60 or not 1<=a.repetitions<=4 or not a.prefix.replace('_','').replace('-','').isalnum():raise RuntimeError('Bounded capture arguments required')
    tool=w/'tools/PresentMon-2.6.0-x64.exe'
    if hashlib.sha256(tool.read_bytes()).hexdigest()!=TOOL_HASH:raise RuntimeError('PresentMon identity mismatch')
    expected=w/('V1-stock-test' if a.variant=='stock' else 'Atlas2-test')/'bin/bb-probe.exe';runs=[]
    for n in range(a.repetitions):
        verified_private_image(a.pid,expected);name='Atlas2-'+a.prefix+'-'+str(n)+'-'+str(time.time_ns());output=s/(a.prefix+'-'+str(n)+'.csv');log=output.with_suffix('.tool.log');started=datetime.datetime.now(datetime.timezone.utc).isoformat();args=[str(tool),'--process_id',str(a.pid),'--timed',str(a.seconds),'--terminate_after_timed','--no_console_stats','--no_track_input','--session_name',name,'--output_file',str(output)]
        with log.open('w') as stream:
            child=subprocess.Popen(args,stdout=stream,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:code=child.wait(timeout=a.seconds+15)
            except subprocess.TimeoutExpired:
                subprocess.run([str(tool),'--session_name',name,'--terminate_existing_session'],stdout=stream,stderr=stream,timeout=10);code=child.wait(timeout=10)
        if code!=0 or not output.is_file():raise RuntimeError('Independent ETW capture failed; inspect private tool log')
        runs.append(dict(capture=n,started_utc=started,csv=str(output),seconds=a.seconds,**summarize(output,a.pid)));atomic_json(s/(a.prefix+'-summary.json'),dict(schema=1,variant=a.variant,pid=a.pid,presentmon_sha256=TOOL_HASH,captures=runs,read_only=True,input_tracking=False,complete=False))
        print('ETW_CAPTURE_READY '+a.prefix+' repetition='+str(n+1)+' frames='+str(runs[-1]['selected_rows']),flush=True)
    atomic_json(s/(a.prefix+'-summary.json'),dict(schema=1,variant=a.variant,pid=a.pid,presentmon_sha256=TOOL_HASH,captures=runs,read_only=True,input_tracking=False,complete=True));print('INDEPENDENT_ETW_SERIES_COMPLETE',flush=True)
if __name__=='__main__':main()
