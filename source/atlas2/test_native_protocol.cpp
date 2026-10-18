// SPDX-License-Identifier: GPL-2.0-or-later
#define main RetainedUiMain
#include "../native/tests/test_navigation_map.cpp"
#undef main
#include <filesystem>
int main(int argc,char**argv){
    assert(argc==2);const std::filesystem::path root=argv[1];std::filesystem::create_directories(root);
    const auto control=root/"control.txt",trace=root/"trace.json";_putenv_s("BB_MAP_TEST_CONTROL",control.string().c_str());_putenv_s("BB_MAP_TEST_TRACE",trace.string().c_str());_putenv_s("BB_ATLAS_QA","1");
    _putenv_s("BB_ATLAS2_MEASURE","1");
    ImGui::CreateContext();auto&io=ImGui::GetIO();io.DisplaySize={1920,1080};io.DeltaTime=1.f/60;io.IniFilename=nullptr;io.Fonts->AddFontDefault();unsigned char*p;int w,h;io.Fonts->GetTexDataAsRGBA32(&p,&w,&h);io.BackendFlags|=ImGuiBackendFlags_RendererHasVtxOffset;
    BbMap::Init();auto send=[&](const char* text){std::ofstream(control)<<text;SDL_Delay(110);BbMap::PollTestCommands();};auto read=[&](){std::ifstream f(trace.string()+".atlas2.json");nlohmann::json j;f>>j;return j;};
    send("atlas2-request 1000 open");auto first=read();assert(first["schema"]==2&&first["ack"]["id"]==1000&&BbMap::IsOpen());
    send("atlas2-request 1000 close");auto duplicate=read();assert(BbMap::IsOpen()&&duplicate["ack"]["command"]=="open"&&duplicate["sequence"]>first["sequence"]);
    frame();send("atlas2-request 1001 atlas2-static");frame();SDL_Delay(110);BbMap::PollTestCommands();auto rendered=read();assert(rendered["render"]["mode"]==0&&rendered["render"]["pose"]["valid"]==true);
    send("atlas2-request 1002 atlas2-travel 9999999");auto rejected=read();assert(rejected["ack"]["state"]=="rejected"&&rejected["ack"]["travel_request_result"]==0);
    send("atlas2-request 1003 atlas2-measure-start cpu_fixture");frame();
    send("atlas2-request 1004 atlas2-measure-stop");auto measured=read();assert(measured["measurement"]["active"]==false&&measured["measurement"]["present_samples"]>0&&measured["measurement"]["map_cpu_samples"]>0);
    std::ifstream result(trace.string()+".measurement.json");nlohmann::json values;result>>values;assert(values["present_interval_ms"].size()>0&&values["gpu_timestamp_measured"]==false);
    send("atlas2-request 1005 close");assert(!BbMap::IsOpen());BbMapStatic::Shutdown();ImGui::DestroyContext();std::puts("NATIVE_PROTOCOL_CPU_PASS");
}
