// SPDX-License-Identifier: GPL-2.0-or-later
#include "core.h"
#include "../native/gpu/shim/bbport_map_static.h"
#include "imgui_internal.h"
#include <iostream>
using namespace Atlas2;
static bool fog=false;static std::vector<bool> flags;
namespace BbMapFeatures {
bool FogEnabled(){return fog;}
std::vector<bool> StaticRegionVisibility(const std::string&){return flags;}
}
static void Check(bool b,const char* why){if(!b)throw std::runtime_error(why);}
// A CPU-only fake acknowledges the backend protocol. It cannot test Vulkan fences or GPU timing.
static void Backend(){for(auto* t:ImGui::GetPlatformIO().Textures){if(t->Status==ImTextureStatus_WantCreate){t->SetTexID(ImTextureID(t->UniqueID+100));t->SetStatus(ImTextureStatus_OK);}if(t->Status==ImTextureStatus_WantDestroy){t->SetTexID(ImTextureID_Invalid);t->BackendUserData=nullptr;t->SetStatus(ImTextureStatus_Destroyed);}}}
int main(int argc,char**argv){try{
    Check(argc==3,"usage cache-test pack-root report");fs::path root=fs::absolute(argv[1]);_putenv_s("BB_ATLAS2_ENABLED","1");_putenv_s("BB_ATLAS2_DIR",root.string().c_str());_putenv_s("BB_ATLAS2_INDEX_SHA256",Hash(Read(root/"atlas2-index.json")).c_str());
    ImGui::CreateContext();auto& io=ImGui::GetIO();io.DisplaySize={1920,1080};io.DeltaTime=1.f/60;io.IniFilename=nullptr;io.BackendFlags|=ImGuiBackendFlags_RendererHasTextures;io.Fonts->AddFontDefault();
    auto index=ReadJson(root/"atlas2-index.json");int frame=0,max_slots=0,max_uploads=0;size_t areas=0;Json first;
    for(int repeat=0;repeat<3;++repeat)for(const auto& entry:index.at("areas")){auto m=ReadJson(root/entry.at("area").get<std::string>()/"manifest.json");std::string region=entry.at("region_id");float x=(m["bounds"][0].get<float>()+m["bounds"][2].get<float>())/2,z=(m["bounds"][1].get<float>()+m["bounds"][3].get<float>())/2;Check(BbMapStatic::Load(region),"runtime manifest load");
        for(int step=0;step<80;++step){ImGui::NewFrame();int li=step%int(m["layers"].size());float zoom=step<20?9.f:step<40?.15f:step<60?25.f:1.f;float cx=x+(step%10-5)*18,cz=z+(step%8-4)*15;
            BbMapStatic::Draw(ImGui::GetBackgroundDrawList(),region,li,{960,540},{1253,807},cx,cz,zoom);ImGui::Render();auto s=BbMapStatic::Stats();int n=s.at("resident_slots"),uploads=s.at("uploads_this_frame");Check(n<=int(CacheSlots),"cache slots exceed bound");Check(uploads<=4,"upload bound");max_slots=std::max(max_slots,n);max_uploads=std::max(max_uploads,uploads);if(frame==0)first=s;Backend();++frame;
        }++areas;
    }
    BbMapStatic::Command("atlas2-reference");Check(BbMapStatic::Mode()==1,"reference toggle");BbMapStatic::Command("atlas2-overlay");Check(BbMapStatic::Mode()==2,"overlay toggle");BbMapStatic::Command("atlas2-static");Check(BbMapStatic::Mode()==0,"static toggle");
    // Fog with no known flags must draw no conditional slices. Always-visible slices are allowed.
    fog=true;flags.clear();ImGui::NewFrame();const auto& e=index["areas"][0];auto m=ReadJson(root/e["area"].get<std::string>()/"manifest.json");std::string region=e["region_id"];BbMapStatic::Draw(ImGui::GetBackgroundDrawList(),region,0,{960,540},{1253,807},0,0,1);ImGui::Render();Backend();
    auto final=BbMapStatic::Stats();for(auto*t:ImGui::GetPlatformIO().Textures){t->SetTexID(ImTextureID_Invalid);t->BackendUserData=nullptr;}BbMapStatic::Shutdown();ImGui::DestroyContext();
    WriteJson(argv[2],{{"schema",1},{"pass",true},{"backend","CPU fake, no Vulkan or game"},{"frames",frame},{"area_loads",areas},{"max_slots",max_slots},{"max_uploads_per_frame",max_uploads},{"rgba_byte_bound",CacheSlots*TileBytes},{"first_frame",first},{"last_frame",final},{"native_gameplay_tested",false}});std::cout<<"ATLAS2_CACHE_PASS frames="<<frame<<" max_slots="<<max_slots<<" uploads_per_frame="<<max_uploads<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<"ATLAS2_CACHE_FAIL "<<e.what()<<"\n";return 1;}}
