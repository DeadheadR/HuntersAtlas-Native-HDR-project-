from pathlib import Path
import os,hashlib,json,shutil,re,zipfile,importlib.util,sys,subprocess,struct
S=Path(__file__).parent;R=Path(r'C:\Users\MichaelPC\Documents\Codex\2026-10-18\task-12\atlas2');W=R/'.local/atlas2';seed=W/'Atlas2-test'
O=S/'staging/HuntersAtlas';O.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
manifest=json.loads((seed/'manifest.json').read_text())
exclude={'atlas2-local.json','Start-Atlas2.cmd'}
for name,expected in manifest['files'].items():
 if name in exclude or name.startswith('tools/'):continue
 source=seed/name
 if sha(source)!=expected:raise RuntimeError('Seed differs: '+name)
 destination=O/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
for name in ('LICENSE',):shutil.copy2(seed/name,O/name)
for folder in ('licenses',):
 if (seed/folder).exists():shutil.copytree(seed/folder,O/folder,dirs_exist_ok=True)
shutil.copy2(S/'compact-build/bb-probe-compact.exe',O/'bin/bb-probe.exe')
def executable_sections(path):
 data=path.read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0];count=struct.unpack_from('<H',data,pe+6)[0];optional=struct.unpack_from('<H',data,pe+20)[0];result={}
 for i in range(count):
  at=pe+24+optional+i*40;name=data[at:at+8].rstrip(b'\0').decode('ascii');size,offset=struct.unpack_from('<II',data,at+16)
  if name in ('.text','.pdata','.xdata','.rdata','.data','.rsrc'):result[name]=hashlib.sha256(data[offset:offset+size]).hexdigest()
 return result
before=executable_sections(O/'bin/bb-probe.exe')
strip=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\.local\native-toolchain\msys64\clang64\bin\llvm-strip.exe')
subprocess.run([str(strip),'--strip-debug',str(O/'bin/bb-probe.exe')],check=True)
if executable_sections(O/'bin/bb-probe.exe')!=before:raise RuntimeError('Stripping changed executable code/data/unwind/resource sections')
compiler=strip.with_name('clang.exe')
subprocess.run([str(compiler),'-O2','-municode','-mwindows',str(S/'compact_launcher.c'),'-o',str(O/'HuntersAtlas.exe')],check=True)
shutil.copytree(S/'compact-maps',O/'maps-baked',dirs_exist_ok=True)
for path in (O/'maps-baked').glob('*.log'):path.unlink()
measurement=O/'maps-baked/measurements.json'
if measurement.exists():measurement.unlink()
# Both launch entry points resolve all map data relative to this extracted folder.
replacement='''    compact_root=contract["root"]/"maps-baked"
    compact_index=contract["manifest"]["compact_maps"]["index_sha256"]
    env.update(BB_ATLAS2_ENABLED="1",BB_ATLAS2_DIR=str(compact_root),BB_ATLAS2_INDEX_SHA256=compact_index,BB_ATLAS2_ASYNC_LOAD="1")
    env.pop("BB_ATLAS2_REFERENCE_DIR",None)
    env.pop("BB_ATLAS2_MEASURE",None)
'''
for name in ('bootstrap/entry.py','bootstrap/integrated_play.py'):
 p=O/name;value=p.read_text();start=value.index('    atlas2=json.loads(');end=value.index('    return env',start)
 value=value[:start]+replacement+value[end:];text(p,value)
# Show the compiled renderer identity through passive diagnostics during this test.
p=O/'bootstrap/integrated_play.py';value=p.read_text();value=value.replace('    return env','    diagnostic_dir=contract["state_root"]/"diagnostics"\n    diagnostic_dir.mkdir(parents=True,exist_ok=True)\n    env.update(BB_MAP_TEST_CONTROL="NUL",BB_MAP_TEST_TRACE=str(diagnostic_dir/"map-trace.json"))\n    return env');text(p,value)
shutil.copy2(S/'compact_install.py',O/'owned/compact_install.py')
text(O/'Install.cmd','@echo off\ncd /d "%~dp0"\n"%~dp0runtime\\python\\python.exe" -I -B "%~dp0owned\\compact_install.py" %*\nif errorlevel 1 (\n echo.\n echo Installation did not finish. Read the message above.\n pause\n exit /b 1\n)\n')
text(O/'Launch.cmd','@echo off\nstart "" "%~dp0HuntersAtlas.exe"\n')
text(O/'Update.cmd','@echo off\necho This is the compact-map test package. Install updates from a complete replacement ZIP.\npause\n')
text(O/'Uninstall.cmd','@echo off\necho This package runs from its extracted folder. It does not modify your game or other launcher.\necho Keep your selected save folder when removing an extracted Atlas folder.\npause\n')
text(O/'README.md',"""# Hunter's Atlas — compact map test

1. Extract the complete ZIP into a new folder, such as `NEW`.
2. Run `Install.cmd`. Select your Bloodborne 1.09 game folder if asked.
3. Open `HuntersAtlas.exe`. In **Mods & patches**, Hunter's Atlas is enabled.
4. Press **Play**, then **Continue** in the game. Press **M** to open the map.

All map geometry and decoration are included. No map generation, compiler,
download or separately installed launcher is needed. Mouse-look starts enabled;
the map releases the mouse when closed. Your existing save folder is retained
when found in your current launcher settings; otherwise choose it in the launcher.

For this test, check the area name, floor selection, zoom/pan, mouse-look after
closing the map, and several map open/close cycles. This is a local test build.
""")
text(O/'SOURCE-BUILD.md',"""# Compact test build

Prepared from the retained Atlas native runtime and bundled Windows 1.9
dependencies, using the compiled vector additions in source/compact.
These additions require the corresponding Hunter's Atlas source tree and its
pinned native build. The installable runtime never compiles or extracts collision.
Retain the supplied LICENSE and third-party notices.
""")
for name in ('map_vector.cpp','bake_vectors.cpp','vector.vert','build_compact.py','compact_launcher.c'):
 destination=O/'source/compact'/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/name,destination)
# The launcher retains its normal Mods page and player settings; preparation and
# remote updater actions do not belong to a fully prepared local test package.
p=O/'integration/ui/bbport_launcher_win.py';value=p.read_text();value=value.replace("root.title('Bloodborne — bbport')","root.title(\"Hunter's Atlas — Compact maps\")")
value=value.replace("'atlas_enabled': False","'atlas_enabled': True")
value=value.replace("        self.atlas_prepare_button.grid(row=self.next_row(f), column=0, sticky='w', pady=(6, 0))","        self.atlas_prepare_button.grid_remove()")
value=value.replace("        self.ttk.Button(f,text=_('Check Atlas updates','Проверить обновления Atlas'),\n                        command=lambda:self.install_atlas_update(VERSION,manual_check=True)).grid(\n            row=self.next_row(f),column=0,sticky='w',pady=(6,0))",'')
value=value.replace("        if package and not package.generated_ready and enabled and not self.process:","        if False and package and not package.generated_ready and enabled and not self.process:")
value=value.replace('    Launcher(root, tk, ttk, filedialog, messagebox)\n','    launcher=Launcher(root, tk, ttk, filedialog, messagebox)\n    root.deiconify()\n')
value=value.replace("        root.after(1800, root.destroy)",'''        launcher.show('mods')
        def audit_ui():
            report={'window_state':root.state(),'window_viewable':bool(root.winfo_viewable()),'atlas_enabled':bool(launcher.var('atlas_enabled','app').get()),'atlas_status':str(launcher.atlas_status.cget('text'))}
            (Path(OWNED_ATLAS_ROOT)/'state/ui-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            root.destroy()
        root.after(12000,audit_ui)''')
text(p,value)
p=O/'integration/ui/atlas_addon.py';value=p.read_text()
value=value.replace("        if contract.get('generator') is None:\n            raise AtlasManifestError('Atlas package is missing its map preparation tool.')", "        compiled = contract.get('manifest',{}).get('compact_maps',{}).get('format') == 'compiled-vector-v1'\n        if contract.get('generator') is None and not compiled:\n            raise AtlasManifestError('Atlas package is missing its map preparation tool.')")
text(p,value)
for name in ('bootstrap/atlas_feature_config.py','integration/ui/atlas_feature_config.py'):
 p=O/name;value=p.read_text().replace("'atlas_travel_enabled': False","'atlas_travel_enabled': True");text(p,value)
text(O/'state/port/settings.ini','[map]\nenabled=1\nkeyboard=0\ncontroller=0\n')
proof=json.loads((seed/'native-build.json').read_text());proof.update(runtime_sha256=sha(O/'bin/bb-probe.exe'),format='compiled-vector-v1',compact_source_receipt=json.loads((S/'compact-build/native-build.json').read_text()))
text(O/'native-build.json',json.dumps(proof,indent=2))
manifest.update(version='1.0 compact test',generator=None,compact_maps=dict(format='compiled-vector-v1',directory='maps-baked',index_sha256=sha(O/'maps-baked/atlas2-index.json')),experimental_atlas2=False)
manifest['files']={p.relative_to(O).as_posix():sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='manifest.json' and 'state' not in p.relative_to(O).parts}
text(O/'manifest.json',json.dumps(manifest,indent=2))
print('COMPACT_PACKAGE_STAGED',sum(p.stat().st_size for p in O.rglob('*') if p.is_file()),flush=True)
if '--zip' in sys.argv:
 target=Path(r'D:\Bloodborne\Hunters-Atlas-Compact-Test.zip');temporary=target.with_suffix('.zip.tmp')
 with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(O.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(O).as_posix())
 os.replace(temporary,target)
 result=dict(zip=str(target),bytes=target.stat().st_size,sha256=sha(target),map_bytes=sum(p.stat().st_size for p in (O/'maps-baked').rglob('*') if p.is_file()),format='compiled-vector-v1')
 text(S/'package-receipt.json',json.dumps(result,indent=2));print(json.dumps(result),flush=True)
