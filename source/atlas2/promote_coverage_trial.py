"""Promote one fully validated isolated coverage repair; retain the base catalog."""
from pathlib import Path
from contextlib import contextmanager
import ctypes,hashlib,json,os,shutil,time
from pack_format import shared_read,sha,load_view,groups
from bake_all_views import replace_file

def require(ok,why):
 if not ok:raise RuntimeError(why)
def read(path):return json.loads(shared_read(path))
@contextmanager
def writer(root):
 kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p;kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32];kernel.ReleaseMutex.argtypes=[ctypes.c_void_p];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
 name='Local\\Atlas2.Coverage.'+hashlib.sha256(root.resolve().as_posix().encode()).hexdigest();handle=kernel.CreateMutexW(None,False,name);require(bool(handle),'Coverage writer mutex unavailable')
 try:
  require(kernel.WaitForSingleObject(handle,0) in (0,128),'Another coverage writer is active')
  try:yield
  finally:kernel.ReleaseMutex(handle)
 finally:kernel.CloseHandle(handle)
def atomic_bytes(path,data,token):
 require(shutil.disk_usage(path.parent).free>=16*1024**3+len(data)+32*1024**2,'Free-space reserve before promotion write');tmp=path.with_name(path.name+'.'+token+'.tmp');tmp.write_bytes(data);deadline=time.monotonic()+5
 while True:
  try:replace_file(tmp,path);return
  except OSError as error:
   if (not isinstance(error,PermissionError) and getattr(error,'winerror',None) not in (5,32,33)) or time.monotonic()>=deadline:raise
   time.sleep(.05)
def main():
 work=Path(__file__).resolve().parents[2]/'.local/atlas2';root=(work/'parity-full16').resolve();trial=(work/'coverage-trial11').resolve();area='Area11';source=trial/area;target=root/area
 inventory_path=work/'full-base-inventory.json';strict_path=work/'coverage-trial11-validation.json';cache_path=work/'coverage-trial11-runtime-cache.json';preserved_path=work/'coverage-trial11-preservation.json';receipt_path=work/'coverage-promotion.json'
 inventory=read(inventory_path);strict=read(strict_path);cache=read(cache_path);preserved=read(preserved_path);state=read(root/'generation-state.json');require(state['state']=='complete' and state['complete_views']==602,'Complete base generation required');require(inventory['structural_pass'] and inventory['areas']==16 and inventory['improved_views']==602,'Complete structural inventory required');require(inventory['raster_gap_count']==2 and {g['area'] for g in inventory['raster_gaps']}=={area},'This promotion is limited to the two validated Area11 cases');require(strict['pass'] and strict['improved_views']==46 and strict['raster_gap_count']==0 and cache['pass'] and cache['composite_views']==46 and preserved['pass'],'All isolated trial checks required')
 trial_inventory=read(work/'full-Area11-gap-inventory.json');signature=lambda rows:sorted((g['area'],g['layer_id'],g['triangle_index'],tuple(g['triangle_xz'])) for g in rows);require(signature(inventory['raster_gaps'])==signature(trial_inventory['raster_gaps']),'Trial cases do not match the full inventory');components={p.name:sha(p) for p in [inventory_path,strict_path,cache_path,preserved_path,work/'coverage-trial11-stage-identity.json',Path(__file__).resolve()]};token=hashlib.sha256(json.dumps(components,sort_keys=True).encode()).hexdigest()[:16]
 with writer(root):
  before_index=shared_read(root/'atlas2-index.json');before_hash=hashlib.sha256(before_index).hexdigest();trial_manifest_bytes=shared_read(source/'manifest.json');trial_manifest=json.loads(trial_manifest_bytes);trial_hash=hashlib.sha256(trial_manifest_bytes).hexdigest();trial_index_sha=sha(trial/'atlas2-index.json');require(trial_index_sha==strict['index_sha256']==cache['index_sha256'],'Trial validation/cache identity');trial_entry=next(e for e in read(trial/'atlas2-index.json')['areas'] if e['area']==area);require(trial_entry['manifest_sha256']==trial_hash,'Trial manifest identity')
  if receipt_path.exists():
   old=read(receipt_path)
   if old.get('complete') and old.get('token')==token and old.get('index_after_sha256')==before_hash and sha(target/'manifest.json')==trial_hash:print('COVERAGE_PROMOTION_ALREADY_COMPLETE');return
  require(before_hash==inventory['index_sha256'],'Base catalog changed since complete validation');index=json.loads(before_index);entry=next(e for e in index['areas'] if e['area']==area);before_manifest=shared_read(target/'manifest.json');require(hashlib.sha256(before_manifest).hexdigest()==entry['manifest_sha256'],'Original area identity');base=json.loads(before_manifest);stage=trial_manifest['coverage_stage_id'];backup=source/('manifest-pre-coverage-'+stage[:12]+'.json');require(shared_read(backup)==before_manifest,'Trial was made from a different original area');require(all(trial_manifest[k]==base[k] for k in ['source_sha256','feature_sha256','grid_sha256','bounds','layers','primary','ppu','width','height','levels','world_to_image']),'Trial changed geometry or transforms');require(len(trial_manifest['views'])==46 and len(trial_manifest['coverage_geometry'])==2,'Unexpected trial scope')
  files={}
  def add(relative,identity):
   rel=Path(relative);require(not rel.is_absolute() and '..' not in rel.parts and ':' not in str(rel),'Asset path');src=(source/rel).resolve();dst=target/rel;src.relative_to(source);dst.parent.resolve().relative_to(root);require(src.is_file() and sha(src)==identity,'Validated trial dependency changed');require(rel not in files or files[rel]==identity,'Conflicting dependency identity');files[rel]=identity
  for header in trial_manifest['views']:
   view=load_view(source,header);add(header['view_file'],header['view_sha256']);add(view['line_overlay']['file'],view['line_overlay']['sha256'])
   for group,tiles in groups(view):
    for tile in tiles:
     rel=Path(tile['file'])
     if rel not in files:add(tile['file'],tile['sha256'])
  missing=[]
  for rel,identity in files.items():
   dst=target/rel
   if dst.exists():require(sha(dst)==identity,'Existing catalog object differs from its identity')
   else:missing.append(rel)
  growth=sum((source/rel).stat().st_size for rel in missing)+len(before_index)+len(before_manifest)+len(trial_manifest_bytes)+64*1024**2;size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file());require(size+growth<=16*1024**3,'Promotion output budget');require(shutil.disk_usage(root).free>=16*1024**3+growth,'Promotion free-space reserve');print('COVERAGE_PROMOTION_REVIEW files='+str(len(missing))+' reserved_bytes='+str(growth),flush=True)
  for rel in missing:
   src=source/rel;dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True)
   if src.suffix=='.a2t':
    try:os.link(src,dst)
    except OSError:shutil.copy2(src,dst)
   else:shutil.copy2(src,dst)
   require(sha(dst)==files[rel],'Promoted object content mismatch')
  index_backup=root/('atlas2-index-pre-promote-'+token+'.json');manifest_backup=target/('manifest-pre-promote-'+token+'.json')
  for path,data in [(index_backup,before_index),(manifest_backup,before_manifest)]:
   if path.exists():require(shared_read(path)==data,'Conflicting promotion rollback receipt')
   else:atomic_bytes(path,data,token)
  entry['manifest_sha256']=trial_hash;after_index=json.dumps(index,sort_keys=True).encode();after_hash=hashlib.sha256(after_index).hexdigest();atomic_bytes(target/'manifest.json',trial_manifest_bytes,token)
  try:atomic_bytes(root/'atlas2-index.json',after_index,token)
  except BaseException:
   observed=sha(root/'atlas2-index.json')
   if observed!=after_hash:
    require(observed==before_hash,'Index outcome uncertain; rollback receipts retained');atomic_bytes(target/'manifest.json',before_manifest,token);raise
  require(sha(target/'manifest.json')==trial_hash and sha(root/'atlas2-index.json')==after_hash,'Promotion commit identity');receipt=dict(schema=1,complete=True,token=token,area=area,validated_views=46,missing_files_promoted=len(missing),reserved_growth_bytes=growth,index_before_sha256=before_hash,index_after_sha256=after_hash,manifest_before_sha256=hashlib.sha256(before_manifest).hexdigest(),manifest_after_sha256=trial_hash,components=components,old_objects_and_views_retained=True,full_strict_validation_required=True,native_gameplay_tested=False);atomic_bytes(receipt_path,json.dumps(receipt,indent=2).encode(),token);print('COVERAGE_PROMOTION_COMPLETE area='+area+' views=46',flush=True)
if __name__=='__main__':main()
