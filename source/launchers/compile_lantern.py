"""Build the isolated modified Lantern engine with an existing CLANG64 toolchain."""
import argparse, json, os, subprocess
from pathlib import Path

def compile_engine(source:Path,repo:Path,msys:Path,jobs:int):
    engine=source/'engine'; bash=msys/'usr/bin/bash.exe'
    if not bash.is_file():raise FileNotFoundError(bash)
    env=os.environ.copy()
    env.update(MSYSTEM='CLANG64',MSYS2_PATH_TYPE='inherit',CC='clang',CXX='clang++',
        BB_JOBS=str(jobs),BB_LTO='ON',BB_PGO='off',BB_ATLAS_FORCE_BUILD='1',
        ATLAS_SOURCE_ROOT=repo.resolve().as_posix(),
        CMAKE_PREFIX_PATH=(msys/'clang64').resolve().as_posix(),
        PKG_CONFIG_PATH=(msys/'clang64/lib/pkgconfig').resolve().as_posix())
    env['PATH']=os.pathsep.join([str(msys/'clang64/bin'),str(msys/'usr/bin'),env.get('PATH','')])
    log=source/'atlas-native-build.log'
    with log.open('wb') as stream:
        result=subprocess.run([str(bash),'--noprofile','--norc','build.sh'],cwd=engine,env=env,
            stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(errors='replace')[-9000:]);raise RuntimeError(f'Native build failed: {log}')
    print(f'Native engine built: {engine / "out/bb-probe.exe"}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--msys',type=Path,required=True);p.add_argument('--jobs',type=int,default=4)
    a=p.parse_args();compile_engine(a.source.resolve(),a.repo.resolve(),a.msys.resolve(),a.jobs)
