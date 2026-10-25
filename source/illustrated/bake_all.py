from pathlib import Path
import os,subprocess,sys,json,time,hashlib,shutil
ROOT=Path(__file__).resolve().parent; SRC=ROOT
reference=Path(os.environ.get('ATLAS_REFERENCE_DIR','')).expanduser()
if not os.environ.get('ATLAS_REFERENCE_DIR'):
 raise RuntimeError('Set ATLAS_REFERENCE_DIR to the extracted Atlas reference directory')
if not os.environ.get('ATLAS_GAME_DIR'):
 raise RuntimeError('Set ATLAS_GAME_DIR to the user\'s extracted game data directory')
reference=reference.resolve()
MAPS=reference/'maps' if (reference/'maps').is_dir() else reference
WORK_ROOT=Path(os.environ.get('ATLAS_WORK_DIR',str(ROOT/'work'))).expanduser().resolve()
ASSET_ROOT=Path(os.environ.get('ATLAS_ASSET_DIR',str(ROOT/'assets'))).expanduser().resolve()
ids=[p.stem for p in MAPS.glob('m*.json') if len(p.stem)==12]
ids.sort(); manifest={'schema':1,'pipeline':'offline-authored-navmesh+collision-support','maps':[],'started':time.time()}
(ROOT/'reports').mkdir(parents=True,exist_ok=True)
for mid in ids:
 env=os.environ.copy();env['ATLAS_MAP_ID']=mid;env['ATLAS_WORK_DIR']=str(WORK_ROOT);env['ATLAS_ASSET_DIR']=str(ASSET_ROOT);work=WORK_ROOT/mid;asset=ASSET_ROOT/mid
 work.mkdir(parents=True,exist_ok=True);asset.mkdir(parents=True,exist_ok=True)
 rec={'id':mid,'status':'running','stages':[],'work':str(work),'asset':str(asset)};manifest['maps'].append(rec)
 stages=[('extract_collision.py',[]),('navmesh.py',[]),('support_nav.py',[]),('nav_geometry.py',[]),('exact_overlaps.py',[]),('passage_sheets.py',['--map-id',mid,'--work-dir',str(work)])]
 for name,args in stages:
  log=work/(name+'.log')
  with log.open('w',encoding='utf-8') as f:
   p=subprocess.run([sys.executable,str(SRC/name),*args],cwd=str(ROOT),env=env,stdout=f,stderr=subprocess.STDOUT)
  rec['stages'].append({'name':name,'exit_code':p.returncode,'log':str(log)})
  manifest['updated']=time.time();(ROOT/'reports'/'bake-manifest.json').write_text(json.dumps(manifest,indent=2))
  if p.returncode:
   rec['status']='failed';rec['failure_stage']=name;break
 if rec['status']=='running': shutil.copy2(work/'navigation.json',asset/'navigation.json')
 if rec['status']=='running':
  style='forest' if mid=='m27_00_00_00' else 'urban'
  atlas=ROOT/'assets'/f'{style}-atlas.png';atlas_copy=asset/atlas.name;shutil.copy2(atlas,atlas_copy)
  cmd=[sys.executable,str(SRC/'bake_illustrations.py'),'--style',style,'--navigation',str(asset/'navigation.json'),'--output',str(asset/'illustrations.json'),'--atlas',str(atlas_copy)]
  log=work/'bake_illustrations.py.log'
  with log.open('w',encoding='utf-8') as f:p=subprocess.run(cmd,cwd=str(ROOT),env=env,stdout=f,stderr=subprocess.STDOUT)
  rec['stages'].append({'name':'bake_illustrations.py','style':style,'exit_code':p.returncode,'log':str(log)})
  if p.returncode:rec['status']='failed';rec['failure_stage']='bake_illustrations.py'
  else:
   shutil.copy2(asset/'illustrations.json',work/'illustrations.json')
   rec['status']='complete'
  qa=work/'geometry-qa.json'
  if qa.exists(): shutil.copy2(qa,ROOT/'reports'/f'{mid}-geometry-qa.json')
manifest['finished']=time.time();manifest['summary']={k:sum(r['status']==k for r in manifest['maps']) for k in ('complete','failed','running')}
(ROOT/'reports'/'bake-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest['summary']))
