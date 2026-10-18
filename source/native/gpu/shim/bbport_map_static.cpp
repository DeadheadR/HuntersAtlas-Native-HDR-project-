// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_map_static.h"
#include "bbport_map_features.h"
#include "imgui_internal.h"
#include "../../../atlas2/core.h"
#include <cstdlib>
#include <chrono>
#include <memory>
#include <tuple>

namespace BbMapStatic { namespace {
using namespace Atlas2;
struct Record {int lod,x,y;fs::path path;std::string hash;};
struct Group {std::vector<int> requirements;std::map<std::tuple<int,int,int>,Record> tiles;};
struct View {std::vector<Group> groups;};
struct Slot {std::unique_ptr<ImTextureData> texture;std::string key;int frame=-1;};
std::array<Slot,CacheSlots> slots;
std::array<std::string,128> rejected_tiles;size_t rejected_next=0;
std::string loaded,error;fs::path root,area_root;Transform transform;Grid grid;
View context;std::vector<View> views;int primary=-1,levels=1,previous=-1,manual=-1,mode=0;
float last_x=0,last_z=0;bool prior_valid=false;uint64_t hits=0,misses=0,failures=0;int uploads=0,retirements=0,visible=0,last_lod=0;double draw_ms=0;int unique=2000000;
View ParseView(const Json& j,const fs::path& base){View v;if(j.at("groups").size()>128)throw std::runtime_error("group bound");for(const auto& g:j.at("groups")){Group out;out.requirements=g.at("requires").get<std::vector<int>>();for(int r:out.requirements)if(r< -1||r>255)throw std::runtime_error("reveal index");if(g.at("tiles").size()>200000)throw std::runtime_error("tile manifest bound");for(const auto& t:g.at("tiles")){std::string file=t.at("file");if(file.empty()||file.find("..")!=std::string::npos||file.find(':')!=std::string::npos||file.find('\\')!=std::string::npos||fs::path(file).is_absolute())throw std::runtime_error("tile path");Record r{t.at("lod"),t.at("x"),t.at("y"),base/file,t.at("sha256")};if(r.lod<0||r.lod>=levels||r.x<0||r.y<0||r.x>128||r.y>128||r.hash.size()!=64)throw std::runtime_error("tile coordinate");if(!out.tiles.emplace(std::tuple{r.lod,r.x,r.y},r).second)throw std::runtime_error("duplicate tile");}v.groups.push_back(std::move(out));}return v;}
void Collect(){for(auto& s:slots)if(s.texture&&s.texture->WantDestroyNextFrame&&s.texture->Status==ImTextureStatus_Destroyed){ImGui::UnregisterUserTexture(s.texture.get());s.texture.reset();s.key.clear();}}
ImTextureData* Texture(const Record& r){const auto key=r.path.string();if(std::find(rejected_tiles.begin(),rejected_tiles.end(),key)!=rejected_tiles.end())return nullptr;int frame=ImGui::GetFrameCount();for(auto& s:slots)if(s.texture&&!s.texture->WantDestroyNextFrame&&s.key==key){s.frame=frame;++hits;return s.texture.get();}++misses;
    Slot* free=nullptr;for(auto& s:slots)if(!s.texture){free=&s;break;}
    if(!free){Slot* old=nullptr;for(auto& s:slots)if(s.texture&&!s.texture->WantDestroyNextFrame&&s.frame<frame-1&&(!old||s.frame<old->frame))old=&s;if(old&&retirements<8){old->texture->WantDestroyNextFrame=true;++retirements;}return nullptr;}
    if(uploads>=4)return nullptr;
    try{auto bytes=Decode(Read(r.path,TileBytes+1024),r.hash);auto t=std::make_unique<ImTextureData>();t->Create(ImTextureFormat_RGBA32,Dimension,Dimension);std::copy(bytes.begin(),bytes.end(),static_cast<unsigned char*>(t->GetPixels()));t->UseColors=true;t->UniqueID=unique++;ImGui::RegisterUserTexture(t.get());free->texture=std::move(t);free->key=key;free->frame=frame;++uploads;return free->texture.get();}catch(...){++failures;rejected_tiles[rejected_next++%rejected_tiles.size()]=key;error="Static tile unavailable or failed integrity check";return nullptr;}
}
bool Allowed(const Group& g,const std::vector<bool>& flags){if(!BbMapFeatures::FogEnabled())return true;for(int r:g.requirements)if(r<0||r>=int(flags.size())||!flags[r])return false;return true;}
int Count(const View& view,int lod,int x0,int y0,int x1,int y1,const std::vector<bool>& flags){int n=0;for(const auto& g:view.groups)if(Allowed(g,flags))for(int x=x0;x<=x1;++x)for(int y=y0;y<=y1;++y)n+=g.tiles.count({lod,x,y});return n;}
}
bool Enabled(){static bool enabled=[](){const char* v=std::getenv("BB_ATLAS2_ENABLED");return v&&std::string(v)=="1";}();return enabled;}
bool Load(const std::string& region){if(!Enabled())return false;if(loaded==region)return error.empty()||!views.empty();loaded=region;error.clear();grid={};context={};views.clear();prior_valid=false;previous=-1;manual=-1;primary=-1;
    try{const char* dir=std::getenv("BB_ATLAS2_DIR"),*expected=std::getenv("BB_ATLAS2_INDEX_SHA256");if(!dir||!expected)throw std::runtime_error("Atlas2 pack configuration missing");root=fs::path(dir);auto bytes=Read(root/"atlas2-index.json",1024*1024);if(Hash(bytes)!=expected)throw std::runtime_error("Atlas2 index identity mismatch");auto index=Json::parse(bytes);if(index.at("schema")!=1||index.at("areas").size()>16)throw std::runtime_error("Atlas2 index schema");Json entry;for(const auto& r:index.at("areas"))if(r.at("region_id")==region)entry=r;if(entry.is_null())throw std::runtime_error("Atlas2 area pack unavailable");std::string label=entry.at("area");if(label.size()!=6||label.rfind("Area",0)!=0||label.find_first_not_of("0123456789",4)!=std::string::npos)throw std::runtime_error("Atlas2 area identity");area_root=root/label;
        bytes=Read(area_root/"manifest.json",32*1024*1024);if(Hash(bytes)!=entry.at("manifest_sha256").get<std::string>())throw std::runtime_error("Atlas2 manifest identity mismatch");auto m=Json::parse(bytes);if(m.at("schema")!=1||m.at("region_id")!=region||m.at("vertical_axis")!="Y"||m.at("tile_size")!=Tile||m.at("gutter")!=Gutter)throw std::runtime_error("Atlas2 format mismatch");auto b=m.at("bounds").get<std::array<double,4>>();transform={b[0],b[3],m.at("ppu"),m.at("width"),m.at("height")};transform.Validate();levels=m.at("levels");if(levels<1||levels>16||m.at("views").size()>128)throw std::runtime_error("Atlas2 layer bounds");
        bytes=Read(area_root/"grid.json");if(Hash(bytes)!=m.at("grid_sha256").get<std::string>())throw std::runtime_error("Atlas2 grid integrity mismatch");grid.FromJson(Json::parse(bytes));primary=m.at("primary");context=ParseView(m.at("context"),area_root/"context");int i=0;for(const auto& v:m.at("views"))views.push_back(ParseView(v,area_root/("F"+std::to_string(i++))));if(grid.anchors.size()!=views.size()||primary<0||primary>=int(views.size()))throw std::runtime_error("Atlas2 layer identity");return true;
    }catch(...){error="Static area data unavailable or failed integrity check";grid={};context={};views.clear();return false;}}
int Select(const std::string& region,float x,float y,float z,bool valid,bool continuity){if(!valid||!Load(region)){prior_valid=false;previous=-1;return -1;}bool keep=continuity&&prior_valid&&std::hypot(x-last_x,z-last_z)<20;int selected=grid.Select(x,y,z,keep?previous:-1,keep?.35f:0.f,manual);if(continuity){previous=selected;last_x=x;last_z=z;prior_valid=selected>=0;}return selected;}
int Primary(const std::string& region){return Load(region)?primary:-1;}
int Mode(){return mode;}
Json ProjectionMetrics(float x,float z,float zoom){auto uv=transform.Image(x,z),world=transform.World(uv[0],uv[1]);double delta=std::hypot(world[0]-x,world[1]-z);return {{"roundtrip_world_delta",delta},{"roundtrip_pixel_delta",delta*zoom},{"kind","world-image-world roundtrip; live visual alignment unmeasured"}};}
void Command(const std::string& c){if(!Enabled())return;if(c=="atlas2-static")mode=0;if(c=="atlas2-reference")mode=1;if(c=="atlas2-overlay")mode=2;if(c=="atlas2-floor-auto")manual=-1;if(c.rfind("atlas2-floor ",0)==0){try{int v=std::stoi(c.substr(13));if(v>=0&&v<int(grid.anchors.size()))manual=v;}catch(...){}}}
void Draw(ImDrawList* draw,const std::string& region,int layer,ImVec2 center,ImVec2 extent,float cx,float cz,float zoom,float opacity){
    auto start=std::chrono::steady_clock::now();Collect();uploads=retirements=visible=0;if(!Load(region)||layer<0||layer>=int(views.size())){draw->AddText({center.x-180,center.y},IM_COL32(223,214,187,255),"Static area data unavailable; check local pack.");return;}
    // One authored flag snapshot per frame, before tile lookup/drawing. No flag reads in geometry loops.
    const auto flags=BbMapFeatures::StaticRegionVisibility(region);int lod=Lod(zoom,transform.ppu,levels);int x0,y0,x1,y1;
    auto range=[&](){double units=Tile*std::pow(2,lod)/transform.ppu;x0=std::max(0,int(std::floor((cx-extent.x*.5/zoom-transform.x0)/units)));x1=std::min(int(std::ceil(transform.width/transform.ppu/units))-1,int(std::floor((cx+extent.x*.5/zoom-transform.x0)/units)));y0=std::max(0,int(std::floor((transform.z1-(cz+extent.y*.5/zoom))/units)));y1=std::min(int(std::ceil(transform.height/transform.ppu/units))-1,int(std::floor((transform.z1-(cz-extent.y*.5/zoom))/units)));};
    range();while(lod<levels-1&&Count(context,lod,x0,y0,x1,y1,flags)+Count(views[layer],lod,x0,y0,x1,y1,flags)>48){++lod;range();}last_lod=lod;
    auto render=[&](const View& v){double units=Tile*std::pow(2,lod)/transform.ppu;for(const auto& g:v.groups)if(Allowed(g,flags))for(int y=y0;y<=y1;++y)for(int x=x0;x<=x1;++x){auto it=g.tiles.find({lod,x,y});if(it==g.tiles.end())continue;++visible;if(auto* t=Texture(it->second)){float wx=float(transform.x0+x*units),wz=float(transform.z1-y*units);ImVec2 a(center.x+(wx-cx)*zoom,center.y-(wz-cz)*zoom),b(a.x+float(units)*zoom,a.y+float(units)*zoom);float lo=float(Gutter)/Dimension,hi=float(Gutter+Tile)/Dimension;draw->AddImage(t->GetTexRef(),a,b,{lo,lo},{hi,hi},IM_COL32(255,255,255,int(std::clamp(opacity,0.f,1.f)*255)));}}};
    render(context);render(views[layer]);if(!error.empty())draw->AddText({center.x-180,center.y},IM_COL32(223,214,187,255),error.c_str());draw_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
}
Json Stats(){int used=0,retired=0;for(const auto& s:slots)if(s.texture){++used;retired+=s.texture->WantDestroyNextFrame;}return {{"schema",1},{"mode",mode},{"area_loaded",!views.empty()},{"layer",previous},{"manual_layer",manual},{"lod",last_lod},{"visible_tiles",visible},{"resident_slots",used},{"retiring_slots",retired},{"slot_limit",CacheSlots},{"cpu_pixel_bytes",used*TileBytes},{"requested_gpu_rgba_byte_bound",CacheSlots*TileBytes},{"uploads_this_frame",uploads},{"hits",hits},{"misses",misses},{"integrity_failures",failures},{"local_candidates",grid.last_candidates},{"candidate_bound",grid.max_candidates},{"submit_ms",draw_ms},{"error",error}};}
void Shutdown(){for(auto& s:slots)if(s.texture){if(s.texture->GetTexID()!=ImTextureID_Invalid||s.texture->BackendUserData)continue;ImGui::UnregisterUserTexture(s.texture.get());s.texture.reset();}grid={};views.clear();context={};loaded.clear();}
}
