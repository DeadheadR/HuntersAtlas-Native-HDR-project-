from pathlib import Path
import subprocess,os,json
S=Path(__file__).parent; B=S/'compact-build'
R=Path(r'C:\Users\MichaelPC\Documents\Codex\2026-10-18\task-12\atlas2'); W=R/'.local/atlas2'
TC=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\.local\native-toolchain\msys64\clang64\bin')
BASE=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\.local\release-1.2-v19-20261017\forced-rebuild19-r2\rebuild\build')
source=(R/'source/native/gpu/shim/bbport_map.cpp').read_text()
source=source.replace('float cx=0,cz=0,zoom=3.0f,padx=0,pady=0;','float cx=0,cz=0,zoom=3.0f,padx=0,pady=0;\nfloat zoom_ui_scale=0;')
source=source.replace(')),0.15f,25.0f);',')),0.15f*MapUiScale(),25.0f*MapUiScale());\n    zoom_ui_scale=MapUiScale();')
source=source.replace('selected=current;follow=true;zoom=9.0f*MapUiScale();','selected=current;follow=true;zoom=9.0f*MapUiScale();zoom_ui_scale=MapUiScale();')
source=source.replace('    if(!open)return;\n    runtime_map_location', '    if(!open)return;\n    const float current_ui_scale=MapUiScale();\n    if(zoom_ui_scale>0)zoom*=current_ui_scale/zoom_ui_scale;\n    zoom_ui_scale=current_ui_scale;\n    runtime_map_location')
source=source.replace('ImGui::GetIO().MouseWheel),.15f,25.0f);','ImGui::GetIO().MouseWheel),.15f*scale,25.0f*scale);')
assert 'current_ui_scale/zoom_ui_scale' in source
assert 'MouseWheel),.15f*scale,25.0f*scale)' in source
(S/'bbport_map.cpp').write_text(source)
header=(B/'compact_gpu.h').read_text().replace('static constexpr int W=3840,H=2160;','inline static uint32_t W=3840,H=2160;')
header=header.replace('io.DisplaySize={W,H}', 'io.DisplaySize={float(W),float(H)}').replace('draw->PushClipRect({0,0},{W,H})','draw->PushClipRect({0,0},{float(W),float(H)})')
(B/'resolution_gpu.h').write_text(header)
env=dict(os.environ,PATH=str(TC)+os.pathsep+os.environ.get('PATH',''))
common=[str(TC/'clang++.exe'),'-std=c++23','-O2','-DNDEBUG','-DNOMINMAX','-Wl,--threads=1','-I'+str(R/'source/atlas2'),'-I'+str(R/'source/native/gpu/third_party/imgui'),'-I'+str(R/'source/native/gpu/third_party/imgui/backends'),'-I'+str(R/'source/native/gpu/shim'),'-I'+str(B)]
def run(args,name):
 with (B/(name+'.log')).open('w') as f:subprocess.run(list(map(str,args)),env=env,cwd=BASE,stdout=f,stderr=f,check=True)
run(common+['-c',S/'bbport_map.cpp','-o',B/'bbport_map.cpp.obj'],'responsive-map')
args=common+[S/'check_resolution.cpp',B/'check_stubs.cpp',B/'bbport_map.cpp.obj']
args += [W/'async-build'/(n+'.obj') for n in ('bbport_map_art.cpp','bbport_map_features.cpp')]
args += [B/(n+'.obj') for n in ('bbport_map_static.cpp','imgui_impl_vulkan.cpp')]
run(args+[BASE/'libbbgpu.a','-lSDL3','-lz','-lcrypto','-lvulkan-1','-o',B/'check-resolution.exe'],'resolution-link')
args=json.loads((W/'async-build/link-arguments.json').read_text());args[0]=str(TC/'clang++.exe')
for name in ('bbport_map.cpp','bbport_map_static.cpp','imgui_impl_vulkan.cpp'):args=[str(B/(name+'.obj')) if x.replace('\\','/').endswith('/'+name+'.obj') else x for x in args]
args[args.index('-o')+1]=str(B/'bb-probe-responsive.exe');args=[x.replace('\\','/') for x in args];args.append('-lvulkan-1')
rsp=B/'responsive-link.rsp';rsp.write_text(subprocess.list2cmdline(args[1:]));run([args[0],'@'+str(rsp)],'responsive-link')
print('RESPONSIVE_RUNTIME_AND_CHECK_BUILT',flush=True)
