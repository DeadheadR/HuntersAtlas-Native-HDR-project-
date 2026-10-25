"""Apply the Atlas 3.1 integration to a pristine, pinned Lantern source tree.

The existing Windows 1.9 integration is never edited. Every upstream edit uses
an exact anchor, and the receipt records both sides of every changed file.
"""
from __future__ import annotations
import argparse, hashlib, json, re, shutil
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
PIN='d901fbd2ea4bea114b37c26a2a9278d1e97f7b46'
SOURCE_TREE_SHA256='96dc305bb14a0e2d47e0b52e3c1a4c7899e9d72be63a65fa3bf0fa37ebc848ad'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(text, old, new, *, count=1):
    if text.count(old)!=count: raise ValueError(f'Upstream anchor changed: {old[:100]!r}')
    return text.replace(old,new,count)

def prepare(upstream:Path, target:Path):
    if target.exists(): raise ValueError('Prepared source already exists; use a new build directory')
    tree=hashlib.sha256()
    for p in sorted(p for p in upstream.rglob('*') if p.is_file()):
        if p.is_symlink():raise ValueError('Upstream source symlink refused')
        tree.update((p.relative_to(upstream).as_posix()+'\0'+sha(p)+'\n').encode())
    if tree.hexdigest()!=SOURCE_TREE_SHA256:raise ValueError('Expected the pristine pinned Lantern v0.9.37 source archive')
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(upstream,target)
    receipt={'upstream_commit':PIN,'upstream_release':'v0.9.37','edits':{},'atlas_sources':{},'copies':{}}
    def edit(name, fn):
        p=target/name; before=sha(p)
        value=p.read_text(encoding='utf-8-sig'); value=fn(value)
        p.write_text(value,encoding='utf-8',newline='\n')
        receipt['edits'][name]={'before':before,'after':sha(p)}
    def copy(relative,destination):
        src=REPO/relative; dst=target/destination
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        receipt['atlas_sources'][relative]=sha(src)
        receipt['copies'][destination]={'source':relative,'sha256':sha(src)}

    # Guarded position/event-flag readers and existing game-thread travel bridge.
    for name in ('runtime_map.c','runtime_map.h','runtime_atlas_state.c','runtime_atlas_state.h',
                 'runtime_menu_sound.c','runtime_menu_sound.h','map_build_guard.inc','map_confirm_guard.inc',
                 'runtime_atlas_release.h'):
        copy('source/native/src/'+name,'engine/src/'+name)
    edit('engine/src/probe.c',lambda s:replace(replace(s,'#include "runtime.h"',
        '#include "runtime.h"\n#include "runtime_map.h"\n#include "runtime_atlas_state.h"'),
        '    if (!cpu_only) bbgpu_patch_image(image, size);',
        '    runtime_map_bind(image,size);\n    runtime_atlas_state_bind(image,size);\n'
        '    if (!cpu_only) bbgpu_patch_image(image, size);'))
    # Lantern already owns the verified game-thread frame hook. Join that callback
    # instead of overwriting it with the older Windows adapter's trampoline.
    def state(s):
        s=replace(s,'static int state_ready, travel_ready;','static int state_ready, travel_ready, travel_guarded;')
        s=replace(s,'static int64_t (ATLAS_ABI *original_frame)(void *);','')
        # Cold Lantern asset/shader preparation on HDD can outlast the older
        # adapter's one-minute loading timeout. Keep requests guarded, allow the
        # normal loading phase three minutes, and still require the target block.
        s=replace(s,'GetTickCount64()-request_time>60000','GetTickCount64()-request_time>180000')
        s=replace(s,'static int64_t ATLAS_ABI frame_bridge(void *self) {\n    game_tick();return original_frame(self);\n}',
            'void runtime_atlas_game_tick(void) { if(travel_guarded){travel_ready=1;game_tick();} }')
        begin=s.index('    unsigned char *trampoline=VirtualAlloc(')
        end=s.index('\n#else',begin)
        return s[:begin]+'    travel_guarded=1;puts("Atlas: native travel guards ready; using Lantern main game thread");'+s[end:]
    edit('engine/src/runtime_atlas_state.c',state)
    edit('engine/gpu/shim/engine/features.cpp',lambda s:replace(replace(s,
        'extern "C" int runtime_file_translate',
        'extern "C" void runtime_atlas_game_tick(void);\nextern "C" int runtime_file_translate'),
        '    TrophySync::Tick();','    TrophySync::Tick();\n    runtime_atlas_game_tick();'))
    edit('engine/gpu/bbgpu.h',lambda s:replace(s,'int bbgpu_overlay_captures_input(void);',
        'int bbgpu_overlay_captures_input(void);\nuint32_t bbgpu_atlas_route_pad(uint32_t,uint8_t,uint8_t,uint8_t,uint8_t);'))
    edit('engine/gpu/shim/bbgpu.cpp',lambda s:replace(s,
        'extern "C" int bbgpu_overlay_captures_input(void) {',
        'extern "C" uint32_t bbgpu_atlas_route_pad(uint32_t b,uint8_t lx,uint8_t ly,uint8_t rx,uint8_t ry) {\n'
        '    return BbOverlay::RoutePad(b,lx,ly,rx,ry);\n}\n\n'
        'extern "C" int bbgpu_overlay_captures_input(void) {'))
    def pad(s):
        s=replace(s,'#include "runtime.h"','#include "runtime.h"\n#include "runtime_atlas_release.h"')
        s=replace(s,'    if (bbgpu_overlay_captures_input()) return;',
            '    /* Atlas routes mapped host input before neutralizing the game state. */')
        s=replace(s,'static int hold_after_capture;','static BbAtlasRelease atlas_release;')
        s=replace(s,'    if (bbgpu_overlay_captures_input()) { hold_after_capture=1; return; }\n','')
        s=replace(s,'    if (hold_after_capture) {\n        if (d->buttons) { d->buttons=0; d->l2=d->r2=0; }\n        else hold_after_capture=0;\n    }\n','')
        s=replace(s,'    touch_ids(d);\n}',
            '    const uint32_t raw=d->buttons;\n'
            '    uint8_t axes_now[4]={d->left_x,d->left_y,d->right_x,d->right_y};\n'
            '    uint8_t triggers[2]={d->l2,d->r2};\n'
            '    const int before=bbgpu_overlay_captures_input();\n'
            '    d->buttons=bbgpu_atlas_route_pad(raw,d->left_x,d->left_y,d->right_x,d->right_y);\n'
            '    if(before || bbgpu_overlay_captures_input()){\n'
            '        bb_atlas_remember(&atlas_release,raw,axes_now,triggers);\n'
            '        d->buttons=0;d->left_x=d->left_y=d->right_x=d->right_y=128;d->l2=d->r2=0;d->touch_count=0;return;\n'
            '    }\n'
            '    bb_atlas_release_filter(&atlas_release,raw,&d->buttons,axes_now,triggers);\n'
            '    d->left_x=axes_now[0];d->left_y=axes_now[1];d->right_x=axes_now[2];d->right_y=axes_now[3];d->l2=triggers[0];d->r2=triggers[1];\n'
            '    touch_ids(d);\n}')
        return s
    edit('engine/src/runtime_pad.c',pad)
    def audio(s):
        old=(REPO/'source/native/src/runtime_audio.c').read_text()
        block=old[old.index('static pthread_mutex_t menu_load_lock'):old.index("/* SDL's 7.1->stereo")]
        mix=old[old.index('static float sat('):old.index('static void fold8(')]
        block=block.replace('pthread_mutex_t','HostMutex').replace('PTHREAD_MUTEX_INITIALIZER','HOST_MUTEX_INIT').replace('pthread_mutex_lock','host_lock').replace('pthread_mutex_unlock','host_unlock')
        mix=mix.replace('pthread_mutex_lock','host_lock').replace('pthread_mutex_unlock','host_unlock').replace('*master_gain','')
        s=replace(s,'#include "runtime.h"','#include "runtime.h"\n#include "runtime_menu_sound.h"\n#include <stdatomic.h>')
        s=replace(s,'static size_t buffers_out, ports_opened;','static size_t buffers_out, ports_opened;\n'+block+mix)
        return replace(s,'        if (p->dump) fwrite(converted,1,bytes,p->dump);','        menu_mix(converted,p);\n        if (p->dump) fwrite(converted,1,bytes,p->dump);')
    edit('engine/src/runtime_audio.c',audio)
    edit('engine/gpu/shim/bbport_overlay.h',lambda s:replace(s,'bool CapturesInput();',
        'bool CapturesInput();\nuint32_t RoutePad(uint32_t,uint8_t,uint8_t,uint8_t,uint8_t);'))
    def overlay(s):
        s=replace(s,'#include "bbport_overlay.h"',
            '#include "bbport_overlay.h"\n#include "bbport_map.h"\n#include "bbport_map_static.h"\n'
            '#include "bbport_atlas_menu.h"\n#include "bbport_atlas_paths.h"\n#include "bbport_map_art.h"\n'
            '#include "atlas2/texture_budget.h"\n#include <fstream>')
        s=replace(s,'    info.DescriptorPoolSize = 16;',
            '    info.DescriptorPoolSize = BbMapStatic::Enabled() ? Atlas2::RendererImageDescriptors : 16;')
        s=replace(s,'    initialized = true;',
            '    initialized = true;\n    BbMapArt::Init();\n    BbMap::Init();')
        # Preserve CJK, PC controls, prompts, timing, frame generation and every engine menu.
        s=replace(s,'    const VkFormat color_format = static_cast<VkFormat>(format);',
            '    const auto map_font=BbAtlasPath("BB_MAP_FONT");\n'
            '    if(!map_font.empty()) { if(auto* font=io.Fonts->AddFontFromFileTTF(map_font.string().c_str(),24.0f))BbMap::SetTitleFont(font); }\n'
            '    const VkFormat color_format = static_cast<VkFormat>(format);')
        s=replace(s,'    const bool is_open = menu_open;',
            '    BbAtlasMenu::Suppress(menu_open || prompt_active);\n'
            '    if(!prompt_active && BbAtlasMenu::HandleMouse(event))return true;\n'
            '    if(!prompt_active && BbMap::HandleEvent(event))return true;\n'
            '    const bool is_open = menu_open || BbMap::IsOpen();')
        s=replace(s,'            SetOpen(event.key.key == SDLK_INSERT ? !is_open : false);',
            '            if(BbMap::IsOpen())BbMap::Close();\n'
            '            SetOpen(event.key.key == SDLK_INSERT ? !menu_open : false);')
        s=replace(s,'            SetOpen(!is_open);',
            '            if(BbMap::IsOpen())BbMap::Close();\n            SetOpen(!menu_open);')
        s=replace(s,'(menu_open || prompt_active || BbSettings::Get().show_fps || CompileNoteActive())',
            '(menu_open || prompt_active || BbMap::IsOpen() || BbAtlasMenu::Visible() || BbSettings::Get().show_fps || CompileNoteActive())')
        s=replace(s,'    return menu_open || prompt_active;',
            '    return menu_open || prompt_active || BbMap::CapturesInput();')
        s=replace(s,'void Render(vk::CommandBuffer cmdbuf, vk::ImageView view, vk::Extent2D extent) {',
            'uint32_t RoutePad(uint32_t b,uint8_t lx,uint8_t ly,uint8_t rx,uint8_t ry) {\n'
            '    std::scoped_lock lock{imgui_mutex};\n'
            '    if(!initialized || menu_open || prompt_active)return b;\n'
            '    return BbAtlasMenu::RoutePad(b,lx,ly,rx,ry);\n}\n\n'
            'void Render(vk::CommandBuffer cmdbuf, vk::ImageView view, vk::Extent2D extent) {\n'
            '    static const char* qa_exit=std::getenv("BB_ATLAS_EXIT_TRIGGER");\n'
            '    if(qa_exit && std::getenv("BB_ATLAS_QA") && std::remove(qa_exit)==0){SDL_Event quit{};quit.type=SDL_EVENT_QUIT;SDL_PushEvent(&quit);}\n'
            '    {std::scoped_lock lock{imgui_mutex};BbMap::PollTestCommands();BbMap::Tick();BbAtlasMenu::Suppress(menu_open||prompt_active);BbAtlasMenu::Tick();}')
        s=replace(s,'    ImGui::NewFrame();\n',
            '    ImGui::NewFrame();\n'
            '    if(menu_open && BbMap::IsOpen())BbMap::Close();\n'
            '    if(BbMap::IsOpen())BbMap::Draw();\n'
            '    else if(!menu_open && !prompt_active)BbAtlasMenu::Draw();\n'
            '    io.MouseDrawCursor=menu_open || BbMap::IsOpen() || BbAtlasMenu::Interacting();\n')
        s=replace(s,'    if (BbSettings::Get().show_fps && !menu_open) {',
            '    if (BbSettings::Get().show_fps && !menu_open && !BbMap::IsOpen()) {')
        s=replace(s,'    if (!menu_open && CompileNoteActive()) {',
            '    if (!menu_open && !BbMap::IsOpen() && CompileNoteActive()) {')
        return s
    edit('engine/gpu/shim/bbport_overlay.cpp',overlay)
    presenter='engine/gpu/shadps4/video_core/renderer_vulkan/'
    signature='void DumpFinalFrameIfDue(const Instance& instance, Scheduler& scheduler, vk::CommandBuffer cmdbuf,'
    edit(presenter+'vk_temporal_upscaler.h',lambda s:replace(s,signature,
        'void DumpAtlasUiFrameIfDue(const Instance&, Scheduler&, vk::CommandBuffer, vk::Image, u32, u32, vk::Format);\n'+signature))
    edit(presenter+'vk_temporal_upscaler.cpp',lambda s:replace(s,signature,
        (REPO/'source/launchers/atlas_ui_readback.inc').read_text()+'\n'+signature))
    edit(presenter+'vk_presenter.cpp',lambda s:replace(s,'    // Flush vulkan commands.',
        '    DumpAtlasUiFrameIfDue(instance,scheduler,cmdbuf,swapchain_image,swapchain.GetExtent().width,swapchain.GetExtent().height,swapchain.GetSurfaceFormat().format);\n\n    // Flush vulkan commands.'))
    # Extend the CURRENT ImGui backend, rather than replacing it with an old copy.
    def backend(s):
        atlas=(REPO/'source/compact/vector_backend.cpp').read_text()
        start=atlas.index('#include "vector_shader.h"')
        end=atlas.index('static void ImGui_ImplVulkan_CreateDescriptorSetLayout',start)
        s=replace(s,'static void ImGui_ImplVulkan_CreateDescriptorSetLayout',atlas[start:end]+'static void ImGui_ImplVulkan_CreateDescriptorSetLayout')
        anchor='    ImGui_ImplVulkan_DestroyDeviceObjects();'
        s=replace(s,anchor,
            '    BbAtlasVectorReleaseGpu();\n'
            '    if(atlas_pipeline)vkDestroyPipeline(bd->VulkanInitInfo.Device,atlas_pipeline,bd->VulkanInitInfo.Allocator);\n'
            '    if(atlas_layout)vkDestroyPipelineLayout(bd->VulkanInitInfo.Device,atlas_layout,bd->VulkanInitInfo.Allocator);\n'
            '    atlas_pipeline=VK_NULL_HANDLE;atlas_layout=VK_NULL_HANDLE;\n'+anchor)
        return s
    edit('engine/gpu/third_party/imgui/backends/imgui_impl_vulkan.cpp',backend)
    cmake='''
# Hunter's Atlas 3.1 integration, based on Lantern Engine v0.9.37.
if(NOT ATLAS_SOURCE_ROOT)
  message(FATAL_ERROR "ATLAS_SOURCE_ROOT is required for this modified runtime")
endif()
target_sources(bbgpu PRIVATE
  "${ATLAS_SOURCE_ROOT}/source/compact/bbport_map.cpp"
  "${ATLAS_SOURCE_ROOT}/source/compact/map_vector.cpp"
  "${ATLAS_SOURCE_ROOT}/source/native/gpu/shim/bbport_map_art.cpp"
  "${ATLAS_SOURCE_ROOT}/source/native/gpu/shim/bbport_map_controller.cpp"
  "${ATLAS_SOURCE_ROOT}/source/native/gpu/shim/bbport_map_features.cpp"
  "${ATLAS_SOURCE_ROOT}/source/native/gpu/shim/bbport_atlas_menu.cpp")
set_source_files_properties("${ATLAS_SOURCE_ROOT}/source/compact/map_vector.cpp"
  PROPERTIES COMPILE_DEFINITIONS ATLAS_VECTOR_BUILD
  COMPILE_OPTIONS "-UVK_NO_PROTOTYPES;-UIMGUI_IMPL_VULKAN_NO_PROTOTYPES")
target_include_directories(bbgpu PRIVATE
  "${ATLAS_SOURCE_ROOT}/source/compact" "${ATLAS_SOURCE_ROOT}/source/atlas2"
  "${ATLAS_SOURCE_ROOT}/source/native/gpu/shim" "${ATLAS_SOURCE_ROOT}/source")
target_link_libraries(bbgpu PRIVATE z crypto Vulkan::Vulkan)
'''
    edit('engine/gpu/CMakeLists.txt',lambda s:replace(s,'project(bbgpu LANGUAGES C CXX)',
        'project(bbgpu LANGUAGES C CXX)\n'
        'add_compile_options("-include${ATLAS_SOURCE_ROOT}/source/launchers/clang_compat.h")')+cmake)
    edit('engine/gpu/third_party/sirit/src/stream.h',lambda s:replace(s,
        '#include <bit>','#include <bit>\n#include <cstdlib>'))
    # The offline shader-cache compiler does not load a game or use Atlas state.
    edit('engine/tests/test_gpu_runtime_stubs.cpp',lambda s:s+'''
#include "../src/runtime_map.h"
#include "../src/runtime_atlas_state.h"
#include "../src/runtime_menu_sound.h"
extern "C" {
int runtime_map_location(BbMapLocation *out) { if(out)*out={};return 0; }
int runtime_map_menu_open() { return 0; }
int runtime_map_menu_state(BbMapMenu *out) { if(out)*out={};return 0; }
uint32_t runtime_map_confirm_button() { return 0x4000; }
int runtime_atlas_flag(uint32_t) { return -1; }
uintptr_t runtime_atlas_player_token() { return 0; }
int runtime_atlas_travel_request(const BbAtlasTravelDestination*) { return 0; }
int runtime_atlas_travel_status() { return 0; }
int runtime_atlas_travel_supported() { return 0; }
void runtime_audio_menu_event(int) {}
void runtime_atlas_game_tick() {}
void runtime_audio_menu_stats(BbMenuSoundStats *out) { if(out)*out={}; }
}
''')
    def build_script(s):
        s=replace(s,'gpu_config=(-G Ninja ',
            'gpu_config=("-DATLAS_SOURCE_ROOT=${ATLAS_SOURCE_ROOT:?Atlas source root is required}" -G Ninja ')
        s=replace(s,'if [[ -n $windows && -f out/bb-probe.exe',
            'if [[ ${BB_ATLAS_FORCE_BUILD:-0} != 1 && -n $windows && -f out/bb-probe.exe')
        return replace(s,'if [[ -n $windows ]] && [[ ! -f out/bb-start.exe',
            'if [[ -n $windows ]] && [[ ${BB_ATLAS_FORCE_BUILD:-0} == 1 || ! -f out/bb-start.exe')
    edit('engine/build.sh',build_script)
    # Keep licensing attribution, while clearly distinguishing the modified binary.
    edit('engine/src/lantern.rc',lambda s:s.replace('Lantern Engine','Hunter\'s Atlas (based on Lantern Engine)'))
    copy('source/lite/integration/bloodborne.ico','engine/src/lantern.ico')
    (target/'ATLAS-INTEGRATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.upstream.resolve(),a.output.resolve()),indent=2))
