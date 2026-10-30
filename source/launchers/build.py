"""Independent compilation and packaging entry points for the two Atlas targets."""
from __future__ import annotations
import argparse, datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path, PurePosixPath

REPO=Path(__file__).resolve().parents[2]
VERSION='3.1'
WINDOWS_SHA='62b44d98825e09cecb52eaf91995249f5ffa963789e75385d1ee5f17bb1f253f'
LANTERN_SHA='0982583284a5ea3d28028fa188db5b025134ef52b3d320440e99d2119e6b9e4e'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def checked_zip(path, expected):
    if sha(path)!=expected:raise ValueError(f'Pinned input archive changed: {path}')
    return zipfile.ZipFile(path)

def safe_name(name):
    p=PurePosixPath(name)
    if '\\' in name or ':' in name or p.is_absolute() or any(x in ('','..','.') for x in p.parts):raise ValueError(f'Unsafe archive name: {name}')
    return p

def extract(archive,root,prefix=''):
    root.mkdir(parents=True,exist_ok=True)
    for member in archive.infolist():
        if member.is_dir() or not member.filename.startswith(prefix):continue
        name=member.filename[len(prefix):]
        if not name:continue
        rel=safe_name(name)
        if ((member.external_attr>>16)&0o170000)==0o120000:raise ValueError('Archive symlink refused')
        dst=root/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        with archive.open(member) as src,dst.open('wb') as out:shutil.copyfileobj(src,out)

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def load_json(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def prepare_lantern_inputs(cfg,source):
    from prepare_lantern import prepare
    from prepare_launcher import prepare as prepare_ui
    inputs=list((REPO/'source/launchers').glob('*'))+list((REPO/'source/compact').glob('*'))
    inputs+=list((REPO/'source/native/src').glob('runtime_*'))
    inputs+=list((REPO/'source/native/src').glob('map_*guard.inc'))+[REPO/'source/lite/integration/bloodborne.ico']
    inputs+=list((REPO/'source/nativeplus').glob('*.patch'))
    signature={p.relative_to(REPO).as_posix():sha(p) for p in sorted(inputs) if p.is_file()}
    mark=source/'ATLAS-PREPARATION-INPUTS.json'
    if mark.is_file() and load_json(mark)==signature:return
    if not source.exists():
        prepare(Path(cfg['lantern_source_root']),source);prepare_ui(source)
    else:
        fresh=REPO/'.local/prepared-sources'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        native=prepare(Path(cfg['lantern_source_root']),fresh);prepare_ui(fresh)
        ui=load_json(fresh/'ATLAS-LAUNCHER-INTEGRATION.json')
        paths=set(native['edits'])|set(native['copies'])
        prefix='launcher/windows/BloodborneLauncher/'
        paths|={prefix+n for n in ui}|{prefix+'Core/AtlasIntegration.cs'}
        paths|={prefix+n for n in ('app.ico','lantern-beta.ico','lantern-stable.ico','lantern-j3loo.ico')}
        paths|={'ATLAS-INTEGRATION.json','ATLAS-LAUNCHER-INTEGRATION.json'}
        for name in sorted(paths):
            target=source/name;candidate=fresh/name
            if not target.is_file() or sha(target)!=sha(candidate):
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(candidate,target)
    write_json(mark,signature)

def runtime_sections(path):
    import struct
    raw=path.read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0]
    count=struct.unpack_from('<H',raw,pe+6)[0];optional=struct.unpack_from('<H',raw,pe+20)[0]
    result={}
    for i in range(count):
        at=pe+24+optional+40*i;name=raw[at:at+8].rstrip(b'\0').decode('ascii')
        size,offset=struct.unpack_from('<II',raw,at+16)
        if name in ('.text','.pdata','.xdata','.rdata','.data','.rsrc'):result[name]=hashlib.sha256(raw[offset:offset+size]).hexdigest()
    return result

def strip_verified(path,msys):
    before=runtime_sections(path)
    env=dict(os.environ,PATH=str(msys/'clang64/bin')+os.pathsep+os.environ.get('PATH',''))
    subprocess.run([str(msys/'clang64/bin/llvm-strip.exe'),'--strip-debug',str(path)],env=env,check=True)
    if runtime_sections(path)!=before:raise ValueError('Stripping changed runtime code/data/unwind sections')

def runtime_dlls(folder,msys):
    """Resolve PE imports recursively against this compiler's DLL set."""
    import re
    reader=msys/'clang64/bin/llvm-readobj.exe'
    system=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'
    queue=list(folder.glob('*.exe'));seen=set();proof={}
    while queue:
        file=queue.pop()
        if file.name.lower() in seen:continue
        seen.add(file.name.lower())
        output=subprocess.run([str(reader),'--coff-imports',str(file)],capture_output=True,text=True,check=True).stdout
        for name in re.findall(r'^\s+Name: (\S+\.dll)\s*$',output,re.MULTILINE|re.IGNORECASE):
            if name.lower().startswith(('api-ms-','ext-ms-')) or (system/name).is_file():continue
            dst=folder/name;src=msys/'clang64/bin'/name
            if src.is_file():shutil.copy2(src,dst)
            if not dst.is_file():raise FileNotFoundError(f'Unresolved runtime import {file.name}: {name}')
            proof[name]=sha(dst);queue.append(dst)
    return proof

def zip_player(root,destination):
    # Explicitly omit every mutable/cache path, even after local testing.
    forbidden={'user','savedata','cache','shader','logs','profile','captures','screenshots','__pycache__'}
    files=[]
    for path in sorted(root.rglob('*')):
        rel=path.relative_to(root)
        if not path.is_file():continue
        if path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400:raise ValueError('Package reparse point refused')
        if any(p in forbidden for p in rel.parts) or path.suffix in ('.pyc','.pyo','.log','.pdb'):continue
        if 'state' in rel.parts and rel.as_posix() not in ('state/port/settings.ini','state/port/bbport.ini','state/port/input.ini'):continue
        files.append(path)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files:archive.write(path,path.relative_to(root).as_posix())
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip():raise ValueError('Player archive failed CRC check')
    os.replace(temporary,destination)
    return {'zip':destination.name,'bytes':destination.stat().st_size,'sha256':sha(destination),'files':len(files)}

def stage_windows(cfg,out,compile_runtime):
    root=out/'HuntersAtlas-Windows';root.mkdir(parents=True,exist_ok=False)
    with checked_zip(Path(cfg['windows_seed_zip']),WINDOWS_SHA) as archive:extract(archive,root)
    build=REPO/'.local/windows19-build';build.mkdir(parents=True,exist_ok=True)
    if compile_runtime:
        arguments=load_json(Path(cfg['windows_link_arguments']))
        arguments=[('-Wl,--out-implib,'+(build/'bb-probe.dll.a').as_posix()) if str(v).startswith('-Wl,--out-implib,') else v for v in arguments]
        if not any(Path(str(v).replace('\\','/')).name=='imgui_impl_vulkan.cpp.obj' for v in arguments):
            backend=Path(cfg['windows_base_build'])/'CMakeFiles/bbgpu.dir/third_party/imgui/backends/imgui_impl_vulkan.cpp.obj'
            if not backend.is_file():raise FileNotFoundError('The pinned ImGui backend object is missing')
            at=next(i for i,v in enumerate(arguments) if Path(str(v).replace('\\','/')).name=='libbbgpu.a')
            # The retained link keeps this backend inside libbbgpu.a. Move its override
            # before that archive, as the original compact-renderer build does.
            arguments.insert(at,str(backend))
        write_json(build/'link-arguments.json',arguments)
        subprocess.run([sys.executable,str(REPO/'source/illustrated/build_native.py'),
            '--source-dir',str(REPO/'source/compact'),'--base-source',str(REPO/'source'),
            '--base-build',cfg['windows_base_build'],'--link-arguments',str(build/'link-arguments.json'),
            '--toolchain',str(Path(cfg['msys_root'])/'clang64/bin'),'--build-dir',str(build),
            '--baseline-exe',str(root/'bin/bb-probe.exe')],check=True)
    if not (build/'bb-probe-illustrated.exe').is_file():raise FileNotFoundError('Compile the Windows edition before packaging it')
    shutil.copy2(build/'bb-probe-illustrated.exe',root/'bin/bb-probe.exe')
    strip_verified(root/'bin/bb-probe.exe',Path(cfg['msys_root']))
    proof=load_json(root/'native-build.json');proof['runtime_sha256']=sha(root/'bin/bb-probe.exe')
    receipt=load_json(build/'build-native-receipt.json')
    proof['atlas_release']=VERSION
    # Published proof contains portable source hashes, not workstation paths.
    proof['dual_target_rebuild']={'target':'windows-v1.9','sources':receipt['sources'],'preservation_rule':receipt['preservation_rule']}
    proof['illustrated_source_receipt']['candidate_sha256']=proof['runtime_sha256']
    write_json(root/'native-build.json',proof)
    dependencies=load_json(root/'dependencies.json')
    write_json(root/'dependencies.json',dependencies)
    shutil.copy2(REPO/'docs/INSTALL-LAUNCHERS.md',root/'docs/INSTALL-LAUNCHERS.md')
    (root/'README.md').write_text(f"# Hunter's Atlas {VERSION} - Windows edition\n\n"
        "Based on Bloodborne for Windows v1.9 (Supermedo).\n\n"
        "Extract into a new folder and run Install.cmd. Select your CUSA00207 Bloodborne 1.09 game folder and the existing save folder containing savedata.\n\n"
        "Open HuntersAtlas.exe, enable Hunter's Atlas in Mods & patches, then Play / Continue. Open the in-game menu and select Map, or press M.\n\n"
        "Full installation and update instructions: [docs/INSTALL-LAUNCHERS.md](docs/INSTALL-LAUNCHERS.md).\n",encoding='utf-8')
    manifest=load_json(root/'manifest.json');manifest.update(version=VERSION,release_revision=VERSION+'-dual-launcher')
    for name in ('bin/bb-probe.exe','native-build.json','dependencies.json','README.md','docs/INSTALL-LAUNCHERS.md'):
        manifest['files'][name]=sha(root/name)
    write_json(root/'manifest.json',manifest)
    return root

def stage_lantern(cfg,out,compile_runtime):
    from prepare_lantern import prepare
    from prepare_launcher import prepare as prepare_ui
    from compile_lantern import compile_engine
    from compile_launcher import compile_launcher
    source=REPO/'.local/lantern-src';ui=REPO/'.local/lantern-ui'
    if compile_runtime:
        prepare_lantern_inputs(cfg,source)
        compile_engine(source,REPO,Path(cfg['msys_root']),int(cfg.get('jobs',4)))
        compile_launcher(source,ui,Path(cfg['dotnet']),REPO/'.local/build-tools')
    probe=source/'engine/out/bb-probe.exe'
    if not probe.is_file() or not (ui/'HuntersAtlas.exe').is_file():raise FileNotFoundError('Build the Lantern runtime and UI first')
    root=out/'HuntersAtlas-Lantern';root.mkdir(parents=True,exist_ok=False)
    with checked_zip(Path(cfg['lantern_binary_zip']),LANTERN_SHA) as archive:
        # Include the official engine resources/DLLs; exclude the three official launch entry points.
        for member in archive.infolist():
            prefix='BloodbornePC/'
            if member.is_dir() or not member.filename.startswith(prefix+'engine/'):continue
            name=member.filename[len(prefix):];safe_name(name)
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(member) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
    shutil.copy2(probe,root/'engine/out/bb-probe.exe');strip_verified(root/'engine/out/bb-probe.exe',Path(cfg['msys_root']))
    for name in ('bb-start.exe','bb-engine-assets.exe','bb-shader-lab.exe','bb-gpu-capabilities.exe','gpu-cache.id','gpu-cache.legacy.id'):
        compiled=source/'engine/out'/name
        if not compiled.is_file():raise FileNotFoundError(compiled)
        shutil.copy2(compiled,root/'engine/out'/name)
        if compiled.suffix=='.exe':strip_verified(root/'engine/out'/name,Path(cfg['msys_root']))
    dll_proof=runtime_dlls(root/'engine/out',Path(cfg['msys_root']))
    shutil.copy2(ui/'HuntersAtlas.exe',root/'HuntersAtlas.exe')
    with checked_zip(Path(cfg['windows_seed_zip']),WINDOWS_SHA) as seed:
        for item in seed.infolist():
            if item.is_dir() or not item.filename.startswith('maps-baked/'):continue
            safe_name(item.filename);target=root/'atlas'/item.filename;target.parent.mkdir(parents=True,exist_ok=True)
            with seed.open(item) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
        import io
        with zipfile.ZipFile(io.BytesIO(seed.read('assets.atlaslite'))) as assets:
            asset_manifest=json.loads(assets.read('manifest.json'))
            extract(assets,root/'atlas/reference')
        for name,expected in asset_manifest['files'].items():
            if sha(root/'atlas/reference'/safe_name(name))!=expected['sha256']:raise ValueError('Reference asset mismatch: '+name)
    # Native+ HDR: its notices (RenoDX's MIT license for PsychoV-30's code), its guide,
    # and an example lantern.ini for its HDR mode.
    shutil.copytree(REPO/'source/nativeplus/licenses',root/'licenses')
    shutil.copy2(REPO/'source/nativeplus/README.md',root/'README-NativePlusHDR.md')
    (root/'nativeplus-example.ini').write_text(
        # No hdr_peak / hdr_paper_white: the peak comes from the display (hdr_peak_auto), the paper
        # white is the engine's 203 nits.
        'hdr=1\nhdr_mode=nativeplus\n'
        'hdr_tonemapper=5\nhdr_exposure=1\nhdr_grade_highlights=50\nhdr_shadows=50\n'
        'hdr_contrast=50\nhdr_saturation=50\nhdr_bloom=50\nhdr_scene_grading=100\n'
        'hdr_black_floor=0\n',encoding='utf-8')
    # The shipped defaults start on Native+, as Native+'s own package does. HDR output stays
    # opt-in (Windows HDR must be on too); peak and paper white come from the display.
    ini=root/'engine/lantern.default.ini'
    defaults=dict(line.split('=',1) for line in (root/'nativeplus-example.ini').read_text().splitlines())
    defaults.pop('hdr')
    lines=[line for line in ini.read_text(encoding='utf-8-sig').splitlines()
           if line.split('=',1)[0].strip() not in defaults.keys()|{'hdr_peak','hdr_paper_white'}]
    ini.write_text('\n'.join(lines+[f'{k}={v}' for k,v in defaults.items()])+'\n',encoding='utf-8')
    # A generic initial file is copied from shipped defaults; never use a developer's personal preferences.
    shutil.copy2(root/'engine/lantern.default.ini',root/'lantern.ini')
    for file in ('NOTICE','LICENSE'):
        shutil.copy2(source/file,root/(file if file=='NOTICE' else 'LICENSE-LANTERN'))
    shutil.copy2(REPO/'LICENSE',root/'LICENSE-ATLAS')
    for name,text in {
        'Install.cmd':'@echo off\ncd /d "%~dp0"\nstart "" "%~dp0HuntersAtlas.exe"\n',
        'Launch.cmd':'@echo off\nstart "" "%~dp0HuntersAtlas.exe"\n',
        'Play.cmd':'@echo off\nstart "" "%~dp0HuntersAtlas.exe" --play\n',
        'Uninstall.cmd':'@echo off\necho This edition runs from its own extracted folder.\necho Keep your chosen save folder. It does not replace another launcher.\npause\n',
    }.items():(root/name).write_text(text,encoding='utf-8')
    shutil.copy2(REPO/'docs/INSTALL-LAUNCHERS.md',root/'INSTALL.md')
    (root/'README.txt').write_text(f"Hunter's Atlas {VERSION} - Awakenchan-compatible edition\n\n"
        "Hunter's Atlas created by MikeTat1988 (https://github.com/MikeTat1988/HuntersAtlas)\n"
        "Based on Lantern Engine v0.9.37.\nLantern Engine by Awaken (https://github.com/Awakenchan/LanternEngine)\n"
        "Native+ HDR by LRF17 (https://github.com/LRF17/LanternEngine-NativePlusHDR): Display > HDR mode > Native+. See README-NativePlusHDR.md.\n"
        "Modified for Hunter's Atlas; not an official Lantern Engine release.\n\n"
        "Extract into a new folder. Run Install.cmd, select your CUSA00207 1.09 game and existing save folder, then Play / Continue. Press M for the map.\n"
        "Find Settings > Hunter's Atlas > Enable Hunter's Atlas. It is integrated into this edition; a separate entry in the ordinary Mods list is not required.\n"
        "Full installation instructions are in INSTALL.md. Graphics, controls, profiles and save backups use the included Lantern-based launcher.\n"
        "This edition has a private launcher profile under state/profile. Other launcher settings and installations are not modified.\n"
        "Install updates using a complete matching Atlas ZIP in a new folder. Stock Lantern updates cannot replace this modified runtime.\n"
        "No game files, saves, personal profiles or shader caches are included.\n",encoding='utf-8')
    launch_files={name:sha(root/name) for name in ('engine/out/bb-probe.exe','engine/out/bb-start.exe','atlas/maps-baked/atlas2-index.json')}
    write_json(root/'atlas/adapter.json',{'schema':1,'target':'lantern-v0.9.37','atlas_version':VERSION,
        'upstream_commit':'d901fbd2ea4bea114b37c26a2a9278d1e97f7b46',
        'map_index_sha256':sha(root/'atlas/maps-baked/atlas2-index.json'),'launch_files':launch_files})
    write_json(root/'package.json',{'version':'0.9.37','atlas_version':VERSION,'engine':'lantern-fps94-atlas-'+VERSION})
    write_json(root/'atlas/runtime-dependencies.json',dll_proof)
    immutable={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
    write_json(root/'atlas-package-manifest.json',{'schema':1,'target':'lantern-v0.9.37','files':immutable})
    return root

def main():
    p=argparse.ArgumentParser();p.add_argument('--target',choices=['windows19','lantern'],required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--package-only',action='store_true');a=p.parse_args();cfg=load_json(a.config)
    for key in ('windows_seed_zip','windows_base_build','windows_link_arguments','lantern_source_root','lantern_binary_zip','msys_root','dotnet'):
        cfg[key]=str((REPO/Path(cfg[key])).resolve())
    base=REPO/'.local/artifacts'/a.target
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out=base/stamp
    out.mkdir(parents=True,exist_ok=False)
    root=stage_windows(cfg,out,not a.package_only) if a.target=='windows19' else stage_lantern(cfg,out,not a.package_only)
    label='Windows' if a.target=='windows19' else 'Lantern-NativePlusHDR'
    result=zip_player(root,out/f'Hunters-Atlas-{VERSION}-{label}.zip')
    result.update(target=a.target,atlas_version=VERSION)
    write_json(out/'build-receipt.json',result)
    write_json(base/'latest.json',{'directory':str(out),'receipt':result})
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
