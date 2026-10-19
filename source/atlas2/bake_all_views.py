"""Resumable, single-worker, bounded CPU generation of all anonymous area views."""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,shutil,subprocess,time
from pack_format import sha,load_view,shared_read
from generation_guard import acquire
GIB=1024**3
def replace_file(source,target):
 if os.name!='nt' or not Path(target).exists():os.replace(source,target);return
 kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.ReplaceFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
 if not kernel.ReplaceFileW(str(Path(target).resolve()),str(Path(source).resolve()),None,0,None,None):raise ctypes.WinError(ctypes.get_last_error())
def atomic(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(value,sort_keys=True),encoding='utf-8');deadline=time.monotonic()+5
 while True:
  try:replace_file(tmp,path);return
  except OSError as error:
   if not isinstance(error,PermissionError) and getattr(error,'winerror',None) not in [5,32,33] or time.monotonic()>=deadline:raise
   time.sleep(.05)
def size(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
def generation_window(root,identity,max_seconds,max_gib):
 path=Path(root)/'generation-window.json';now=time.time();mono=time.monotonic()
 if path.exists():window=json.loads(shared_read(path))
 else:
  window=dict(schema=1,generator_identity=identity,started_epoch=now,deadline_epoch=now+max_seconds,storage_budget_bytes=int(max_gib*GIB),free_space_reserve_bytes=16*GIB);atomic(path,window)
 if window['generator_identity']!=identity or window['storage_budget_bytes']!=int(max_gib*GIB) or window['free_space_reserve_bytes']!=16*GIB:raise RuntimeError('Persisted generation identity or storage limits differ')
 began=float(window['started_epoch']);end=float(window['deadline_epoch'])
 if not 0<began<=now<end<float('inf'):raise RuntimeError('Original generation time bound reached or invalid')
 return mono-(now-began),mono+min(max_seconds,end-now)
def main():
 p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--baker',type=Path,required=True);p.add_argument('--runtime-directory',type=Path,required=True);p.add_argument('--resume',action='store_true');p.add_argument('--areas',nargs='*');p.add_argument('--max-gib',type=float,default=16);p.add_argument('--max-seconds',type=int,default=21600);a=p.parse_args();baseline=a.baseline.resolve();out=a.output.resolve();assets=a.assets.resolve()
 if out.is_relative_to(baseline) or baseline.is_relative_to(out):raise RuntimeError('Independent output required')
 if out.exists() and not a.resume:raise RuntimeError('Use a fresh output or explicit resume')
 if not out.exists():shutil.copytree(baseline,out)
 generation_lease=acquire(out)
 env=dict(os.environ,PATH=str(a.runtime_directory.resolve())+os.pathsep+os.environ.get('PATH',''))
 if os.name=='nt':ctypes.windll.kernel32.SetErrorMode(0x0001|0x0002|0x8000)
 identity=hashlib.sha256(b''.join(Path(__file__).with_name(f).read_bytes() for f in ['bake_parity.cpp','parity_style.h','core.h','texture_budget.h'])).hexdigest();index=json.loads(shared_read(out/'atlas2-index.json'));started,deadline=generation_window(out,identity,a.max_seconds,a.max_gib);measurements=[];last_total=-1
 def census():
  rows=[]
  for e in index['areas']:
   contents=shared_read(out/e['area']/'manifest.json');m=json.loads(contents);covered=[i for i,v in enumerate(m['views']) if 'view_file' in v]
   if covered and m.get('parity_generator_identity')!=identity:raise RuntimeError('Output generator identity changed; preserve it and use fresh output')
   e['manifest_sha256']=hashlib.sha256(contents).hexdigest();rows.append(dict(area=e['area'],complete=len(covered),expected=len(m['views'])))
  atomic(out/'atlas2-index.json',index);return rows
 rows=census();expected=sum(r['expected'] for r in rows)
 for e in index['areas']:
  label=e['area']
  if a.areas and label not in a.areas:continue
  area=out/label;m=json.loads(shared_read(area/'manifest.json'));missing=[]
  for i,v in enumerate(m['views']):
   if 'view_file' in v:load_view(area,v)
   else:missing.append(i)
  if not missing:continue
  current=size(out);remaining=int(a.max_gib*GIB)-current-64*1024**2
  if remaining<=0 or shutil.disk_usage(out).free<16*GIB+64*1024**2:raise RuntimeError('Generation storage budget/reserve reached; completed views preserved')
  env['BB_ATLAS2_BAKE_REMAINING_BYTES']=str(remaining);before=time.monotonic();command=[str(a.baker.resolve()),str(assets/'maps'/(e['region_id']+'.json')),str(assets/'maps/features.json'),str(area/'manifest.json'),str(area),label,'16',','.join(map(str,missing)),str(assets/'art'),identity]
  with (area/'bake-full.log').open('a',encoding='utf-8') as log:
   child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   try:
    while child.poll() is None:
     rows=census();total=sum(r['complete'] for r in rows);state=dict(schema=1,state='running',worker_pid=child.pid,generator_identity=identity,elapsed_seconds=time.monotonic()-started,complete_views=total,expected_views=expected,area=label,areas=rows,storage_budget_bytes=int(a.max_gib*GIB),free_space_reserve_bytes=16*GIB,offline_only=True)
     atomic(out/'generation-state.json',state)
     if total!=last_total:print('FULL_BAKE_CHECKPOINT area='+label+' views='+str(total)+'/'+str(expected)+' seconds='+str(round(state['elapsed_seconds'],1)),flush=True);last_total=total
     if time.monotonic()>deadline or shutil.disk_usage(out).free<16*GIB+32*1024**2:
      child.terminate();child.wait(timeout=15);state.update(state='bounded_stop',reason='time or free-space limit');atomic(out/'generation-state.json',state);raise RuntimeError('Owned CPU baker stopped at bound; atomic completed views preserved')
     time.sleep(2)
   except BaseException:
    # A metadata/controller failure must not leave its owned CPU child running.
    if child.poll() is None:child.terminate();child.wait(timeout=15)
    raise
  rows=census();total=sum(r['complete'] for r in rows);row=dict(area=label,seconds=time.monotonic()-before,exit_code=child.returncode,completed_views=next(r['complete'] for r in rows if r['area']==label),total_output_bytes=size(out));measurements.append(row);atomic(out/'generation-measurements.json',dict(schema=1,generator_identity=identity,areas=measurements))
  print('FULL_BAKE_AREA '+json.dumps(row),flush=True)
  if child.returncode:
   atomic(out/'generation-state.json',dict(schema=1,state='baker_blocked',area=label,complete_views=total,expected_views=expected,private_log=str(area/'bake-full.log')));raise RuntimeError('CPU baker stopped for '+label+'; checkpoint retained')
 rows=census();total=sum(r['complete'] for r in rows);atomic(out/'generation-state.json',dict(schema=1,state='complete' if total==expected else 'selected_checkpoint',generator_identity=identity,complete_views=total,expected_views=expected,total_bytes=size(out),elapsed_seconds=time.monotonic()-started,areas=rows,offline_only=True));print('FULL_BAKE_DONE views='+str(total)+'/'+str(expected),flush=True)
if __name__=='__main__':main()
