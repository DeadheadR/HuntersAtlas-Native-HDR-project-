"""Run retained V1 Python suites and native UI/controller tests without a game or GPU."""
from pathlib import Path
import argparse,json,os,re,subprocess
def main():
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--baseline-build',type=Path,required=True);p.add_argument('--native-only',action='store_true');p.add_argument('--native-build',type=Path);p.add_argument('--report-name',default='regression');a=p.parse_args();repo=Path(__file__).resolve().parents[2];work=repo/'.local/atlas2';out=work/a.report_name;out.resolve().relative_to(work.resolve());out.mkdir(exist_ok=True);env=dict(os.environ,PATH=str(a.toolchain)+os.pathsep+os.environ.get('PATH',''),PYTHONDONTWRITEBYTECODE='1');rows=[]
    if a.native_only:rows=[r for r in json.loads((work/'regression-tests.json').read_text())['suites'] if r['suite'] in ['owned','bootstrap','assets']]
    for label,directory,pattern in [('owned','source/owned/tests','test_*.py'),('bootstrap','source/lite/tests/bootstrap','test_*.py'),('assets','source/lite','test_assets.py')]:
        if a.native_only:continue
        log=out/(label+'.log')
        with log.open('w',encoding='utf-8') as f:run=subprocess.run([str(a.python),'-B','-m','unittest','discover','-s',directory,'-p',pattern],cwd=repo,env=env,stdout=f,stderr=f)
        text=log.read_text(encoding='utf-8',errors='replace');match=re.search(r'Ran (\d+) tests?',text);rows.append(dict(suite=label,exit_code=run.returncode,test_count=int(match[1]) if match else None,log=str(log)));print('V1_PYTHON_REGRESSION',label,run.returncode,flush=True)
    compiler=str(a.toolchain/'clang++.exe');inc='-I'+str(repo/'source/native/gpu/third_party/imgui');build=a.native_build.resolve() if a.native_build else work/'native-build'
    common=[compiler,'-std=c++23','-O2','-DNOMINMAX',inc]
    def compile(source,obj):
        with obj.with_suffix('.log').open('w') as f:subprocess.run(common+['-c',str(source),'-o',str(obj)],env=env,stdout=f,stderr=f,check=True)
    test=out/'navigation.obj';stubs=out/'stubs.obj';compile(repo/'source/native/tests/test_navigation_map.cpp',test);compile(repo/'source/atlas2/test_runtime_stubs.cpp',stubs)
    args=common+[str(test),str(stubs)]+[str(build/(name+'.obj')) for name in ['bbport_map.cpp','bbport_map_art.cpp','bbport_map_features.cpp','bbport_map_static.cpp']]+[str(a.baseline_build/'libbbgpu.a'),'-lSDL3','-lz','-lcrypto','-o',str(out/'navigation.exe')]
    with (out/'navigation-link.log').open('w') as f:subprocess.run(args,env=env,stdout=f,stderr=f,check=True)
    for mode in ['v1','v2','disabled']:
        e=dict(env,BB_ATLAS2_ENABLED='0' if mode=='v1' else '1',BB_MAP_DIR=str(work/('reference-assets/maps' if mode=='v1' else 'runtime-assets/maps')),BB_MAP_ART_DIR=str(work/'reference-assets/art'),BB_MAP_CATALOG=str(work/'runtime-assets/maps/catalog.json'),BB_MAP_CONFIG=str(out/(mode+'.ini')),BB_ATLAS2_DIR=str(work/'packs'),BB_ATLAS2_INDEX_SHA256=__import__('hashlib').sha256((work/'packs/atlas2-index.json').read_bytes()).hexdigest(),BB_ATLAS2_REFERENCE_DIR=str(work/'reference-assets/maps'))
        if mode=='disabled':e['BB_ATLAS_ENABLED']='0'
        with (out/(mode+'-ui.log')).open('w') as f:r=subprocess.run([str(out/'navigation.exe')]+(['disabled'] if mode=='disabled' else []),env=e,stdout=f,stderr=f)
        rows.append(dict(suite=mode+'-native-ui',exit_code=r.returncode));print('NATIVE_UI_REGRESSION',mode,r.returncode,flush=True)
    compile(repo/'source/native/tests/test_map_controller.cpp',out/'controller.obj')
    with (out/'controller-link.log').open('w') as f:subprocess.run(common+[str(out/'controller.obj'),str(a.baseline_build/'libbbgpu.a'),'-lSDL3','-o',str(out/'controller.exe')],env=env,stdout=f,stderr=f,check=True)
    with (out/'controller.log').open('w') as f:r=subprocess.run([str(out/'controller.exe')],env=env,stdout=f,stderr=f)
    rows.append(dict(suite='native-controller',exit_code=r.returncode))
    report=dict(schema=1,pass_=all(r['exit_code']==0 for r in rows),suites=rows,native_gameplay_tested=False,native_build=str(build));report['pass']=report.pop('pass_');(work/(a.report_name+'-tests.json')).write_text(json.dumps(report,indent=2));print('ATLAS2_REGRESSION_COMPLETE',report['pass'])
if __name__=='__main__':main()
