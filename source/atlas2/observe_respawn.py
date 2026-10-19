"""Bounded observation only: generic death OCR, load cycle and copied-save respawn."""
from pathlib import Path
import argparse,json,subprocess,time,threading
from capture_game_private import capture_game
from live_protocol import Channel,atomic_json,valid_pose,classify_comparison,read_json
from live_compare import menu
from launch_session import verify_lease

def observe(c,s,w,reservation):
 verify_lease(w,reservation);end=time.monotonic()+90;rows=[];dead=False;invalid=False;seen_at=0;initial=c.read()['pose'];events=[];stop=threading.Event();report=dict(schema=1,passed=False,complete=False,observations=rows,pose_events=events,images_uploaded=False,observer_does_not_cause_death=True)
 def monitor():
  last=-1
  while not stop.is_set() and time.monotonic()<end and len(events)<1000:
   try:
    t=read_json(c.trace)
    if t['sequence']!=last:events.append(dict(sequence=t['sequence'],pose=t['pose']));last=t['sequence']
   except (OSError,ValueError,KeyError):pass
   stop.wait(.1)
 worker=threading.Thread(target=monitor,daemon=True);worker.start()
 try:
  for n in range(25):
   if time.monotonic()>=end:break
   iteration_started=time.monotonic()
   state=c.read();invalid|=not valid_pose(state['pose']) or any(not valid_pose(e['pose']) for e in events);terms=[]
   try:
    capture_game(s,timeout=8)
    cmd=[r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('startup_ocr.ps1')),'-Label',s.name,'-RunRoot',str(s.parent)]
    run=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=12)
    if run.returncode==0:terms=json.loads(run.stdout.strip())['generic_terms']
   except (TimeoutError,subprocess.TimeoutExpired,json.JSONDecodeError):pass
   now_dead='you died' in terms or 'вы погибли' in terms
   if now_dead:dead=True;seen_at=time.monotonic()
   rows.append(dict(sequence=state['sequence'],pose_valid=valid_pose(state['pose']),generic_death_visible=now_dead,generic_loading_visible='loading' in terms,pose=state['pose']));atomic_json(s/'death-respawn-observation.json',report)
   if dead and invalid and valid_pose(state['pose']) and not now_dead and time.monotonic()-seen_at>2:
    menu(c,c.trace.parent/'pad.txt');c.command('atlas2-floor-auto');c.command('open');issued=c.command('atlas2-static');st=c.rendered(0,issued['sequence']);issued=c.command('atlas2-reference');ref=c.rendered(1,issued['sequence']);comparison=classify_comparison(st,ref);report.update(passed=comparison['status']=='pass',respawn_comparison=comparison,respawn_pose=st['pose']);c.command('atlas2-static');c.command('close');break
   time.sleep(max(.1,(1 if n<8 else 4.5)-(time.monotonic()-iteration_started)))
 finally:
  stop.set();worker.join(timeout=2);invalid|=any(not valid_pose(e['pose']) for e in events);report.update(complete=True,death_text_confirmed=dead,invalid_pose_load_cycle_observed=invalid,starting_pose=initial);atomic_json(s/'death-respawn-observation.json',report)
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=a.session.resolve();s.relative_to(w.resolve());c=Channel(s/'map-qa/trace.json.atlas2.json',w/'Atlas2-test/bin/bb-probe.exe',max_age=30);r=observe(c,s,w,a.reserved_window);print('DEATH_RESPAWN_OBSERVATION pass='+str(r['passed'])+' death_text='+str(r['death_text_confirmed'])+' load_cycle='+str(r['invalid_pose_load_cycle_observed']))
if __name__=='__main__':main()
