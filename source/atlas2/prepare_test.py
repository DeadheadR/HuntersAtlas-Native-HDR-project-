"""Prepare a private Atlas2 install and copied-save profile without launching a game."""
from pathlib import Path
import argparse,hashlib,json,os,runpy,shutil,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from private_runtime import isolate_overlay

PIN='887f5baf7e149ea7604e4e037fd5eef43a0ad483a8dcb649a6122636d906c557'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def snapshots(root):
    result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink() or getattr(p,'is_junction',lambda:False)():raise RuntimeError('Linked savedata rejected')
        if p.is_file():result[p.relative_to(root).as_posix()]=sha(p)
    return result
def sfo(p):
    data=p.read_bytes();magic,ver,keys,values,count=struct.unpack_from('<5I',data)
    if magic!=0x46535000:raise RuntimeError('SFO format')
    out={}
    for i in range(count):
        k,fmt,n,maxlen,v=struct.unpack_from('<HHIII',data,20+16*i)
        key=data[keys+k:data.index(b'\0',keys+k)].decode()
        if key in ['TITLE_ID','APP_VER']:out[key]=data[values+v:values+v+n].rstrip(b'\0').decode()
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument('--installed',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--saves',type=Path,required=True);a=p.parse_args();work=a.work.resolve();dest=work/'Atlas2-test'
    if sha(a.installed/'bin/bb-probe.exe')!=PIN:raise RuntimeError('Pinned runtime mismatch')
    identity=sfo(a.game/'sce_sys/param.sfo')
    if identity!={'TITLE_ID':'CUSA00207','APP_VER':'01.09'}:raise RuntimeError('Game version mismatch')
    game_sha=sha(a.game/'eboot.bin');feature=json.loads((work/'reference-assets/maps/features.json').read_text())
    if game_sha!=feature['game_eboot_sha256']:raise RuntimeError('Game executable mismatch')
    if dest.exists():raise RuntimeError('Test installation must be fresh')
    shutil.copytree(a.installed,dest,ignore=shutil.ignore_patterns('state','__pycache__','*.pyc'))
    for name in ['Install.cmd','Update.cmd','Uninstall.cmd']:
        (dest/name).write_text('@echo off\necho Local experimental profile. Use Start-Atlas2.cmd. System installation is disabled.\nexit /b 1\n',encoding='utf-8')
    shutil.copy2(work/'native-build/bb-probe-atlas2.exe',dest/'bin/bb-probe.exe')
    # A separate verified reference executable remains immutable and identifiable.
    reference=work/'V1-reference';reference.mkdir();shutil.copy2(a.installed/'bin/bb-probe.exe',reference/'bb-probe.exe')
    profile=dest/'state/profile';profile.mkdir(parents=True);settings=json.loads((a.installed/'state/profile/settings.json').read_text())
    savedata=dest/'state/test-user/savedata';before=snapshots(a.saves);savedata.parent.mkdir(parents=True);shutil.copytree(a.saves,savedata)
    if snapshots(savedata)!=before or snapshots(a.saves)!=before:raise RuntimeError('Copied-save verification failed')
    settings.update(atlas_dir=str(dest),user_dir=str(savedata.parent),atlas_fog_enabled=True,check_updates=False,online=False,bridge_live_map=False,extra_env='')
    write(profile/'settings.json',settings)
    write(profile/'import-receipt.json',dict(schema=1,source_sha256=None,qa_fixture=True))
    write(profile/'port-data-import-receipt.json',dict(schema=1,qa_fixture=True))
    shutil.copytree(a.installed/'state/port',dest/'state/port',ignore=shutil.ignore_patterns('fsr4_shaders','*.log'))
    (dest/'state/map-settings.ini').write_text('enabled=1\nkeyboard=0\ncontroller=1\n')
    # Strip draw geometry from the normal live path. Original validated geometry is retained separately for developer comparison.
    reduced=work/'runtime-assets';shutil.copytree(work/'reference-assets',reduced)
    atlas=json.loads((reduced/'maps/atlas.json').read_text());index=json.loads((work/'packs/atlas2-index.json').read_text());entries={r['region_id']:r for r in index['areas']}
    for record in atlas['maps']:
        entry=entries[record['id']];record['name']=entry['area'];path=reduced/'maps'/(record['id']+'.json');m=json.loads(path.read_text());manifest=json.loads((work/'packs'/entry['area']/'manifest.json').read_text());m['name']=entry['area']
        for l in m['layers']:
            l.update(triangles=[],heights=[],outlines=[],walls=[])
        for k in ['lamps','markers']:
            for i,marker in enumerate(m.get(k,[]),1):marker['name']=f'Marker{i:03}'
        write(path,m)
    write(reduced/'maps/atlas.json',atlas);write(reduced/'maps/catalog.json',{})
    receipt=json.loads((reduced/'maps/generated-assets.json').read_text());receipt['files']={name:sha(reduced/name) for name in receipt['files']};write(reduced/'maps/generated-assets.json',receipt)
    inputs={p.relative_to(reduced).as_posix():p for p in reduced.rglob('*') if p.is_file()}
    assets=runpy.run_path(str(a.installed/'bootstrap/assets.py'));assets['build'](inputs,dest/'assets.atlaslite')
    config=dict(enabled='1',directory=str(work/'packs'),index_sha256=sha(work/'packs/atlas2-index.json'),reference_directory=str(work/'reference-assets/maps'),allowed_user_root=str(work))
    write(dest/'atlas2-local.json',config)
    # Both official entry paths explicitly restore experimental options after their environment sanitization.
    env_text='\n    atlas2=json.loads((contract["root"]/"atlas2-local.json").read_text(encoding="utf-8"))\n    env.update(BB_ATLAS2_ENABLED=atlas2["enabled"],BB_ATLAS2_DIR=atlas2["directory"],BB_ATLAS2_INDEX_SHA256=atlas2["index_sha256"],BB_ATLAS2_REFERENCE_DIR=atlas2["reference_directory"])\n    for key in ("BB_USER_DIR","BB_GPU_USER_DIR"):\n        if key in env:Path(env[key]).resolve().relative_to(Path(atlas2["allowed_user_root"]).resolve())\n'
    for name in ['entry.py','integrated_play.py']:
        path=dest/'bootstrap'/name;s=path.read_text(encoding='utf-8')
        if name=='integrated_play.py':anchor='    return env\n'
        else:
            # The owned normal launch helper returns env immediately before the next function.
            anchor='    return env\n'
        if s.count(anchor)!=1:raise RuntimeError('Environment injection anchor mismatch')
        path.write_text(s.replace(anchor,env_text+anchor),encoding='utf-8',newline='\n')
    native=json.loads((dest/'native-build.json').read_text());native.update(runtime_sha256=sha(dest/'bin/bb-probe.exe'),experimental_atlas2=True,reference_runtime_sha256=PIN);write(dest/'native-build.json',native)
    isolate_overlay(dest)
    manifest=json.loads((dest/'manifest.json').read_text());manifest['asset_pack']['sha256']=sha(dest/'assets.atlaslite');manifest['experimental_atlas2']=True
    for name in list(manifest['files']):manifest['files'][name]=sha(dest/name)
    manifest['files']['atlas2-local.json']=sha(dest/'atlas2-local.json');write(dest/'manifest.json',manifest)
    (dest/'Start-Atlas2.cmd').write_text('@echo off\nset "BB_ATLAS_PROFILE_ROOT=%~dp0state\\profile"\nset "BB_LAUNCHER_SETTINGS_ROOT=%~dp0state\\profile"\nset "BB_OWNED_ATLAS_ROOT=%~dp0"\n"%~dp0runtime\\python\\pythonw.exe" -I -B "%~dp0owned\\app.py"\n',encoding='utf-8')
    write(work/'protected-state.json',dict(schema=1,game=identity,game_eboot_sha256=game_sha,source_saves=str(a.saves),source_save_hashes=before,copied_save_file_count=len(before),original_atlas_runtime_sha256=sha(a.installed/'bin/bb-probe.exe'),reference_runtime_sha256=sha(reference/'bb-probe.exe'),test_install=str(dest),native_launched=False))
    print('ATLAS2_PRIVATE_INSTALL_READY copied_save_files='+str(len(before)))
if __name__=='__main__':main()
