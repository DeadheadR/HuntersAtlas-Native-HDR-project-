"""Copy the exact installed V1 binary/assets to a private guarded audit profile."""
from pathlib import Path
import hashlib,json,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_test import snapshots
from private_runtime import isolate_overlay
PIN='887f5baf7e149ea7604e4e037fd5eef43a0ad483a8dcb649a6122636d906c557'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def main():
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';installed=Path(r'D:\Bloodborne\HuntersAtlas');dest=work/'V1-stock-test';template=work/'audit-template/savedata';source=work/'qa/live-user/batch03/savedata'
    if sha(installed/'bin/bb-probe.exe')!=PIN:raise RuntimeError('Pinned installed V1 mismatch')
    if dest.exists() or template.exists():raise RuntimeError('Fresh stock-audit paths required')
    before=snapshots(source);template.parent.mkdir(exist_ok=True);shutil.copytree(source,template);assert snapshots(template)==before
    shutil.copytree(installed,dest,ignore=shutil.ignore_patterns('state','__pycache__','*.pyc'))
    for name in ['Install.cmd','Update.cmd','Uninstall.cmd']:(dest/name).write_text('@echo off\necho Private local validation only.\nexit /b 1\n',encoding='utf-8')
    shutil.copytree(work/'Atlas2-test/state/port',dest/'state/port',ignore=shutil.ignore_patterns('fsr4_shaders','*.log'))
    profile=dest/'state/profile';profile.mkdir(parents=True);settings=json.loads((installed/'state/profile/settings.json').read_text());user=dest/'state/test-user';shutil.copytree(template,user/'savedata');settings.update(atlas_dir=str(dest),user_dir=str(user),atlas_fog_enabled=True,check_updates=False,online=False,bridge_live_map=False,extra_env='');write(profile/'settings.json',settings)
    for name in ['import-receipt.json','port-data-import-receipt.json']:write(profile/name,dict(schema=1,source_sha256=None,qa_fixture=True))
    (dest/'state/map-settings.ini').write_text('enabled=1\nkeyboard=0\ncontroller=1\n')
    # Only launch-layer isolation and stock FPS logging are added; the native binary is unchanged.
    guard='    for key in ("BB_USER_DIR","BB_GPU_USER_DIR"):\n        if key in env:Path(env[key]).resolve().relative_to(Path('+repr(str(work))+').resolve())\n    env["BB_FPS_LOG"]="1"\n'
    for name in ['entry.py','integrated_play.py']:
        path=dest/'bootstrap'/name;s=path.read_text();anchor='    return env\n';assert s.count(anchor)==1;path.write_text(s.replace(anchor,guard+anchor),encoding='utf-8',newline='\n')
    isolate_overlay(dest);manifest=json.loads((dest/'manifest.json').read_text());manifest['files']={name:sha(dest/name) for name in manifest['files']};write(dest/'manifest.json',manifest)
    assert sha(dest/'bin/bb-probe.exe')==PIN;assert sha(dest/'assets.atlaslite')==sha(installed/'assets.atlaslite')
    write(work/'stock-audit-preparation.json',dict(schema=1,native_binary_sha256=PIN,native_binary_byte_identical=True,assets_byte_identical=True,template_save_hashes=before,template_source=str(source),original_installed_files_modified=False,workers=0,normal_fog=True));print('EXACT_STOCK_V1_PRIVATE_PROFILE_READY')
if __name__=='__main__':main()
