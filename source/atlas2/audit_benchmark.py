"""Match native CPU/present samples to independent ETW windows on one guarded copied-save point."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import Channel,ProtocolError,atomic_json,matched_pose,read_json
from launch_session import verify_lease
from measure_session import distribution,settle
from capture_presentmon import summarize,TOOL_HASH
from capture_ui import capture_ui
from compare_private_frames import load,metric

def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);p.add_argument('--seconds',type=int,default=20);p.add_argument('--require-raster-check',action='store_true');a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=a.session.resolve();s.relative_to(w.resolve());verify_lease(w,a.reserved_window)
    if a.require_raster_check:
        accepted=read_json(s/'raster-correctness-verification.json');assert accepted['texture_binding_accepted'] and Path(accepted['session'])==s
        for comparison in accepted['comparisons']:
            for image in comparison['images']:
                path=Path(image['path']).resolve();path.relative_to(s);assert hashlib.sha256(path.read_bytes()).hexdigest()==image['sha256']
    c=Channel(s/'map-qa/trace.json.atlas2.json',w/'Atlas2-test/bin/bb-probe.exe',max_age=30);state=c.read();pose=state['pose'];stock=read_json(w/'audit-qa/runs/stock-trace04/stock-status.json');expected_pose=dict(valid=stock['valid'],block=stock['block'],**{k:stock[k] for k in ('x','y','z','yaw')})
    if not matched_pose(pose,expected_pose) or not state['menu_top']:raise ProtocolError('Matched stock pose under native pause menu required')
    c.command('open');c.command('recenter');issued=c.command('atlas2-reference');c.rendered(1,issued['sequence']);settle(c,3,pose);image=capture_ui(s)[0];stock_image=read_json(w/'audit-qa/runs/stock-clean04/latest-stock-ui-capture.json')['images'][0];aa,width,height,_=load(image['path']);bb,ww,hh,_=load(stock_image['path']);assert (width,height)==(ww,hh);parity=metric(aa,bb,width,height,(345,171,1597.5,978),2);atomic_json(s/'reference-stock-canvas-parity.json',dict(schema=1,map_canvas=parity,images_private=True,pose_matched=True,original_stock_binary_sha256='887f5baf7e149ea7604e4e037fd5eef43a0ad483a8dcb649a6122636d906c557'))
    if parity['rgb_mae_0_255']>1:raise ProtocolError('Reference differs from exact stock map canvas; investigate before timing acceptance')
    tool=w/'tools/PresentMon-2.6.0-x64.exe';assert hashlib.sha256(tool.read_bytes()).hexdigest()==TOOL_HASH;rows=[];counts={'reference':0,'static':0}
    try:
        for mode in ('reference','static','static','reference','reference','static'):
            n=counts[mode];counts[mode]+=1;issued=c.command('atlas2-'+mode);c.rendered(1 if mode=='reference' else 0,issued['sequence']);settle(c,2,pose);label='audit_'+mode+'_'+str(n);started=c.command('atlas2-measure-start '+label);generation=started['ack']['measurement_generation'];output=s/(label+'.csv');log=output.with_suffix('.tool.log');session_name='Atlas2-'+label+'-'+str(time.time_ns())
            with log.open('w') as stream:
                child=subprocess.Popen([str(tool),'--process_id',str(c.pid),'--timed',str(a.seconds),'--terminate_after_timed','--no_console_stats','--no_track_input','--session_name',session_name,'--output_file',str(output)],stdout=stream,stderr=stream,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:code=child.wait(timeout=a.seconds+15)
                except subprocess.TimeoutExpired:
                    subprocess.run([str(tool),'--session_name',session_name,'--terminate_existing_session'],stdout=stream,stderr=stream,timeout=10);code=child.wait(timeout=10)
            stopped=c.command('atlas2-measure-stop');native=read_json(c.trace.parent/'trace.json.measurement.json')
            if code or native.get('generation')!=generation or not matched_pose(pose,stopped['pose']) or not stopped['menu_top']:raise ProtocolError('Audit phase confirmation failed')
            atomic_json(s/(label+'-native.json'),native);cpu=distribution(native['map_cpu_elapsed_ms'][2:]);cpu.pop('fps_from_interval_mean',None);row=dict(mode=mode,repeat=n,native_present=distribution(native['present_interval_ms'][2:]),native_map_cpu=cpu,etw=summarize(output,c.pid),pose=pose,phase_counters_same_window=False,window_limit='Native recording includes ETW startup/shutdown; aggregate timing comparison, not exact frame pairs',native_raw=str(s/(label+'-native.json')),etw_csv=str(output));rows.append(row);atomic_json(s/'independent-audit-summary.json',dict(schema=1,results=rows,complete=False,pose=pose,canvas_parity=parity));print('INDEPENDENT_PAIRED_PHASE '+mode+' repeat='+str(n+1)+' etw_frames='+str(row['etw']['selected_rows']),flush=True)
        atomic_json(s/'independent-audit-summary.json',dict(schema=1,results=rows,complete=True,pose=pose,canvas_parity=parity,styling_equal_between_v1_and_v2=False,gpu_metrics_scope='Whole process per-present ETW attribution; not map-only GPU time'))
    finally:c.command('atlas2-measure-stop');c.command('atlas2-static');c.command('close')
    print('INDEPENDENT_PAIRED_AUDIT_COMPLETE',flush=True)
if __name__=='__main__':main()
