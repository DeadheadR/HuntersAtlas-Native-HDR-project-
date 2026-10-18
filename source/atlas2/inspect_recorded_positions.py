"""Read existing managed QA evidence; recorded XYZ never become arbitrary teleport targets."""
from pathlib import Path
import json

def read(path):
    try:return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return {}

def main():
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';index=read(work/'packs/atlas2-index.json');by_prefix={sum(int(v)<<(24-8*i) for i,v in enumerate(e['region_id'][1:].split('_')[:2])):e['area'] for e in index['areas']};root=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\.local\owned-integration-qa\runs');records={};launches=[];max_available=0;files_read=0
    def visit(value,source):
        nonlocal max_available
        if isinstance(value,dict):
            if value.get('valid') is True and all(isinstance(value.get(k),(int,float)) for k in ('block','x','y','z')):
                area=by_prefix.get(int(value['block'])&0xffff0000,'Area00');key=(area,)+tuple(round(value[k],5) for k in ('x','y','z'));records.setdefault(key,dict(area=area,block=value['block'],xyz=[value[k] for k in ('x','y','z')],source_id=source))
            if isinstance(value.get('available_lamps'),int):max_available=max(max_available,value['available_lamps'])
            for item in value.values():visit(item,source)
        elif isinstance(value,list):
            for item in value:visit(item,source)
    if root.exists():
        for session in root.iterdir():
            if not session.is_dir() or not (session/'launch.json').is_file():continue
            launch=read(session/'launch.json');launches.append(launch)
            for path in session.rglob('*.json'):
                if path.stat().st_size>4*1024*1024:continue
                files_read+=1;visit(read(path),'Record'+str(files_read).zfill(3))
    inventory=read(work/'copied-save-inventory.json');original=read(work/'protected-state.json')['source_save_hashes'];proven=0
    for candidate in inventory['candidates']:
        for launch in launches:
            if Path(launch.get('user_dir','')).resolve()==Path(candidate['path']).parent.resolve():
                candidate['provenance_verified']=isinstance(launch.get('source_savedata_sha256'),dict);candidate['receipt_source_matches_current_original']=launch.get('source_savedata_sha256')==original;proven+=candidate['provenance_verified'];break
    (work/'copied-save-inventory.json').write_text(json.dumps(inventory,indent=2));areas=sorted(set(r['area'] for r in records.values()));report=dict(schema=1,files_read=files_read,unique_recorded_positions=len(records),areas=areas,max_recorded_eligible_targets=max_available,receipt_verified_copy_candidates=proven,records=list(records.values()),native_teleport_coverage_extended=False,recorded_xyz_are_not_guarded_destinations=True,options=['Use recorded XYZ for offline projection/layer tests only','Copy an existing receipt-verified alternate QA save into a fresh isolated profile, then inspect guarded flags before attempting travel','For absent discovered targets, use an owned copied profile exposing additional normal native destinations; do not patch flags or raw coordinates'],decision_required_for_current_measurements=False)
    (work/'recorded-position-inventory.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ('files_read','unique_recorded_positions','areas','max_recorded_eligible_targets','receipt_verified_copy_candidates','native_teleport_coverage_extended')}))
if __name__=='__main__':main()
