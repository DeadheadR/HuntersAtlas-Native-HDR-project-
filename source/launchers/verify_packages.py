"""Audit the two actual player archives before distribution."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from build import safe_name,sha,write_json

def verify(windows:Path,lantern:Path):
    report={'pass_all':False,'archives':{}}
    archives={}
    for target,path in [('windows19',windows),('lantern',lantern)]:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None,'ZIP CRC failure'
            names=[i.filename for i in z.infolist() if not i.is_dir()]
            assert len(names)==len(set(n.casefold() for n in names)),'Duplicate/case-colliding paths'
            for name in names:
                parts=safe_name(name).parts
                assert not any(p.casefold() in {'savedata','logs','profile','__pycache__','screenshots','captures'} for p in parts),name
                assert not name.lower().endswith(('.pyc','.pyo','.log','.pdb')),name
            manifest_name='manifest.json' if target=='windows19' else 'atlas-package-manifest.json'
            manifest=json.loads(z.read(manifest_name))
            for name,digest in manifest['files'].items():
                safe_name(name)
                assert hashlib.sha256(z.read(name)).hexdigest()==digest,'Manifest mismatch: '+name
            if target=='lantern':
                assert set(names)==set(manifest['files'])|{manifest_name},'Unlisted Lantern package files'
                adapter=json.loads(z.read('atlas/adapter.json'))
                assert adapter['target']=='lantern-v0.9.37'
                for name,digest in adapter['launch_files'].items():
                    assert hashlib.sha256(z.read(name)).hexdigest()==digest
                package=json.loads(z.read('package.json'))
                assert package['engine']=='lantern-fps94-atlas-3.1'
                credit='Lantern Engine by Awaken (https://github.com/Awakenchan/LanternEngine)'
                assert credit in z.read('NOTICE').decode() and credit in z.read('README.txt').decode()
                assert 'not an official Lantern Engine release' in z.read('README.txt').decode()
                deps=json.loads(z.read('atlas/runtime-dependencies.json'))
                for name,digest in deps.items():assert hashlib.sha256(z.read('engine/out/'+name)).hexdigest()==digest
                map_prefix='atlas/maps-baked/'
            else:
                native=json.loads(z.read('native-build.json'))
                assert native['upstream_release']=='windows-v1.9'
                assert native['runtime_sha256']==hashlib.sha256(z.read('bin/bb-probe.exe')).hexdigest()
                map_prefix='maps-baked/'
            archives[target]={name[len(map_prefix):]:hashlib.sha256(z.read(name)).hexdigest() for name in names if name.startswith(map_prefix)}
            report['archives'][target]={'sha256':sha(path),'bytes':path.stat().st_size,'files':len(names),'manifest_files':len(manifest['files'])}
    assert archives['windows19']==archives['lantern'],'The two editions must carry the same published Atlas maps'
    report.update(pass_all=True,identical_map_files=len(archives['windows19']))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--windows',type=Path,required=True);p.add_argument('--lantern',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();r=verify(a.windows,a.lantern);write_json(a.report,r);print(json.dumps(r,indent=2))
