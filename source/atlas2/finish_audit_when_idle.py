"""Bounded cleanup for the already-running copied-profile census; never kills a process."""
from pathlib import Path
import argparse,json,runpy,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import atomic_json,read_json
def main():
    p=argparse.ArgumentParser();p.add_argument('--reservation',required=True);a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';end=time.monotonic()+600;core=runpy.run_path(str(w/'Atlas2-test/bootstrap/entry.py'));known={'bb-probe.exe','bb-play.exe','shadps4.exe','shadps4-qt.exe','bloodborne.exe'}
    while time.monotonic()<end:
        census=read_json(w/'copied-save-census.json');lease=read_json(w/'native-lease.json')
        if lease.get('reservation')!=a.reservation:raise RuntimeError('Lease changed; refusing cleanup')
        games=[pid for name,pid in core['_windows_process_names']() if name.casefold() in known]
        if census.get('complete') and not games:
            result=dict(schema=1,census_complete=True,native_game_running=False,reservation=a.reservation,qa_source_hashes_unchanged=all(r.get('original_qa_source_hashes_unchanged') for r in census['profiles']))
            try:
                python=w/'Atlas2-test/runtime/python/python.exe'
                subprocess.run([str(python),'-B',str(Path(__file__).with_name('finalize_test.py')),str(w)],check=True,timeout=60,capture_output=True)
                subprocess.run([str(python),'-B',str(Path(__file__).with_name('verify_test.py')),str(w)],check=True,timeout=60,capture_output=True)
                result['prototype_restored']=True;result['source_save_isolation_pass']=True
            except Exception as exc:result['cleanup_error']=str(exc)
            Path(lease['release_request_path']).write_text('Completed bounded copied-save census; no native game remains\n',encoding='ascii');stop=time.monotonic()+5
            while time.monotonic()<stop:
                updated=read_json(w/'native-lease.json')
                if updated.get('state')=='released':result['lease']=updated;break
                time.sleep(.2)
            atomic_json(w/'audit-cleanup.json',result);print('AUDIT_IDLE_CLEANUP_COMPLETE');return
        time.sleep(.5)
    atomic_json(w/'audit-cleanup.json',dict(schema=1,attention_required=True,reason='Bounded cleanup wait expired; no process was killed',reservation=a.reservation))
if __name__=='__main__':main()
