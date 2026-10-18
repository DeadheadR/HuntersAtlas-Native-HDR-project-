"""Restart only the same private copied-save session after its previous native process exits."""
from pathlib import Path
import argparse,datetime,runpy,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import Channel,ProtocolError,atomic_json,classify_comparison,distance,read_json,valid_pose
from live_compare import menu
from launch_session import verify_lease

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);p.add_argument('--verify',action='store_true');a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=a.session.resolve();s.relative_to((w/'qa/runs').resolve());receipt=read_json(s/'launch.json');Path(receipt['user_dir']).resolve().relative_to(w.resolve());verify_lease(w,a.reserved_window);expected=w/'Atlas2-test/bin/bb-probe.exe';trace=s/'map-qa/trace.json.atlas2.json'
    if a.verify:
        before=read_json(s/'restart-receipt.json');c=Channel(trace,expected);now=c.read()
        if now['process_id']==before['previous_native_pid'] or not valid_pose(now['pose']):raise ProtocolError('A new loaded private native process is required')
        menu(c,trace.parent/'pad.txt');c.command('open');c.command('atlas2-floor-auto');issued=c.command('atlas2-static');static=c.rendered(0,issued['sequence']);issued=c.command('atlas2-reference');reference=c.rendered(1,issued['sequence']);result=classify_comparison(static,reference)
        result.update(schema=1,same_copied_save_directory=True,previous_native_pid=before['previous_native_pid'],new_native_pid=now['process_id'],previous_pose=before['previous_pose'],new_pose=now['pose'],reload_xyz_delta=distance(before['previous_pose'],now['pose']),same_loaded_block=before['previous_pose']['block']==now['pose']['block'],previous_layer=before['previous_layer'],reloaded_layer=static['render']['layer'],private_user_dir=receipt['user_dir'],original_saves_used_as_write_target=False)
        result['reload_check_pass']=result['same_loaded_block'] and result['reload_xyz_delta']<=3 and result['previous_layer']==result['reloaded_layer'] and result['status']=='pass';atomic_json(s/'restart-verification.json',result);c.command('atlas2-static');c.command('close');print('COPIED_SAVE_RESTART_PASS='+str(result['reload_check_pass']));return
    previous=read_json(trace)
    if previous.get('schema')!=2 or not valid_pose(previous.get('pose')):raise ProtocolError('Prior loaded private telemetry required')
    core=runpy.run_path(str(w/'Atlas2-test/bootstrap/entry.py'));known={'bb-probe.exe','bb-play.exe','shadps4.exe','shadps4-qt.exe','bloodborne.exe'}
    if any(name.casefold() in known for name,pid in core['_windows_process_names']()):raise ProtocolError('Previous game process must exit before restart')
    coordination=read_json(w/'qa/coordination.json')
    if coordination.get('reserved_window')!=a.reserved_window:raise ProtocolError('Restart reservation changed')
    command=[str(w/'Atlas2-test/runtime/python/python.exe'),'-I','-B',str(Path(__file__).with_name('launch_session.py')),'--child',s.name]
    with (s/'restart-game.log').open('wb') as log:child=subprocess.Popen(command,cwd=w,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    atomic_json(s/'restart-receipt.json',dict(schema=1,requested_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_native_pid=previous['process_id'],previous_pose=previous['pose'],previous_layer=previous['render']['layer'],private_user_dir=receipt['user_dir'],child_pid=child.pid,reused_existing_copied_save=True));print('PRIVATE_RESTART_REQUESTED child_pid='+str(child.pid))
if __name__=='__main__':main()
