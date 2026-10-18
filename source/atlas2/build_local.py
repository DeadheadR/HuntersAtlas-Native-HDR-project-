"""Build only changed Atlas objects; read the retained pinned 1.9 build, never mutate it.

The original renderer/runtime archives are reused unchanged. No network and no game launch.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,ctypes,struct

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def split(s):
    count=ctypes.c_int();fn=ctypes.windll.shell32.CommandLineToArgvW
    fn.restype=ctypes.POINTER(ctypes.c_wchar_p)
    fn.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]
    ptr=fn(s,ctypes.byref(count))
    try:return [ptr[i] for i in range(count.value)]
    finally:ctypes.windll.kernel32.LocalFree(ctypes.cast(ptr,ctypes.c_void_p))
def text_section(p):
    b=Path(p).read_bytes();pe=struct.unpack_from('<I',b,0x3c)[0]
    count=struct.unpack_from('<H',b,pe+6)[0];optional=struct.unpack_from('<H',b,pe+20)[0]
    for i in range(count):
        at=pe+24+optional+40*i
        if b[at:at+8].rstrip(b'\0')==b'.text':
            n,offset=struct.unpack_from('<II',b,at+16)
            return hashlib.sha256(b[offset:offset+n]).hexdigest()
    raise RuntimeError('PE text section missing')
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline-build',type=Path,required=True)
    parser.add_argument('--toolchain',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--link-only',action='store_true',help='Relink already compiled isolated objects after a link-only repair')
    a=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,PATH=str(a.toolchain)+os.pathsep+os.environ.get('PATH',''))
    ninja=a.toolchain/'ninja.exe'
    commands=subprocess.check_output([str(ninja),'-t','commands','bb-probe.exe'],cwd=a.baseline_build,env=env,text=True)
    link=commands.splitlines()[-1]
    # Retained CMake Windows link rule is a shell wrapper around one compiler call.
    m=re.search(r'([A-Za-z]:[/\\][^" ]*clang\+\+\.exe) (.*?) && cd \.',link)
    if not m:raise RuntimeError('Unsupported retained link command')
    args=[m[1]]+split('dummy '+m[2])[1:]
    expanded=[]
    for arg in args:
        if arg.startswith('@'):
            response=a.baseline_build/arg[1:]
            if response.exists():content=response.read_text()
            else:
                ninja_text=(a.baseline_build/'build.ninja').read_text()
                rule=re.search(r'^build bb-probe\.exe: \S+ (.*?)\n(.*?)(?=\n\n)',ninja_text,re.M|re.S)
                if not rule:raise RuntimeError('Retained link rule missing')
                inputs=rule[1].split(' |')[0]
                libraries=re.search(r'^  LINK_LIBRARIES = (.*)$',rule[2],re.M)
                paths=re.search(r'^  LINK_PATH = (.*)$',rule[2],re.M)
                content=inputs+' '+(paths[1] if paths else '')+' '+libraries[1]
            expanded.extend(split('dummy '+content)[1:])
        else:expanded.append(arg)
    args=expanded
    args[0]=str(a.toolchain/'clang++.exe')
    baseline_native=a.baseline_build.parent/'seed/native'
    pinned=a.baseline_build.parent/'package/bin/bb-probe.exe'
    if sha(pinned)!='887f5baf7e149ea7604e4e037fd5eef43a0ad483a8dcb649a6122636d906c557':raise RuntimeError('Pinned reference identity mismatch')
    if text_section(a.baseline_build/'bb-probe.exe')!=text_section(pinned):raise RuntimeError('Retained native build code differs from pinned reference')
    repo_native=root/'native'
    names=['bbport_map.cpp','bbport_map_art.cpp','bbport_map_features.cpp','bbport_map_static.cpp']
    baseline_sha={}
    for name in names[:-1]:
        baseline=baseline_native/'gpu/shim'/name
        original=subprocess.check_output(['git','-c','safe.directory='+str(root.parent).replace('\\','/'),'-C',str(root.parent),'show','4ee4a0e:source/native/gpu/shim/'+name])
        if original.replace(b'\r\n',b'\n')!=baseline.read_bytes().replace(b'\r\n',b'\n'):raise RuntimeError('Retained baseline source differs from selected V1')
        baseline_sha[name]=sha(baseline)
    objects=[]
    for name in names:
        obj=a.output/(name+'.obj')
        cmd=[str(a.toolchain/'clang++.exe'),'-std=gnu++23','-O2','-g','-DNDEBUG','-DNOMINMAX','-DWIN32_LEAN_AND_MEAN','-DIMGUI_IMPL_VULKAN_NO_PROTOTYPES','-fno-omit-frame-pointer','-Wno-deprecated-declarations','-Wno-missing-field-initializers','-include',str(repo_native/'gpu/mingw_libcxx_compat.h'),'-include',str(repo_native/'gpu/shim/bb_win_compat.h'),'-I'+str(repo_native/'gpu/third_party/imgui'),'-I'+str(repo_native/'gpu/shim'),'-c',str(repo_native/'gpu/shim'/name),'-o',str(obj)]
        if a.link_only:
            if not obj.is_file():raise RuntimeError('Compiled object missing')
        else:
            with (a.output/(name+'.log')).open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=log,check=True)
        objects.append(str(obj));print('ATLAS2_OBJECT_READY',len(objects),flush=True)
    # Resolve input files against retained build. Change only output target and prepend overrides.
    output_index=args.index('-o')+1
    args[output_index]=str(a.output/'bb-probe-atlas2.exe')
    args=[('-Wl,--out-implib,'+str(a.output/'libbb-probe-atlas2.dll.a')) if s.startswith('-Wl,--out-implib,') else s for s in args]
    insertion=next(i for i,s in enumerate(args) if s=='libbbgpu.a')
    args[insertion:insertion]=objects
    # Linker threading is capped, as offline compilation shares this host with GPU work.
    args.insert(1,'-Wl,--threads=1')
    args=[s.replace('\\','/') for s in args]
    (a.output/'link-arguments.json').write_text(json.dumps(args,indent=2))
    # A private response file also avoids Windows command-line length limits.
    rsp=a.output/'atlas2-link.rsp';rsp.write_text(subprocess.list2cmdline(args[1:]))
    with (a.output/'link.log').open('w') as log:subprocess.run([args[0],'@'+str(rsp)],cwd=a.baseline_build,env=env,stdout=log,stderr=log,check=True)
    result=dict(schema=1,reference_runtime_sha256=sha(pinned),retained_baseline_text_sha256=text_section(pinned),experimental_runtime_sha256=sha(a.output/'bb-probe-atlas2.exe'),baseline_sources_sha256=baseline_sha,renderer_workers=0,compiler_processes=1,linker_threads=1,native_game_launched=False)
    (a.output/'build-evidence.json').write_text(json.dumps(result,indent=2))
    print('ATLAS2_NATIVE_BUILD_READY',flush=True)
if __name__=='__main__':main()
