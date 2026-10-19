"""Finite copied-save walk test. Only discovered travel and ordinary stick input."""
from pathlib import Path
import argparse,json,math,os,time
from launch_session import verify_lease
from live_protocol import Channel,ProtocolError,atomic_json,classify_comparison,valid_pose
from live_compare import menu,one_destination

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);p.add_argument('--route',type=Path,required=True);a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=a.session.resolve();s.relative_to(w.resolve());route=a.route.resolve();route.relative_to(w.resolve());r=json.loads(route.read_text());verify_lease(w,a.reserved_window);c=Channel(s/'map-qa/trace.json.atlas2.json',w/'Atlas2-test/bin/bb-probe.exe',max_age=30);pad=c.trace.parent/'pad.txt';deadline=time.monotonic()+300;poses=[];checks=[];bursts=0;held_ms=0;report=dict(schema=1,complete=False,route_type=r['kind'],area=r['area'],destination_id=r['destination_id'],poses=poses,comparisons=checks,unknown_memory_writes=False,unlock_writes=False,ordinary_controls_only=True)
 def save():atomic_json(s/('ordinary-'+r['kind']+'.json'),report)
 def pause(wanted):
  for attempt in range(2):
   before=c.read()
   if before.get('menu_top') is wanted and (not wanted or before.get('menu_supported')):return before
   try:pad.write_text('options',encoding='ascii');time.sleep(.35)
   finally:pad.write_text('',encoding='ascii')
   try:return c.wait(lambda x:x.get('menu_top') is wanted and (not wanted or x.get('menu_supported')),after=before['sequence'],timeout=4)
   except ProtocolError:
    if attempt:raise
    report['menu_input_retries']=report.get('menu_input_retries',0)+1;save()
  raise ProtocolError('Ordinary menu state unavailable')
 def button():return pause(not c.read().get('menu_top'))
 def pair():
  if c.read().get('open'):c.command('close')
  pause(True);c.command('enable');c.command('atlas2-floor-auto');c.command('open');issued=c.command('atlas2-static');st=c.rendered(0,issued['sequence']);issued=c.command('atlas2-reference');ref=c.rendered(1,issued['sequence']);result=classify_comparison(st,ref);result.update(pose=st['pose'],bursts=bursts);checks.append(result);save();c.command('atlas2-static');c.command('close');return result
 def pulse(lx,ly,ms):
  nonlocal bursts,held_ms
  max_bursts,max_held=(120,30000) if r['kind']=='death' else (80,18000)
  if bursts>=max_bursts or held_ms+ms>max_held or time.monotonic()>=deadline:raise ProtocolError('Ordinary route bound reached')
  verify_lease(w,a.reserved_window);before=c.read();pose=before['pose']
  if not valid_pose(pose) or before['open'] or before['menu_top']:raise ProtocolError('Loaded unpaused closed-map gameplay required')
  try:pad.write_text('lx='+str(lx)+' ly='+str(ly),encoding='ascii');time.sleep(ms/1000)
  finally:pad.write_text('',encoding='ascii')
  bursts+=1;held_ms+=ms;until=time.monotonic()+.3;after=c.wait(lambda x:time.monotonic()>=until,after=before['sequence'],timeout=8);poses.append(dict(sequence=after['sequence'],pose=after['pose'],input=[lx,ly,ms]));save()
  if not valid_pose(after['pose']):raise ProtocolError('Pose became unavailable; ordinary movement stopped')
  if after['pose']['block']!=pose['block']:raise ProtocolError('Unexpected region change; ordinary movement stopped')
  if math.hypot(after['pose']['x']-pose['x'],after['pose']['z']-pose['z'])>4:raise ProtocolError('Unexpected movement; ordinary movement stopped')
  return after['pose']
 try:
  dest=next((d for d in c.read()['safe_destinations'] if d['return_point']==r['destination_id'] and d['area']==r['area']),None)
  if dest is None:raise ProtocolError('Route destination is not currently eligible')
  prior=None
  if r.get('resume_attempt'):
   proof=Path(r['resume_attempt']).resolve();proof.relative_to(s);prior=json.loads(proof.read_text());old=prior['poses'][-1]['pose'];now=c.read()['pose']
   if now['block']!=old['block'] or math.dist([now[k] for k in ('x','y','z')],[old[k] for k in ('x','y','z')])>.1:raise ProtocolError('Paused continuation pose differs from its receipt')
   arrival=prior['guarded_arrival'];report['resumed_from']=str(proof)
  else:arrival=one_destination(c,dest,pad)
  report['guarded_arrival']=arrival
  if arrival['status']!='pass':raise ProtocolError('Supported arrival comparison failed')
  start=pair();button()
  if prior:f=tuple(prior['calibration']['forward']);rt=tuple(prior['calibration']['right']);fn=rn=.4
  else:
   p0=c.read()['pose'];pf=pulse(128,0,200);pr=pulse(255,128,200);f=(pf['x']-p0['x'],pf['z']-p0['z']);rt=(pr['x']-pf['x'],pr['z']-pf['z']);fn=math.hypot(*f);rn=math.hypot(*rt)
   if min(fn,rn)<.08:raise ProtocolError('Ordinary input calibration blocked or too small')
   f=tuple(v/fn for v in f);rt=tuple(v/rn for v in rt)
  det=rt[0]*f[1]-rt[1]*f[0]
  if abs(det)<.5:raise ProtocolError('Ordinary input basis is ambiguous')
  report['calibration']=dict(forward=f,right=rt,determinant=det);speed=max(.5,(fn+rn)/.4);stalls=0
  for number,point in enumerate(r['waypoints'][1:]):
   for attempt in range(12):
    pose=c.read()['pose'];dx,dz=point[0]-pose['x'],point[2]-pose['z'];distance=math.hypot(dx,dz)
    report.update(current_waypoint=number+1,target_xyz=point,remaining_horizontal=distance)
    tolerance=.6 if r['kind']=='death' and number<len(r['waypoints'])-2 else .35
    if distance<=tolerance:break
    u=(dx*f[1]-dz*f[0])/det;v=(rt[0]*dz-rt[1]*dx)/det;n=math.hypot(u,v);amplitude=(70 if distance<.75 else 125) if r['kind']=='death' else 100;lx=max(0,min(255,round(128+u/n*amplitude)));ly=max(0,min(255,round(128-v/n*amplitude)));ms=max(60,min(120 if r['kind']=='death' and distance<.75 else 250,round(distance/speed*650)));now=pulse(lx,ly,ms);progress=distance-math.hypot(point[0]-now['x'],point[2]-now['z']);stalls=stalls+1 if progress<.015 else 0
    if r['kind']=='death':speed=.5*speed+.5*max(.5,min(6,math.hypot(now['x']-pose['x'],now['z']-pose['z'])/(ms/1000)))
    if stalls>=4:raise ProtocolError('Collision or no progress on candidate route')
    if abs(now['y']-pose['y'])>3:raise ProtocolError('Unexpected height drop; ordinary movement stopped')
    if r['kind']!='death' and bursts%5==0:
     check=pair();print('ORDINARY_ROUTE_SAMPLE checks='+str(len(checks))+' layer=F'+str(check.get('rendered_layer',-1)).zfill(3),flush=True)
     if check['status']!='pass':raise ProtocolError('V1/V2 mismatch during ordinary route')
     button()
   else:raise ProtocolError('Candidate waypoint was not reached within its bound')
  if r['kind']=='death':
   from observe_respawn import observe
   death=observe(c,s,w,a.reserved_window);report.update(complete=True,passed=death['passed'],executed_bursts=bursts,held_ms=held_ms,death_observation=str(s/'death-respawn-observation.json'));save();print('ORDINARY_DEATH_ROUTE_COMPLETE pass='+str(report['passed']));return
  final=pair();ys=[x['pose']['y'] for x in poses if x['pose']['valid']];layers={x.get('rendered_layer') for x in checks if x['status']=='pass'};report.update(complete=True,executed_bursts=bursts,held_ms=held_ms,observed_height_span=max(ys)-min(ys),observed_matched_layers=sorted(layers),passed=final['status']=='pass' and max(ys)-min(ys)>.8 and len(layers)>=2,scope='Ordinary continuous walking over a connected height-changing route with finite paused V1/V2 checkpoints; no teleport between walking samples, no subjective staircase visual review');save();print('ORDINARY_ROUTE_COMPLETE pass='+str(report['passed'])+' matched_layers='+str(len(layers)))
 except Exception as exc:
  report.update(complete=True,passed=False,stop_reason=str(exc),executed_bursts=bursts,held_ms=held_ms)
  if r['kind']=='death' and ('height drop' in str(exc) or 'Pose became unavailable' in str(exc)):
   from observe_respawn import observe
   death=observe(c,s,w,a.reserved_window);report.update(passed=death['passed'],death_observation=str(s/'death-respawn-observation.json'));save();print('ORDINARY_DEATH_ROUTE_OBSERVED pass='+str(report['passed']));return
  save();raise
 finally:
  pad.write_text('',encoding='ascii')
  try:
   state=c.read()
   if valid_pose(state['pose']):
    if state.get('open'):c.command('close')
    pause(True);c.command('atlas2-static');c.command('close')
  except Exception:pass
if __name__=='__main__':main()
