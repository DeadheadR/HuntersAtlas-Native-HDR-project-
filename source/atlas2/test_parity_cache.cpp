// SPDX-License-Identifier: GPL-2.0-or-later
#define main LegacyCacheMain
#include "test_cache.cpp"
#undef main
int main(int argc,char**argv){try{
    Check(argc==3||argc==4,"usage parity-cache pack-root report [expected-views]");fs::path root=fs::absolute(argv[1]);_putenv_s("BB_ATLAS2_ENABLED","1");_putenv_s("BB_ATLAS2_DIR",root.string().c_str());_putenv_s("BB_ATLAS2_INDEX_SHA256",Hash(Read(root/"atlas2-index.json")).c_str());
    ImGui::CreateContext();auto& io=ImGui::GetIO();io.DisplaySize={1920,1080};io.DeltaTime=1.f/60;io.IniFilename=nullptr;io.BackendFlags|=ImGuiBackendFlags_RendererHasTextures;io.Fonts->AddFontDefault();flags.assign(256,true);
    int frames=0,composites=0,max_slots=0,max_lines=0,max_uploads=0;Json samples=Json::array();
    auto index=ReadJson(root/"atlas2-index.json");for(const auto& e:index["areas"]){auto m=ReadJson(root/e["area"].get<std::string>()/"manifest.json");if(m["schema"]!=2&&m["schema"]!=3)continue;std::string region=e["region_id"];Check(BbMapStatic::Load(region),"schema2 manifest");float x=(m["bounds"][0].get<float>()+m["bounds"][2].get<float>())/2,z=(m["bounds"][1].get<float>()+m["bounds"][3].get<float>())/2;
        for(int layer=0;layer<int(m["views"].size());++layer){if(m["views"][layer].value("kind",std::string())!="composite"&&!m["views"][layer].contains("view_file"))continue;++composites;
            for(float zoom:{.225f,13.5f,37.5f})for(bool f:{false,true})for(bool shading:{false,true})for(int warm=0;warm<6;++warm){fog=f;ImGui::NewFrame();BbMapStatic::Draw(ImGui::GetBackgroundDrawList(),region,layer,{960,540},{1253,807},x,z,zoom,1,shading,1.5f);ImGui::Render();auto s=BbMapStatic::Stats();Check(s["composite"]==true&&s["detail_ppu"]==16,"selected composite transform");Check(s["integrity_failures"]==0,"parity integrity");int slots=s["resident_slots"],lines=s["line_candidates"],uploads=s["uploads_this_frame"];Check(slots<=64&&uploads<=4&&lines<=int(LineSegmentLimit),"bounded resources");max_slots=std::max(max_slots,slots);max_lines=std::max(max_lines,lines);max_uploads=std::max(max_uploads,uploads);Backend();++frames;}
            samples.push_back({{"area",e["area"]},{"layer",layer},{"stats",BbMapStatic::Stats()}});
            ImGui::NewFrame();BbMapStatic::Draw(ImGui::GetBackgroundDrawList(),region,layer,{960,540},{1253,807},1e30f,-1e30f,13.5f,1,true,1.5f);ImGui::Render();auto off=BbMapStatic::Stats();Check(off["visible_tiles"]==0&&off["lines_drawn"]==0,"offmap huge coordinates");Backend();
        }
    }
    Check(composites==(argc==4?std::stoi(argv[3]):14),"exact parity view coverage");for(auto*t:ImGui::GetPlatformIO().Textures){t->SetTexID(ImTextureID_Invalid);t->BackendUserData=nullptr;}BbMapStatic::Shutdown();ImGui::DestroyContext();
    WriteJson(argv[2],{{"pass",true},{"backend","CPU fake; not Vulkan"},{"composite_views",composites},{"frames",frames},{"max_slots",max_slots},{"max_uploads",max_uploads},{"max_line_candidates",max_lines},{"rgba_byte_bound",CacheSlots*TileBytes},{"samples",samples}});std::cout<<"PARITY_CACHE_PASS views="<<composites<<" frames="<<frames<<" slots="<<max_slots<<" uploads="<<max_uploads<<" lines="<<max_lines<<"\n";return 0;
}catch(const std::exception&e){std::cout<<"PARITY_CACHE_FAIL "<<e.what()<<"\n";return 1;}}
