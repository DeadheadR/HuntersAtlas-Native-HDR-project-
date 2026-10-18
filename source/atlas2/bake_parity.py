"""CPU-only quality comparison in fresh private output roots; never edits live packs."""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,shutil,subprocess,time

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--baker',type=Path,required=True);p.add_argument('--ppu',type=int,choices=[8,16,32],required=True);p.add_argument('--areas',nargs='+',default=['Area02','Area10']);p.add_argument('--primary-only',action='store_true')
    p.add_argument('--runtime-directory',type=Path,required=True);p.add_argument('--all-area-fallback',action='store_true');p.add_argument('--layers',nargs='*',default=[],help='Explicit anonymous AreaNN:index,index selections');a=p.parse_args()
    baseline=a.baseline.resolve();out=a.output.resolve();environment=dict(os.environ);environment['PATH']=str(a.runtime_directory.resolve())+os.pathsep+environment.get('PATH','')
    if os.name=='nt':ctypes.windll.kernel32.SetErrorMode(0x0001|0x0002|0x8000)
    if out.exists() or out.is_relative_to(baseline) or baseline.is_relative_to(out):raise RuntimeError('Fresh isolated output root required')
    if a.all_area_fallback:shutil.copytree(baseline,out)
    else:out.mkdir(parents=True)
    index=json.loads((baseline/'atlas2-index.json').read_text());selected=[e for e in index['areas'] if e['area'] in a.areas];selections={k:[int(x) for x in v.split(',')] for k,v in (item.split(':',1) for item in a.layers)}
    if len(selected)!=len(set(a.areas)):raise RuntimeError('Unknown anonymous area ID')
    identity=hashlib.sha256(b''.join((Path(__file__).parent/f).read_bytes() for f in ('bake_parity.cpp','parity_style.h','core.h'))).hexdigest();results=[]
    for e in selected:
        label=e['area'];dest=out/label
        if not a.all_area_fallback:shutil.copytree(baseline/label,dest)
        m=json.loads((dest/'manifest.json').read_text());primary=m['primary'];layers=selections.get(label,[primary] if a.primary_only or label=='Area10' else list(range(len(m['layers']))))
        before=time.monotonic();run=subprocess.run([str(a.baker.resolve()),str(a.assets.resolve()/'maps'/(e['region_id']+'.json')),str(a.assets.resolve()/'maps/features.json'),str(dest/'manifest.json'),str(dest),label,str(a.ppu),','.join(map(str,layers)),str(a.assets.resolve()/'art'),identity],capture_output=True,text=True,env=environment,timeout=1800)
        (dest/'bake.log').write_text(run.stdout+run.stderr)
        if run.returncode:raise RuntimeError('CPU parity bake failed for '+label+'; inspect private bake.log')
        m=json.loads((dest/'manifest.json').read_text());e['manifest_sha256']=digest(dest/'manifest.json');row=dict(area=label,ppu=a.ppu,selected_layers=layers,seconds=time.monotonic()-before,new_object_bytes=m['parity_new_object_bytes'],new_objects=m['parity_new_objects'],peak_primitives=m['parity_peak_primitive_count'],total_area_bytes=sum(f.stat().st_size for f in dest.rglob('*') if f.is_file()));results.append(row);print(json.dumps(row),flush=True)
    if not a.all_area_fallback:index['areas']=selected
    (out/'atlas2-index.json').write_text(json.dumps(index,sort_keys=True));(out/'quality-measurements.json').write_text(json.dumps(dict(schema=1,generator_identity=identity,offline_only=True,all_area_legacy_fallback=a.all_area_fallback,live_visual_acceptance='unverified',measurements=results),indent=2));print('PARITY_CPU_PACKS_READY',flush=True)
if __name__=='__main__':main()

