from pathlib import Path
import os,subprocess,json,struct,hashlib
R=Path(r'C:\Users\MichaelPC\Documents\Codex\2026-10-18\task-12\atlas2');W=R/'.local/atlas2'
S=Path(__file__).parent;B=S/'compact-build';B.mkdir(exist_ok=True)
TC=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\.local\native-toolchain\msys64\clang64\bin')
BASE=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\.local\release-1.2-v19-20261017\forced-rebuild19-r2\rebuild\build')
env=dict(os.environ,PATH=str(TC)+os.pathsep+os.environ.get('PATH',''))
def run(args,name,cwd=None):
 with (B/(name+'.log')).open('w') as f:subprocess.run(list(map(str,args)),cwd=cwd,env=env,stdout=f,stderr=f,check=True)
common=[TC/'clang++.exe','-std=c++23','-O2','-DNDEBUG','-DNOMINMAX','-Wl,--threads=1','-I'+str(R/'source/atlas2'),'-I'+str(R/'source/native/gpu/third_party/imgui'),'-I'+str(R/'source/native/gpu/third_party/imgui/backends'),'-I'+str(R/'source/native/gpu/shim')]
run([TC/'glslc.exe',S/'vector.vert','-o',B/'vector.spv'],'shader')
raw=(B/'vector.spv').read_bytes();words=struct.unpack('<%dI'%(len(raw)//4),raw)
(B/'vector_shader.h').write_text('static const uint32_t atlas_vector_shader[] = {'+','.join(map(str,words))+'};\n')
if not (B/'bake-vectors.exe').exists() or (B/'bake-vectors.exe').stat().st_mtime<(S/'bake_vectors.cpp').stat().st_mtime:
 run(common+[S/'bake_vectors.cpp','-lz','-lcrypto','-o',B/'bake-vectors.exe'],'baker')
print('COMPACT_OFFLINE_COMPILER_READY',flush=True)
if (S/'map_vector.cpp').exists():
 backend=(R/'source/native/gpu/third_party/imgui/backends/imgui_impl_vulkan.cpp').read_text()
 export=r'''
#include "SHADER_HEADER"
static VkPipeline atlas_pipeline=VK_NULL_HANDLE;
static VkPipelineLayout atlas_layout=VK_NULL_HANDLE;
extern void BbAtlasVectorReleaseGpu();
extern "C" bool BbAtlasVectorBackend(VkDevice* device,VkPhysicalDevice* physical,VkDescriptorSet* sampler,VkPipelineLayout* layout,VkPipeline* pipeline){
 auto* bd=ImGui_ImplVulkan_GetBackendData();if(!bd)return false;auto* v=&bd->VulkanInitInfo;
 *device=v->Device;*physical=v->PhysicalDevice;*sampler=bd->SamplerLinearDS;
 if(!atlas_pipeline){
  VkPushConstantRange range{VK_SHADER_STAGE_VERTEX_BIT,0,64};VkDescriptorSetLayout sets[]={bd->DescriptorSetLayoutTexture,bd->DescriptorSetLayoutSampler};
  VkPipelineLayoutCreateInfo ci{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};ci.setLayoutCount=2;ci.pSetLayouts=sets;ci.pushConstantRangeCount=1;ci.pPushConstantRanges=&range;
  if(vkCreatePipelineLayout(v->Device,&ci,v->Allocator,&atlas_layout)!=VK_SUCCESS)return false;
  VkShaderModuleCreateInfo si{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};si.codeSize=sizeof(atlas_vector_shader);si.pCode=atlas_vector_shader;VkShaderModule module;
  if(vkCreateShaderModule(v->Device,&si,v->Allocator,&module)!=VK_SUCCESS){vkDestroyPipelineLayout(v->Device,atlas_layout,v->Allocator);atlas_layout={};return false;}
  auto old_module=bd->ShaderModuleVert;auto old_layout=bd->PipelineLayout;bd->ShaderModuleVert=module;bd->PipelineLayout=atlas_layout;
  atlas_pipeline=ImGui_ImplVulkan_CreatePipeline(v->Device,v->Allocator,v->PipelineCache,&v->PipelineInfoMain);
  bd->ShaderModuleVert=old_module;bd->PipelineLayout=old_layout;vkDestroyShaderModule(v->Device,module,v->Allocator);
 }
 *layout=atlas_layout;*pipeline=atlas_pipeline;return atlas_pipeline!=VK_NULL_HANDLE;
}
'''.replace('SHADER_HEADER',(B/'vector_shader.h').as_posix())
 anchor='static void ImGui_ImplVulkan_CreateDescriptorSetLayout('
 assert backend.count(anchor)==1
 backend=backend.replace(anchor,export+'\n'+anchor)
 anchor='    ImGui_ImplVulkan_DestroyDeviceObjects();\n\n    io.BackendRendererName'
 assert backend.count(anchor)==1
 backend=backend.replace(anchor,'    BbAtlasVectorReleaseGpu();\n    if(atlas_pipeline)vkDestroyPipeline(bd->VulkanInitInfo.Device,atlas_pipeline,bd->VulkanInitInfo.Allocator);\n    if(atlas_layout)vkDestroyPipelineLayout(bd->VulkanInitInfo.Device,atlas_layout,bd->VulkanInitInfo.Allocator);\n    atlas_pipeline=VK_NULL_HANDLE;atlas_layout=VK_NULL_HANDLE;\n    ImGui_ImplVulkan_DestroyDeviceObjects();\n\n    io.BackendRendererName')
 (B/'vector_backend.cpp').write_text(backend)
 for name,source in [('bbport_map_static.cpp',S/'map_vector.cpp'),('imgui_impl_vulkan.cpp',B/'vector_backend.cpp')]:
  run(common+['-DIMGUI_IMPL_VULKAN_NO_PROTOTYPES' if name.startswith('imgui') else '-DATLAS_VECTOR_BUILD','-c',source,'-o',B/(name+'.obj')],name)
 args=json.loads((W/'async-build/link-arguments.json').read_text());args[0]=str(TC/'clang++.exe')
 for name in ('bbport_map_static.cpp','imgui_impl_vulkan.cpp'):args=[str(B/(name+'.obj')) if x.replace('\\','/').endswith('/'+name+'.obj') else x for x in args]
 args[args.index('-o')+1]=str(B/'bb-probe-compact.exe')
 args=[x.replace('\\','/') for x in args]
 args.append('-lvulkan-1')
 rsp=B/'link.rsp';rsp.write_text(subprocess.list2cmdline(args[1:]));run([args[0],'@'+str(rsp)],'link',BASE)
 (B/'native-build.json').write_text(json.dumps(dict(runtime_sha256=hashlib.sha256((B/'bb-probe-compact.exe').read_bytes()).hexdigest(),sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (S/'map_vector.cpp',S/'bake_vectors.cpp',S/'vector.vert',B/'vector_backend.cpp')}),indent=2))
 print('COMPACT_NATIVE_BUILT',flush=True)
