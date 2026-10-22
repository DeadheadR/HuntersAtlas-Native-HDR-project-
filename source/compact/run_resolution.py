from pathlib import Path
import ctypes,os,json,subprocess,hashlib
S=Path(__file__).parent;B=S/'compact-build';assets=Path(r'D:\Bloodborne\NEW\assets')
if not (assets/'art').exists():
 assets=Path(r'D:\Bloodborne\backups\Atlas-20261022-before-compact\old-tests\Atlas baked-map test\review\named-assets')
ctypes.windll.kernel32.SetErrorMode(0x8003)
tc=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\.local\native-toolchain\msys64\clang64\bin')
env=dict(os.environ,PATH=str(tc)+os.pathsep+os.environ.get('PATH',''),BB_ATLAS_ENABLED='1',BB_ATLAS2_ENABLED='1',BB_ATLAS2_DIR=str(S/'compact-maps'),BB_ATLAS2_INDEX_SHA256=hashlib.sha256((S/'compact-maps/atlas2-index.json').read_bytes()).hexdigest(),BB_MAP_DIR=str(assets/'maps'),BB_MAP_ART_DIR=str(assets/'art'),BB_MAP_CONFIG=str(B/'resolution-settings.ini'),BB_MAP_CATALOG=str(assets/'maps/catalog.json'),BB_MAP_FOG_ENABLED='0',BB_MAP_ITEMS_ENABLED='0',BB_MAP_TRAVEL_ENABLED='0',BB_MAP_TEST_CONTROL='NUL')
reports=[]
for w,h in [(1280,720),(1920,1080),(2560,1440),(3840,2160),(1920,1200),(3440,1440),(5120,1440)]:
 trace=B/f'resolution-{w}x{h}-trace.json';output=B/f'resolution-{w}x{h}.json';env['BB_MAP_TEST_TRACE']=str(trace)
 with (B/f'resolution-{w}x{h}.log').open('w') as log:subprocess.run([str(B/'check-resolution.exe'),str(assets/'art/native-font.ttf'),str(w),str(h),str(output),str(trace)],cwd=B,env=env,stdout=log,stderr=log,check=True)
 reports.append(json.loads(output.read_text()));print(f'PASS {w}x{h}',flush=True)
(B/'resolution-results.json').write_text(json.dumps(dict(pass_all=True,scope='Offscreen production styled map renderer; no game or swapchain',cases=reports),indent=2))
