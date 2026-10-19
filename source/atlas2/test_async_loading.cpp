#define main LegacyCacheMain
#include "test_cache.cpp"
#undef main
#include <chrono>
#include <thread>
int main(int argc,char**argv){try{
 Check(argc==3,"async test pack report");fs::path root=fs::absolute(argv[1]);_putenv_s("BB_ATLAS2_ENABLED","1");_putenv_s("BB_ATLAS2_ASYNC_LOAD","1");_putenv_s("BB_ATLAS2_DIR",root.string().c_str());_putenv_s("BB_ATLAS2_INDEX_SHA256",Hash(Read(root/"atlas2-index.json")).c_str());
 ImGui::CreateContext();auto&io=ImGui::GetIO();io.DisplaySize={1920,1080};io.DeltaTime=1.f/60;io.IniFilename=nullptr;io.BackendFlags|=ImGuiBackendFlags_RendererHasTextures;io.Fonts->AddFontDefault();flags.assign(256,true);fog=true;
 auto index=ReadJson(root/"atlas2-index.json");Json rows=Json::array();double max_call=0;int max_jobs=0;
 auto load=[&](std::string region){auto stop=std::chrono::steady_clock::now()+std::chrono::seconds(30);int polls=0;for(;;){auto t=std::chrono::steady_clock::now();bool ok=BbMapStatic::Load(region);max_call=std::max(max_call,std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count());auto s=BbMapStatic::Stats();int jobs=s["loader_jobs"];max_jobs=std::max(max_jobs,jobs);Check(jobs<=1,"concurrent loader jobs");if(ok)return polls;Check(std::chrono::steady_clock::now()<stop,"async area timeout");++polls;std::this_thread::sleep_for(std::chrono::milliseconds(1));}};
 auto draw=[&](std::string region,int layer,float x,float z){ImGui::NewFrame();auto t=std::chrono::steady_clock::now();BbMapStatic::Draw(ImGui::GetBackgroundDrawList(),region,layer,{960,540},{1253,807},x,z,13.5f,1,true,1.5f);max_call=std::max(max_call,std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count());ImGui::Render();Backend();auto s=BbMapStatic::Stats();int jobs=s["loader_jobs"];max_jobs=std::max(max_jobs,jobs);Check(jobs<=1&&s["resident_slots"]<=64&&s["uploads_this_frame"]<=4&&s["prepared_external_views"]<=1,"async bounds");return s;};
 // A stale area completion must never become a successful load for a new region.
 std::string first=index["areas"][0]["region_id"],second=index["areas"][1]["region_id"];Check(!BbMapStatic::Load(first),"async load blocked until complete");load(second);Check(BbMapStatic::Stats()["loader_stale_results"]>=1,"stale area not discarded");
 for(const auto&e:index["areas"]){std::string region=e["region_id"];int polls=load(region);auto m=ReadJson(root/e["area"].get<std::string>()/"manifest.json");float x=(m["bounds"][0].get<float>()+m["bounds"][2].get<float>())/2,z=(m["bounds"][1].get<float>()+m["bounds"][3].get<float>())/2;int a=0,b=int(m["views"].size())-1;draw(region,a,x,z);auto stop=std::chrono::steady_clock::now()+std::chrono::seconds(30);Json s;
  // Switch request while the first view job is pending; the returned view must match b.
  do{s=draw(region,b,x,z);Check(std::chrono::steady_clock::now()<stop,"async view timeout");std::this_thread::sleep_for(std::chrono::milliseconds(1));}while(s["loaded_detail_layer"]!=b||s["backend_ready_tiles"]!=s["visible_tiles"]||s["uploads_this_frame"]!=0);
  Check(s["integrity_failures"]==0&&s["prepared_external_views"]==1,"async view failed");rows.push_back({{"area",e["area"]},{"polls",polls},{"stats",s}});
 }
 // Exit with an in-flight load: join it before runtime globals/context are destroyed.
 BbMapStatic::Load(first);for(auto*t:ImGui::GetPlatformIO().Textures){t->SetTexID(ImTextureID_Invalid);t->BackendUserData=nullptr;}BbMapStatic::Shutdown();Check(BbMapStatic::Stats()["loader_jobs"]==0,"shutdown worker still owned");ImGui::DestroyContext();WriteJson(argv[2],{{"schema",1},{"pass",true},{"backend","CPU fake; no GPU"},{"areas",rows.size()},{"max_loader_jobs",max_jobs},{"max_caller_ms",max_call},{"samples",rows}});std::cout<<"ASYNC_LOADING_PASS areas="<<rows.size()<<" jobs="<<max_jobs<<" max_caller_ms="<<max_call<<"\n";return 0;
 }catch(const std::exception&e){std::cout<<"ASYNC_LOADING_FAIL "<<e.what()<<"\n";return 1;}}
