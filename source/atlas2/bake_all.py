"""Local CPU-only pack builder. Run with the owned private Python. Never distribute output."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--assets',type=Path,required=True)
    p.add_argument('--baker',type=Path,required=True)
    p.add_argument('--areas',nargs='*')
    p.add_argument('--ppu',type=float,default=8)
    a=p.parse_args()
    source=a.assets/'maps';a.root.mkdir(parents=True,exist_ok=True)
    identity=hashlib.sha256(b''.join((Path(__file__).parent/n).read_bytes() for n in ['core.h','bake.cpp'])).hexdigest()
    index_path=a.root/'atlas2-index.json'
    index=json.loads(index_path.read_text()) if index_path.exists() else dict(schema=1,reference_commit='4ee4a0edf00ca87797e40f7ad73c27c9b2198625',areas=[])
    atlas=json.loads((source/'atlas.json').read_text())
    for n,record in enumerate(atlas['maps'],1):
        label=f'Area{n:02}'
        if a.areas and label not in a.areas:continue
        dest=a.root/label
        if not dest.exists():
            subprocess.run([str(a.baker.resolve()),str(source/(record['id']+'.json')),str(source/'features.json'),str(dest),label,str(a.ppu),identity],check=True)
        m=json.loads((dest/'manifest.json').read_text())
        if m['source_sha256']!=digest(source/(record['id']+'.json')) or m['feature_sha256']!=digest(source/'features.json') or m['generator_identity']!=identity or m['ppu']!=a.ppu:
            raise RuntimeError('Existing pack identity mismatch; use a fresh output root')
        row=dict(area=label,region_id=record['id'],manifest_sha256=digest(dest/'manifest.json'))
        index['areas']=[r for r in index['areas'] if r['area']!=label]+[row]
        index['areas'].sort(key=lambda r:r['area'])
        temp=index_path.with_suffix('.tmp');temp.write_text(json.dumps(index,sort_keys=True));temp.replace(index_path)
    print('ATLAS2_INDEX_READY',len(index['areas']),flush=True)

if __name__=='__main__':main()
