"""Load only receipt-verified copied QA profiles sequentially and inspect guarded flags; no travel."""
from pathlib import Path
import argparse,hashlib,json,runpy,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import Channel,ProtocolError,atomic_json,read_json,valid_pose,process_image
from live_compare import menu
from drive_game import graceful_close
from launch_session import verify_lease

def main():
    p=argparse.ArgumentParser();p.add_argument('--reserved-window',required=True);a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';approved=read_json(w/'approved-copy-inspection.json');python=w/'Atlas2-test/runtime/python/python.exe';exe=w/'Atlas2-test/bin/bb-probe.exe';results=[];qa=w/'audit-qa/runs';driver=runpy.run_path(str(Path(__file__).resolve().parents[1]/'owned/tests/drive_game.py'));ocr=Path(__file__).with_name('startup_ocr.ps1')
    for copy in approved['copies']:
        verify_lease(w,a.reserved_window);label='census04-'+copy['candidate'];s=qa/label;c=None;row=dict(candidate=copy['candidate'],source_inspected_before_test=True,travel_requested=False)
        try:
            if s.exists():raise RuntimeError('Fresh copied-save census label required')
            launch=subprocess.run([str(python),'-B',str(Path(__file__).with_name('launch_audit.py')),'--reserved-window',a.reserved_window,'--label',label,'--variant','atlas2_audit','--template-id',copy['candidate']],capture_output=True,text=True,timeout=30)
            if launch.returncode:raise RuntimeError('Private census launch failed')
            end=time.monotonic()+150
            while time.monotonic()<end:
                try:c=Channel(s/'map-qa/trace.json.atlas2.json',exe,max_age=10);state=c.read();break
                except ProtocolError:time.sleep(.25)
            else:raise RuntimeError('Private census startup telemetry timeout')
            pad=c.trace.parent/'pad.txt'
            def press(button):
                try:pad.write_text(button,encoding='ascii');time.sleep(.35)
                finally:pad.write_text('',encoding='ascii')
            c.wait(lambda x:True,after=state['sequence']);time.sleep(10);press('cross');confirmed=False
            for attempt in range(4):
                driver['capture_first_frame'](s,timeout=20)
                read=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ocr),'-Label',label,'-RunRoot',str(qa)],capture_output=True,text=True,timeout=20)
                terms=json.loads(read.stdout)['generic_terms'] if read.returncode==0 else []
                if any(t in terms for t in ('corrupt','failed','error')):raise RuntimeError('Private startup reports a data error; refusing input')
                if 'continue' in terms:confirmed=True;break
                if 'online' in terms and 'offline' in terms:press('down');press('cross')
                elif 'press' in terms:press('cross')
                time.sleep(5)
            if not confirmed:raise RuntimeError('Private Continue menu not confirmed; no guessed input')
            press('cross');loaded=c.wait(lambda x:valid_pose(x.get('pose')),timeout=120);settled=time.monotonic()+2;c.wait(lambda x:time.monotonic()>=settled and valid_pose(x.get('pose')),after=loaded['sequence'],timeout=10);menu(c,pad);c.command('open');issued=c.command('atlas2-static');rendered=c.rendered(0,issued['sequence']);ack=c.command('atlas2-audit-flags')
            if not ack.get('ack',{}).get('flag_audit_written'):raise RuntimeError('Guarded flag audit was not confirmed')
            audit=read_json(c.trace.parent/'trace.json.flag-audit.json');areas=[]
            for area in audit['areas']:
                entries=area['destinations'];areas.append(dict(area=area['area'],eligible=sum(d['eligible'] for d in entries),unlock_true=sum(d['unlock_state']==1 for d in entries),unlock_false=sum(d['unlock_state']==0 for d in entries),unlock_unknown=sum(d['unlock_state']<0 for d in entries),condition_unknown=sum(v<0 for d in entries for v in d['on_states']+d['off_states'])))
            row.update(status='inspected',pose=loaded['pose'],loaded_area=rendered['render']['area'],loaded_layer=rendered['render']['layer'],areas=areas,eligible_areas=[v['area'] for v in areas if v['eligible']],eligible_destinations=sum(v['eligible'] for v in areas));atomic_json(s/'copied-save-census.json',row)
        except Exception as exc:row.update(status='unverified',reason=str(exc))
        finally:
            if c and c.pid:
                graceful_close(c.pid,exe);stop=time.monotonic()+20
                while time.monotonic()<stop:
                    try:process_image(c.pid)
                    except ProtocolError:break
                    time.sleep(.2)
                else:raise RuntimeError('Private census game did not close; refusing another process')
                child=read_json(s/'launch.json').get('pid');stop=time.monotonic()+15
                while child and time.monotonic()<stop:
                    try:process_image(child)
                    except ProtocolError:break
                    time.sleep(.2)
            source=Path(copy['source_path']);row['original_qa_source_hashes_unchanged']=all(hashlib.sha256((source/k).read_bytes()).hexdigest()==v for k,v in copy['hashes'].items());results.append(row);atomic_json(w/'copied-save-census.json',dict(schema=1,profiles=results,complete=False,all_original_qa_sources_read_only=True));print('COPIED_PROFILE_CENSUS '+copy['candidate']+' status='+row['status']+' eligible='+str(row.get('eligible_destinations')),flush=True)
        if row['status']!='inspected':break
    atomic_json(w/'copied-save-census.json',dict(schema=1,profiles=results,complete=len(results)==len(approved['copies']) and all(r['status']=='inspected' for r in results),all_original_qa_sources_read_only=True));print('COPIED_SAVE_CENSUS_FINISHED',flush=True)
if __name__=='__main__':main()
