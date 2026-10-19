#define main LegacyCacheMain
#include "test_cache.cpp"
#undef main
#include <chrono>
int main(int argc,char**argv){try{
 Check(argc==3,"cold profile pack report");fs::path root=fs::absolute(argv[1]);_putenv_s("BB_ATLAS2_ENABLED","1");_putenv_s("BB_ATLAS2_DIR",root.string().c_str());_putenv_s("BB_ATLAS2_INDEX_SHA256",Hash(Read(root/"atlas2-index.json")).c_str());
 ImGui::CreateContext();auto&io=ImGui::GetIO();io.DisplaySize={1920,1080};io.DeltaTime=1.f/60;io.IniFilename=nullptr;io.BackendFlags|=ImGuiBackendFlags_RendererHasTextures;io.Fonts->AddFontDefault();flags.assign(256,true);fog=true;
 auto index=ReadJson(root/"atlas2-index.json");Json result=Json::array();
 for(const auto&e:index["areas"]){if(e["area"]!="Area01"&&e["area"]!="Area06")continue;auto start=std::chrono::steady_clock::now();Check(BbMapStatic::Load(e["region_id"]),"load");double load=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();auto m=ReadJson(root/e["area"].get<std::string>()/"manifest.json");float x=e["area"]=="Area06"?-199.740005f:0,y=e["area"]=="Area06"?-50.758003f:0,z=e["area"]=="Area06"?179.419998f:0;int layer=BbMapStatic::StrictLayer(e["region_id"],x,y,z,true);ImGui::NewFrame();start=std::chrono::steady_clock::now();BbMapStatic::Draw(ImGui::GetBackgroundDrawList(),e["region_id"],layer,{960,540},{1253,807},x,z,13.5f,1,true,1.5f);double draw=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();ImGui::Render();Backend();result.push_back({{"area",e["area"]},{"load_ms",load},{"first_draw_ms",draw},{"stats",BbMapStatic::Stats()}});}
 for(auto*t:ImGui::GetPlatformIO().Textures){t->SetTexID(ImTextureID_Invalid);t->BackendUserData=nullptr;}BbMapStatic::Shutdown();ImGui::DestroyContext();WriteJson(argv[2],{{"schema",1},{"backend","CPU fake; no GPU"},{"results",result}});std::cout<<"COLD_PROFILE_COMPLETE\n";return 0;
 }catch(const std::exception&e){std::cout<<"COLD_PROFILE_FAIL "<<e.what()<<"\n";return 1;}}
