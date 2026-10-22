// SPDX-License-Identifier: GPL-2.0-or-later
#include "resolution_gpu.h"
#include "bbport_atlas_style.h"
#include "C:/Users/MichaelPC/Documents/Codex/2026-10-18/task-12/atlas2/source/native/src/runtime_map.h"
#include <thread>
VkQueryPool vector_queries{};bool capture_pixels=false;int atlas_flag_mode=-1;
extern "C" int runtime_map_menu_open(){return 0;}
extern "C" int runtime_map_location(BbMapLocation* out){*out={18.8834972f,-9.5071011f,103.8061447f,1.6026251f,0x18000000u,1};return 1;}
void VectorFrame(){BbMap::Draw();}
int main(int argc,char**argv){try{
 Check(argc==6,"usage font width height output trace");GPU::W=std::stoul(argv[2]);GPU::H=std::stoul(argv[3]);
 GPU gpu;gpu.Init(256);auto* font=ImGui::GetIO().Fonts->AddFontFromFileTTF(argv[1],48);Check(font,"font");BbMap::SetTitleFont(font);Check(BbMapArt::Init(),"art");BbMap::Init();BbMap::OpenFromMenu();
 VkQueryPoolCreateInfo qi{VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO};qi.queryType=VK_QUERY_TYPE_TIMESTAMP;qi.queryCount=2;Vk(vkCreateQueryPool(gpu.device,&qi,nullptr,&vector_queries));
 auto Frame=[&](){gpu.Frame(0,false);BbMap::PollTestCommands();Check(BbMapStatic::Stats()["integrity_failures"]==0,"pack integrity");};
 auto Warm=[&](){for(int i=0;i<15000;++i){Frame();auto s=BbMapStatic::Stats();if(s.value("area_loaded",false)&&s.value("hatch_lod",-1)==s.value("lod",-2)&&s.value("draw_calls",0)>0)return;std::this_thread::sleep_for(std::chrono::milliseconds(1));}throw std::runtime_error("load timeout");};
 auto Trace=[&](){std::this_thread::sleep_for(std::chrono::milliseconds(110));BbMap::PollTestCommands();return ReadJson(std::string(argv[5])+".atlas2.json");};
 Warm();auto before=Trace();float scale=before["render"]["ui_scale"],zoom=before["zoom"];
 Check(std::abs(zoom/scale-9)<.001f,"opening world coverage");
 auto canvas=BbAtlasStyle::Layout(GPU::W,GPU::H).Canvas();Check(canvas.x>=0&&canvas.y>=0&&canvas.x+canvas.w<=GPU::W&&canvas.y+canvas.h<=GPU::H,"canvas clips screen");
 // A wheel tick at 4K must zoom in from 27, not hit the old fixed 25 cap.
 ImGui::GetIO().AddMousePosEvent(canvas.x+canvas.w*.5f,canvas.y+canvas.h*.5f);Frame();Frame();
 ImGui::GetIO().AddMouseWheelEvent(0,1);Frame();auto wheel=Trace();Check(wheel["zoom"].get<float>()>zoom,"wheel zoom failed at scaled resolution");
 // A live size change must preserve map world coverage and normalized zoom.
 float normalized=wheel["zoom"].get<float>()/scale;
 ImGui::GetIO().DisplaySize={float(GPU::W)*.75f,float(GPU::H)*.75f};Warm();auto resized=Trace();
 Check(std::abs(resized["zoom"].get<float>()/resized["render"]["ui_scale"].get<float>()-normalized)<.002f,"resize changed world coverage");
 ImGui::GetIO().DisplaySize={float(GPU::W),float(GPU::H)};Warm();auto restored=Trace();Check(std::abs(restored["zoom"].get<float>()/scale-normalized)<.002f,"resize restoration");
 auto uploads=BbMapStatic::Stats()["gpu_upload_batches_total"];for(int i=0;i<10;++i)Frame();Check(BbMapStatic::Stats()["gpu_upload_batches_total"]==uploads,"per-frame upload");
 // Read back one full native frame to establish actual visible map output. No image saved.
 capture_pixels=true;auto pixels=gpu.Frame(0,false);capture_pixels=false;size_t lit=0;for(size_t i=0;i<pixels.size();i+=4)if(pixels[i]+pixels[i+1]+pixels[i+2]>60)++lit;Check(lit>GPU::W*GPU::H/4,"empty output");
 vkDestroyQueryPool(gpu.device,vector_queries,nullptr);std::vector<std::unique_ptr<ImTextureData>> art;gpu.Cleanup(art);Check(errors==0&&images_created==images_destroyed,"GPU lifetime");
 WriteJson(argv[4],{{"pass",true},{"resolution",{GPU::W,GPU::H}},{"ui_scale",scale},{"canvas",{canvas.x,canvas.y,canvas.w,canvas.h}},{"initial_zoom",zoom},{"wheel_zoom",wheel["zoom"]},{"resized_zoom",resized["zoom"]},{"world_coverage_preserved",true},{"visible_pixels",lit},{"spoiler_images_saved",false}});return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
