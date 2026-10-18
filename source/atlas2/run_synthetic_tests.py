"""Build and run headless synthetic Vulkan coverage without game content."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
from launch_session import verify_lease
def main():
 p=argparse.ArgumentParser();p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--baseline-build',type=Path,required=True);p.add_argument('--native-build',type=Path,required=True);p.add_argument('--reserved-window');a=p.parse_args();repo=Path(__file__).resolve().parents[2];w=repo/'.local/atlas2';out=w/'synthetic-test06';out.mkdir(exist_ok=True);environment=dict(os.environ,PATH=str(a.toolchain)+os.pathsep+os.environ.get('PATH',''));c=[str(a.toolchain/'clang++.exe'),'-std=c++23','-O2','-DNDEBUG','-DNOMINMAX','-I'+str(repo/'source/native/gpu/third_party/imgui')];obj=out/'test.obj'
 def build(args,name):
  with (out/(name+'.build.log')).open('w') as log:subprocess.run(args,env=environment,stdout=log,stderr=log,check=True)
 build(c+['-c',str(Path(__file__).with_name('test_vulkan_tiles.cpp')),'-o',str(obj)],'test');executables={}
 for name,extra in [('old',[]),('fixed',[str(a.native_build/'imgui_impl_vulkan.cpp.obj')])]:
  exe=out/(name+'.exe');build(c+[str(obj),str(a.native_build/'bbport_map_static.cpp.obj')]+extra+[str(a.baseline_build/'libbbgpu.a'),'-lSDL3','-lz','-lcrypto','-lvulkan-1','-o',str(exe)],name);executables[name]=exe
 print('SYNTHETIC_TEST_BINARIES_READY',flush=True)
 if not a.reserved_window:return
 rows=[]
 for name,pool,mode in [('old',16,'reject'),('fixed',96,'normal'),('fixed',96,'inject')]:
  verify_lease(w,a.reserved_window);report=out/(name+'-'+mode+'.json');run=subprocess.run([str(executables[name]),str(w/'synthetic-grid06'),str(report),str(pool),mode],env=environment,timeout=120);r=json.loads(report.read_text());rows.append(dict(name=name,mode=mode,exit_code=run.returncode,result=r));(out/'results.json').write_text(json.dumps(dict(schema=1,no_game_content=True,results=rows),indent=2))
  if run.returncode or not r['pass']:raise RuntimeError('Synthetic Vulkan phase failed: '+name+' '+mode)
 print('SYNTHETIC_ALL_PHASES_PASS',flush=True)
if __name__=='__main__':main()
