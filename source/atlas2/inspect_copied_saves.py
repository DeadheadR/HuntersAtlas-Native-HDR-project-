"""Read-only bounded inventory. Hash differences do not establish new travel coverage."""
from pathlib import Path
import hashlib,json,os

def hashes(root):
    files={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    identity=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
    return files,identity

def main():
    w=Path(__file__).resolve().parents[2]/'.local/atlas2';protected=json.loads((w/'protected-state.json').read_text());original,identity=hashes(Path(protected['source_saves']));candidates=[];seen=set();scanned=0
    bases=[Path(r'D:\Bloodborne\tools\HuntersAtlas-source\.local'),Path(r'D:\Bloodborne\saves'),w/'qa/live-user',w/'Atlas2-test/state']
    skip={'node_modules','.git','native-toolchain','third_party','compiled','build','seed','downloads','runtime','game'}
    for base in bases:
        if not base.exists():continue
        for folder,dirs,files in os.walk(base):
            root=Path(folder);depth=len(root.relative_to(base).parts);scanned+=1
            dirs[:]=[d for d in dirs if d not in skip and not d.startswith(('session-assets-','mod-game-')) and depth<10]
            if root.name.lower()!='savedata':continue
            dirs[:]=[]
            if str(root.resolve()) in seen:continue
            seen.add(str(root.resolve()));values,digest=hashes(root)
            candidates.append(dict(candidate='Copy'+str(len(candidates)+1).zfill(2),path=str(root),files=len(values),content_identity=digest,identical_to_current_original=values==original,userdata_hashes=sorted(set(v for k,v in values.items() if 'userdata' in k)),coverage_verified=False,provenance_verified=False))
    report=dict(schema=1,read_only=True,bounded_search_roots=[str(b) for b in bases],maximum_depth=10,folders_scanned=scanned,original_identity=identity,candidates=candidates,distinct_content_identities=len(set(c['content_identity'] for c in candidates)),hash_difference_is_not_unlock_evidence=True)
    (w/'copied-save-inventory.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(candidates=len(candidates),distinct_content_identities=report['distinct_content_identities'],identical_to_original=sum(c['identical_to_current_original'] for c in candidates),folders_scanned=scanned)))
if __name__=='__main__':main()
