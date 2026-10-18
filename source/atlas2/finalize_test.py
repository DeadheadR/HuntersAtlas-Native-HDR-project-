"""Refresh only the private experimental install after a local rebuild."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from private_runtime import isolate_overlay
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('work',type=Path);a=parser.parse_args();work=a.work.resolve();root=work/'Atlas2-test'
    config=json.loads((root/'atlas2-local.json').read_text());config.update(allowed_user_root=str(work),index_sha256=sha(work/'packs/atlas2-index.json'));write(root/'atlas2-local.json',config)
    for name in ['Install.cmd','Update.cmd','Uninstall.cmd']:
        (root/name).write_text('@echo off\necho Local experimental profile. Use Start-Atlas2.cmd. System installation is disabled.\nexit /b 1\n',encoding='utf-8')
    for name in ['entry.py','integrated_play.py']:
        p=root/'bootstrap'/name;s=p.read_text(encoding='utf-8')
        anchor='    env.update(BB_ATLAS2_ENABLED=atlas2["enabled"],BB_ATLAS2_DIR=atlas2["directory"],BB_ATLAS2_INDEX_SHA256=atlas2["index_sha256"],BB_ATLAS2_REFERENCE_DIR=atlas2["reference_directory"])\n'
        guard='    for key in ("BB_USER_DIR","BB_GPU_USER_DIR"):\n        if key in env:Path(env[key]).resolve().relative_to(Path(atlas2["allowed_user_root"]).resolve())\n'
        if guard not in s:
            assert s.count(anchor)==1;s=s.replace(anchor,anchor+guard);p.write_text(s,encoding='utf-8',newline='\n')
    profile=root/'state/profile'
    for name in ['import-receipt.json','port-data-import-receipt.json']:write(profile/name,dict(schema=1,source_sha256=None,qa_fixture=True))
    shutil.copy2(work/'native-build/bb-probe-atlas2.exe',root/'bin/bb-probe.exe')
    native=json.loads((root/'native-build.json').read_text());native['runtime_sha256']=sha(root/'bin/bb-probe.exe');write(root/'native-build.json',native)
    isolate_overlay(root)
    m=json.loads((root/'manifest.json').read_text());m['files']={name:sha(root/name) for name in m['files']};write(root/'manifest.json',m)
    print('ATLAS2_PRIVATE_INSTALL_REFRESHED')
if __name__=='__main__':main()
