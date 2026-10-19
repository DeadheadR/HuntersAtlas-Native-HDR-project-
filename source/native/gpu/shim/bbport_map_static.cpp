// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_map_static.h"
#include "bbport_map_features.h"
#include "imgui_internal.h"
#include "../../../atlas2/core.h"
#include <cstdlib>
#include <chrono>
#include <memory>
#include <tuple>
#include <set>
#include <limits>
#include <future>

namespace BbMapStatic { namespace {
using namespace Atlas2;
struct Record {int lod,x,y;fs::path path;std::string hash;};
using TileMap=std::map<std::tuple<int,int,int>,Record>;
struct Group {std::vector<int> requirements,forbids;int fog=0,shaded=-1;std::shared_ptr<const TileMap> tiles;};
struct View {std::vector<Group> groups;Transform transform;int levels=1;bool composite=false;fs::path lines;std::string line_hash;fs::path external;std::string external_hash;int external_layer=-1;bool prepared=true,rejected=false;};
struct Line {std::array<float,4> v;std::vector<int> requirements;int kind;};
struct LineCache {int layer=-1;std::vector<Line> lines;std::map<std::pair<int,int>,std::vector<int>> cells;std::array<int,4> range{0,0,-1,-1};std::vector<int> visible;std::vector<bool> flags;bool fog=false,valid=false;};
LineCache line_cache;int line_candidates=0,line_drawn=0;double detail_ppu=8;bool composite_active=false;
struct Slot {std::unique_ptr<ImTextureData> texture;std::string key;int frame=-1;};
std::array<Slot,CacheSlots> slots;
std::array<std::string,128> rejected_tiles;size_t rejected_next=0;
int detailed_layer=-1;std::string loaded,error;fs::path root,area_root;Transform transform;Grid grid;
View context;std::vector<View> views;int primary=-1,levels=1,previous=-1,manual=-1,mode=0;
float last_x=0,last_z=0;bool prior_valid=false;uint64_t hits=0,misses=0,failures=0,evicted_total=0,created_total=0,collected_total=0;int uploads=0,retirements=0,visible=0,backend_ready=0,last_lod=0;double draw_ms=0;int unique=2000000;
fs::path SafePath(const fs::path& base,const std::string& file){if(file.empty()||file.find("..")!=std::string::npos||file.find(':')!=std::string::npos||file.find('\\')!=std::string::npos||fs::path(file).is_absolute())throw std::runtime_error("pack path");return base/file;}
void CheckRequirements(const std::vector<int>& values){if(values.size()>256)throw std::runtime_error("reveal bound");for(int r:values)if(r< -1||r>255)throw std::runtime_error("reveal index");}
View ParseView(const Json& j,const fs::path& base,const Transform& base_transform,int base_levels){
    View v;v.transform=base_transform;v.levels=base_levels;v.composite=j.value("kind",std::string("legacy"))=="composite";
    if(j.contains("ppu")){v.transform.ppu=j.at("ppu");v.transform.width=j.at("width");v.transform.height=j.at("height");v.levels=j.at("levels");v.transform.Validate();if(v.levels<1||v.levels>16)throw std::runtime_error("view levels");auto matrix=j.at("world_to_image").get<std::array<double,6>>();std::array<double,6> expected={v.transform.ppu,0,-v.transform.x0*v.transform.ppu,0,-v.transform.ppu,v.transform.z1*v.transform.ppu};for(int i=0;i<6;++i)if(!std::isfinite(matrix[i])||std::abs(matrix[i]-expected[i])>1e-6)throw std::runtime_error("view transform mismatch");}
    if(j.contains("view_file")){v.external=SafePath(base,j.at("view_file"));v.external_hash=j.at("view_sha256");v.external_layer=j.at("layer_index");if(v.external_hash.size()!=64)throw std::runtime_error("view identity");v.composite=true;v.prepared=false;return v;}
    std::vector<std::shared_ptr<const TileMap>> sets(j.value("tile_sets",Json::array()).size());if(sets.size()>128)throw std::runtime_error("tile set bound");
    if(j.at("groups").size()>128)throw std::runtime_error("group bound");
    for(const auto& g:j.at("groups")){
        Group out;out.requirements=g.at("requires").get<std::vector<int>>();out.forbids=g.value("forbids",std::vector<int>{});CheckRequirements(out.requirements);CheckRequirements(out.forbids);
        auto fog=g.value("fog_mode",std::string("any"));if(fog!="any"&&fog!="on"&&fog!="off")throw std::runtime_error("fog mode");out.fog=fog=="on"?1:fog=="off"?2:0;out.shaded=g.value("shaded",-1);if(out.shaded< -1||out.shaded>1)throw std::runtime_error("shading variant");
        const Json* records=nullptr;int set=-1;if(g.contains("tile_set")){set=g.at("tile_set");if(set<0||set>=int(sets.size()))throw std::runtime_error("tile set index");records=&j.at("tile_sets").at(set);}else records=&g.at("tiles");
        if(set>=0&&sets[set])out.tiles=sets[set];else{auto tiles=std::make_shared<TileMap>();if(records->size()>200000)throw std::runtime_error("tile manifest bound");for(const auto& t:*records){Record r;
            if(t.is_array()){if(t.size()!=4)throw std::runtime_error("compact tile record");r.lod=t.at(0);r.x=t.at(1);r.y=t.at(2);r.hash=t.at(3);r.path=SafePath(base,"objects/"+r.hash+".a2t");}else{r={t.at("lod"),t.at("x"),t.at("y"),SafePath(base,t.at("file")),t.at("sha256")};}
            if(r.lod<0||r.lod>=v.levels||r.x<0||r.y<0||r.hash.size()!=64||r.hash.find_first_not_of("0123456789abcdef")!=std::string::npos||r.x>=int(std::ceil(v.transform.width/std::ldexp(double(Tile),r.lod)))||r.y>=int(std::ceil(v.transform.height/std::ldexp(double(Tile),r.lod))))throw std::runtime_error("tile coordinate");
            if(!tiles->emplace(std::tuple{r.lod,r.x,r.y},r).second)throw std::runtime_error("duplicate tile");
        }out.tiles=tiles;if(set>=0)sets[set]=tiles;}v.groups.push_back(std::move(out));
    }
    if(j.contains("line_overlay")){v.lines=SafePath(base,j.at("line_overlay").at("file"));v.line_hash=j.at("line_overlay").at("sha256");if(v.line_hash.size()!=64)throw std::runtime_error("line identity");}
    return v;
}
// The optional loader owns only local immutable file data. ImGui, game flags,
// selection history and GPU texture ownership remain on the caller thread.
struct AreaData {fs::path root,area_root;Transform transform;Grid grid;View context;std::vector<View> views;int primary=-1,levels=1;};
struct PreparedView {View view;LineCache lines;};
std::string area_target;int view_target=-1;bool area_ready=false;
double area_worker_ms=0,view_worker_ms=0;uint64_t loader_requests=0,loader_stale=0;
struct TimedArea {AreaData data;double ms=0;};
// Timing is returned with each result, never written by the worker to shared state.
std::future<TimedArea> timed_area_job;
bool AsyncLoading(){const char* e=std::getenv("BB_ATLAS2_ASYNC_LOAD");return e&&std::string(e)=="1";}
LineCache ReadLines(const View& view,int layer){
    LineCache out;out.layer=layer;if(view.lines.empty())return out;
    auto bytes=Read(view.lines,8*1024*1024);if(Hash(bytes)!=view.line_hash)throw std::runtime_error("line hash");auto j=Json::parse(bytes);
    if(j.at("schema")!=1||j.at("cell")!=32||j.at("lines").size()>LineSegmentLimit||j.at("cells").size()>16384)throw std::runtime_error("line bounds");
    for(const auto& l:j.at("lines")){Line v{l.at(1).get<std::array<float,4>>(),l.at(2).get<std::vector<int>>(),l.at(0)};if(v.kind<0||v.kind>1)throw std::runtime_error("line kind");for(float f:v.v)if(!std::isfinite(f)||std::abs(f)>1e6)throw std::runtime_error("line coordinate");CheckRequirements(v.requirements);out.lines.push_back(std::move(v));}
    size_t refs=0;for(const auto& cell:j.at("cells")){int x=cell.at(0),z=cell.at(1);if(std::abs(double(x))>31250||std::abs(double(z))>31250)throw std::runtime_error("line cell");auto ids=cell.at(2).get<std::vector<int>>();refs+=ids.size();if(refs>1000000)throw std::runtime_error("line reference bound");for(int id:ids)if(id<0||id>=int(out.lines.size()))throw std::runtime_error("line index");if(!out.cells.emplace(std::pair{x,z},std::move(ids)).second)throw std::runtime_error("duplicate line cell");}
    out.valid=true;return out;
}
PreparedView ReadView(View header,fs::path base,int layer){
    auto bytes=Read(header.external,16*1024*1024);if(Hash(bytes)!=header.external_hash)throw std::runtime_error("view integrity");auto j=Json::parse(bytes);if(j.contains("view_file")||j.at("layer_index")!=layer||header.external_layer!=layer)throw std::runtime_error("view layer");auto v=ParseView(j,base,header.transform,header.levels);if(!v.composite||v.transform.ppu!=header.transform.ppu||v.transform.width!=header.transform.width||v.transform.height!=header.transform.height||v.levels!=header.levels)throw std::runtime_error("view header transform");v.external=header.external;v.external_hash=header.external_hash;v.external_layer=layer;auto lines=ReadLines(v,layer);return {std::move(v),std::move(lines)};
}
struct TimedView {PreparedView data;double ms=0;};
std::future<TimedView> timed_view_job;
bool JobBusy(){return timed_area_job.valid()||timed_view_job.valid();}
template<class T> bool Ready(std::future<T>& job){return job.valid()&&job.wait_for(std::chrono::seconds(0))==std::future_status::ready;}
void ClearDetail(){if(detailed_layer>=0&&detailed_layer<int(views.size())){auto& old=views[detailed_layer];old.groups.clear();old.lines.clear();old.prepared=false;}detailed_layer=-1;line_cache={};}
bool PrepareView(int layer){
    auto& v=views.at(layer);if(v.prepared)return true;if(v.rejected)return false;
    if(timed_view_job.valid()){
        if(!Ready(timed_view_job))return false;
        try{auto prepared=timed_view_job.get();view_worker_ms=prepared.ms;if(view_target==layer){v=std::move(prepared.data.view);line_cache=std::move(prepared.data.lines);detailed_layer=layer;return true;}++loader_stale;}
        catch(...){if(view_target>=0&&view_target<int(views.size()))views[view_target].rejected=true;error="Static view data unavailable or failed integrity check";++failures;}
        view_target=-1;if(v.rejected)return false;
    }
    if(JobBusy())return false;
    try{ClearDetail();if(AsyncLoading()){
        auto header=v;auto base=area_root;view_target=layer;++loader_requests;
        timed_view_job=std::async(std::launch::async,[header=std::move(header),base,layer](){auto t=std::chrono::steady_clock::now();auto data=ReadView(header,base,layer);return TimedView{std::move(data),std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count()};});return false;
    }auto prepared=ReadView(v,area_root,layer);v=std::move(prepared.view);line_cache=std::move(prepared.lines);detailed_layer=layer;return true;}
    catch(...){v.rejected=true;error="Static view data unavailable or failed integrity check";++failures;return false;}
}
void Collect(){for(auto& s:slots)if(s.texture&&s.texture->WantDestroyNextFrame&&s.texture->Status==ImTextureStatus_Destroyed){ImGui::UnregisterUserTexture(s.texture.get());s.texture.reset();s.key.clear();++collected_total;}}
ImTextureData* Texture(const Record& r){const auto key=r.path.string();if(std::find(rejected_tiles.begin(),rejected_tiles.end(),key)!=rejected_tiles.end())return nullptr;int frame=ImGui::GetFrameCount();for(auto& s:slots)if(s.texture&&!s.texture->WantDestroyNextFrame&&s.key==key){s.frame=frame;++hits;return s.texture.get();}++misses;
    Slot* free=nullptr;for(auto& s:slots)if(!s.texture){free=&s;break;}
    if(!free){Slot* old=nullptr;for(auto& s:slots)if(s.texture&&!s.texture->WantDestroyNextFrame&&s.frame<frame-1&&(!old||s.frame<old->frame))old=&s;if(old&&retirements<8){old->texture->WantDestroyNextFrame=true;++retirements;++evicted_total;}return nullptr;}
    if(uploads>=4)return nullptr;
    try{auto bytes=Decode(Read(r.path,TileBytes+1024),r.hash);auto t=std::make_unique<ImTextureData>();t->Create(ImTextureFormat_RGBA32,Dimension,Dimension);std::copy(bytes.begin(),bytes.end(),static_cast<unsigned char*>(t->GetPixels()));t->UseColors=true;t->UniqueID=unique++;ImGui::RegisterUserTexture(t.get());free->texture=std::move(t);free->key=key;free->frame=frame;++uploads;++created_total;return free->texture.get();}catch(...){++failures;rejected_tiles[rejected_next++%rejected_tiles.size()]=key;error="Static tile unavailable or failed integrity check";return nullptr;}
}
bool Required(const std::vector<int>& requirements,const std::vector<bool>& flags){for(int r:requirements)if(r<0||r>=int(flags.size())||!flags[r])return false;return true;}
bool Allowed(const Group& g,const std::vector<bool>& flags,bool fog,bool shading){if(g.shaded>=0&&g.shaded!=int(shading))return false;if(g.fog==1&&!fog||g.fog==2&&fog)return false;if(!fog)return true;if(!Required(g.requirements,flags))return false;for(int r:g.forbids)if(r>=0&&r<int(flags.size())&&flags[r])return false;return true;}
int Count(const View& view,int lod,int x0,int y0,int x1,int y1,const std::vector<bool>& flags,bool fog,bool shading){int n=0;for(const auto& g:view.groups)if(Allowed(g,flags,fog,shading))for(int x=x0;x<=x1;++x)for(int y=y0;y<=y1;++y)n+=g.tiles->count({lod,x,y});return n;}
void Lines(ImDrawList* draw,const View& view,int layer,ImVec2 center,ImVec2 extent,float cx,float cz,float zoom,float opacity,float scale,const std::vector<bool>& flags,bool fog){
    line_candidates=line_drawn=0;if(view.lines.empty())return;
    if(line_cache.layer!=layer){
        line_cache={};line_cache.layer=layer;
        try{
            auto bytes=Read(view.lines,8*1024*1024);if(Hash(bytes)!=view.line_hash)throw std::runtime_error("line hash");auto j=Json::parse(bytes);
            if(j.at("schema")!=1||j.at("cell")!=32||j.at("lines").size()>LineSegmentLimit||j.at("cells").size()>16384)throw std::runtime_error("line bounds");
            for(const auto& l:j.at("lines")){Line v{l.at(1).get<std::array<float,4>>(),l.at(2).get<std::vector<int>>(),l.at(0)};if(v.kind<0||v.kind>1)throw std::runtime_error("line kind");for(float f:v.v)if(!std::isfinite(f)||std::abs(f)>1e6)throw std::runtime_error("line coordinate");CheckRequirements(v.requirements);line_cache.lines.push_back(std::move(v));}
            size_t refs=0;for(const auto& cell:j.at("cells")){int x=cell.at(0),z=cell.at(1);if(std::abs(double(x))>31250||std::abs(double(z))>31250)throw std::runtime_error("line cell");auto ids=cell.at(2).get<std::vector<int>>();refs+=ids.size();if(refs>1000000)throw std::runtime_error("line reference bound");for(int id:ids)if(id<0||id>=int(line_cache.lines.size()))throw std::runtime_error("line index");if(!line_cache.cells.emplace(std::pair{x,z},std::move(ids)).second)throw std::runtime_error("duplicate line cell");}
            line_cache.valid=true;
        }catch(...){line_cache.lines.clear();line_cache.cells.clear();error="Static line overlay unavailable or failed integrity check";++failures;}
    }
    if(!line_cache.valid)return;
    auto cell=[](double value){return int(std::floor(std::clamp(value,-1e6,1e6)/32));};
    std::array<int,4> range={cell(cx-extent.x*.5/zoom),cell(cz-extent.y*.5/zoom),cell(cx+extent.x*.5/zoom),cell(cz+extent.y*.5/zoom)};
    if(range!=line_cache.range||flags!=line_cache.flags||fog!=line_cache.fog){
        line_cache.range=range;line_cache.flags=flags;line_cache.fog=fog;std::set<int> candidates;
        // This bounded cell index is revisited only when the visible cell range or flags change.
        for(auto it=line_cache.cells.lower_bound({range[0],std::numeric_limits<int>::min()});it!=line_cache.cells.end()&&it->first.first<=range[2];++it)if(it->first.second>=range[1]&&it->first.second<=range[3])candidates.insert(it->second.begin(),it->second.end());
        line_cache.visible.clear();for(int id:candidates)if(!fog||Required(line_cache.lines[id].requirements,flags))line_cache.visible.push_back(id);
    }
    line_candidates=int(line_cache.visible.size());auto project=[&](float x,float z){return ImVec2(center.x+(x-cx)*zoom,center.y-(z-cz)*zoom);};
    for(int id:line_cache.visible){const auto& l=line_cache.lines[id];const auto& p=l.v;if(std::max(p[0],p[2])<cx-extent.x*.5/zoom||std::min(p[0],p[2])>cx+extent.x*.5/zoom||std::max(p[1],p[3])<cz-extent.y*.5/zoom||std::min(p[1],p[3])>cz+extent.y*.5/zoom)continue;draw->AddLine(project(p[0],p[1]),project(p[2],p[3]),l.kind?IM_COL32(204,193,163,int(220*opacity)):IM_COL32(15,18,19,int(255*opacity)),l.kind?.85f*scale:std::clamp(zoom*.13f,2.5f*scale,5.f*scale));++line_drawn;}
}
}
bool Enabled(){static bool enabled=[](){const char* v=std::getenv("BB_ATLAS2_ENABLED");return v&&std::string(v)=="1";}();return enabled;}
AreaData ReadArea(const std::string& region){AreaData out;auto& root=out.root;auto& area_root=out.area_root;auto& transform=out.transform;auto& grid=out.grid;auto& context=out.context;auto& views=out.views;auto& primary=out.primary;auto& levels=out.levels;
    const char* dir=std::getenv("BB_ATLAS2_DIR"),*expected=std::getenv("BB_ATLAS2_INDEX_SHA256");if(!dir||!expected)throw std::runtime_error("Atlas2 pack configuration missing");root=fs::path(dir);auto bytes=Read(root/"atlas2-index.json",1024*1024);if(Hash(bytes)!=expected)throw std::runtime_error("Atlas2 index identity mismatch");auto index=Json::parse(bytes);if(index.at("schema")!=1||index.at("areas").size()>16)throw std::runtime_error("Atlas2 index schema");Json entry;for(const auto& r:index.at("areas"))if(r.at("region_id")==region)entry=r;if(entry.is_null())throw std::runtime_error("Atlas2 area pack unavailable");std::string label=entry.at("area");if(label.size()!=6||label.rfind("Area",0)!=0||label.find_first_not_of("0123456789",4)!=std::string::npos)throw std::runtime_error("Atlas2 area identity");area_root=root/label;
        bytes=Read(area_root/"manifest.json",32*1024*1024);if(Hash(bytes)!=entry.at("manifest_sha256").get<std::string>())throw std::runtime_error("Atlas2 manifest identity mismatch");auto m=Json::parse(bytes);const int schema=m.at("schema");if((schema!=1&&schema!=2&&schema!=3)||m.at("region_id")!=region||m.at("vertical_axis")!="Y"||m.at("tile_size")!=Tile||m.at("gutter")!=Gutter)throw std::runtime_error("Atlas2 format mismatch");auto b=m.at("bounds").get<std::array<double,4>>();transform={b[0],b[3],m.at("ppu"),m.at("width"),m.at("height")};transform.Validate();levels=m.at("levels");if(levels<1||levels>16||m.at("views").size()>128)throw std::runtime_error("Atlas2 layer bounds");
        bytes=Read(area_root/"grid.json");if(Hash(bytes)!=m.at("grid_sha256").get<std::string>())throw std::runtime_error("Atlas2 grid integrity mismatch");grid.FromJson(Json::parse(bytes));primary=m.at("primary");context=ParseView(m.at("context"),schema==1?area_root/"context":area_root,transform,levels);int i=0;for(const auto& v:m.at("views")){views.push_back(ParseView(v,schema==1?area_root/("F"+std::to_string(i)):area_root,transform,levels));if(!views.back().external.empty()&&views.back().external_layer!=i)throw std::runtime_error("view index");++i;}if(grid.anchors.size()!=views.size()||primary<0||primary>=int(views.size()))throw std::runtime_error("Atlas2 layer identity");return out;
}
void AdoptArea(AreaData data){root=std::move(data.root);area_root=std::move(data.area_root);transform=data.transform;grid=std::move(data.grid);context=std::move(data.context);views=std::move(data.views);primary=data.primary;levels=data.levels;area_ready=true;}
bool Load(const std::string& region){
    if(!Enabled())return false;
    if(loaded==region&&area_ready)return true;
    if(timed_area_job.valid()){
        if(!Ready(timed_area_job))return false;
        try{auto ready=timed_area_job.get();area_worker_ms=ready.ms;if(area_target==region){AdoptArea(std::move(ready.data));return true;}++loader_stale;}
        catch(...){error="Static area data unavailable or failed integrity check";++failures;if(area_target==region)return false;}
    }
    if(timed_view_job.valid()){
        if(!Ready(timed_view_job))return false;
        try{timed_view_job.get();++loader_stale;}catch(...){++failures;}
        view_target=-1;
    }
    if(loaded==region)return false; // A rejected area is not reread every frame.
    loaded=region;area_ready=false;error.clear();prior_valid=false;previous=-1;manual=-1;primary=-1;detailed_layer=-1;line_cache={};line_candidates=line_drawn=0;
    try{if(AsyncLoading()){
        area_target=region;++loader_requests;
        timed_area_job=std::async(std::launch::async,[region,old_grid=std::move(grid),old_context=std::move(context),old_views=std::move(views)]()mutable{old_grid={};old_context={};old_views.clear();auto t=std::chrono::steady_clock::now();auto data=ReadArea(region);return TimedArea{std::move(data),std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count()};});return false;
    }grid={};context={};views.clear();AdoptArea(ReadArea(region));return true;}
    catch(...){error="Static area data unavailable or failed integrity check";grid={};context={};views.clear();return false;}
}
int Select(const std::string& region,float x,float y,float z,bool valid,bool continuity){if(!valid||!Load(region)){prior_valid=false;previous=-1;return -1;}bool keep=continuity&&prior_valid&&std::hypot(x-last_x,z-last_z)<20;int selected=grid.Select(x,y,z,keep?previous:-1,keep?.35f:0.f,manual);if(continuity){previous=selected;last_x=x;last_z=z;prior_valid=selected>=0;}return selected;}
int Primary(const std::string& region){return Load(region)?primary:-1;}
int StrictLayer(const std::string& region,float x,float y,float z,bool valid){return valid&&Load(region)?grid.Select(x,y,z):-1;}
int ManualLayer(){return manual;}
int Mode(){return mode;}
Json ProjectionMetrics(float x,float z,float zoom){auto uv=transform.Image(x,z),world=transform.World(uv[0],uv[1]);double delta=std::hypot(world[0]-x,world[1]-z);return {{"roundtrip_world_delta",delta},{"roundtrip_pixel_delta",delta*zoom},{"kind","world-image-world roundtrip; live visual alignment unmeasured"}};}
void Command(const std::string& c){if(!Enabled())return;if(c=="atlas2-static")mode=0;if(c=="atlas2-reference")mode=1;if(c=="atlas2-overlay")mode=2;if(c=="atlas2-floor-auto"){manual=-1;prior_valid=false;previous=-1;}if(c.rfind("atlas2-floor ",0)==0){try{int v=std::stoi(c.substr(13));if(v>=0&&v<int(grid.anchors.size()))manual=v;}catch(...){}}}
void Draw(ImDrawList* draw,const std::string& region,int layer,ImVec2 center,ImVec2 extent,float cx,float cz,float zoom,float opacity,bool shading,float ui_scale){
    auto start=std::chrono::steady_clock::now();Collect();uploads=retirements=visible=backend_ready=0;line_candidates=line_drawn=0;
    // A failed backend allocation stays WantCreate. Its retry consumes the same
    // four-request budget as newly decoded tiles on the following frame.
    for(const auto& slot:slots)if(slot.texture&&!slot.texture->WantDestroyNextFrame&&slot.texture->Status==ImTextureStatus_WantCreate)++uploads;
    if(!std::isfinite(cx)||!std::isfinite(cz)||!std::isfinite(zoom)||zoom<=0||!std::isfinite(ui_scale)||ui_scale<=0||!Load(region)||layer<0||layer>=int(views.size())){draw->AddText({center.x-180,center.y},IM_COL32(223,214,187,255),JobBusy()?"Loading map...":"Static area data unavailable; check local pack.");return;}
    if(!PrepareView(layer)){draw->AddText(center,IM_COL32(223,214,187,255),JobBusy()?"Loading map...":error.c_str());return;}
    opacity=std::clamp(opacity,0.f,1.f);const auto flags=BbMapFeatures::StaticRegionVisibility(region);const bool fog=BbMapFeatures::FogEnabled();const View& active=views[layer];const Transform& t=active.transform;const bool composite=active.composite;composite_active=composite;detail_ppu=t.ppu;
    // A composite is already ordered like V1 and excludes its active floor from context.
    // Legacy slices retain their original context+active composition for compatibility.
    int lod=Lod(zoom,t.ppu,active.levels),x0,y0,x1,y1;
    auto range=[&](){double units=Tile*std::pow(2,lod)/t.ppu;int nx=int(std::ceil(t.width/t.ppu/units)),ny=int(std::ceil(t.height/t.ppu/units));auto index=[](double value,int maximum){return int(std::floor(std::clamp(value,-1.,double(maximum))));};x0=std::max(0,index((cx-extent.x*.5/zoom-t.x0)/units,nx));x1=std::min(nx-1,index((cx+extent.x*.5/zoom-t.x0)/units,nx));y0=std::max(0,index((t.z1-(cz+extent.y*.5/zoom))/units,ny));y1=std::min(ny-1,index((t.z1-(cz-extent.y*.5/zoom))/units,ny));};
    range();while(lod<active.levels-1&&(composite?0:Count(context,lod,x0,y0,x1,y1,flags,fog,shading))+Count(active,lod,x0,y0,x1,y1,flags,fog,shading)>48){++lod;range();}last_lod=lod;
    auto render=[&](const View& v){double units=Tile*std::pow(2,lod)/v.transform.ppu;for(const auto& g:v.groups)if(Allowed(g,flags,fog,shading))for(int y=y0;y<=y1;++y)for(int x=x0;x<=x1;++x){auto it=g.tiles->find({lod,x,y});if(it==g.tiles->end())continue;++visible;if(auto* tex=Texture(it->second)){if(tex->Status!=ImTextureStatus_OK)continue;++backend_ready;float wx=float(v.transform.x0+x*units),wz=float(v.transform.z1-y*units);ImVec2 a(center.x+(wx-cx)*zoom,center.y-(wz-cz)*zoom),b(a.x+float(units)*zoom,a.y+float(units)*zoom);float lo=float(Gutter)/Dimension,hi=float(Gutter+Tile)/Dimension;draw->AddImage(ImTextureRef(tex->GetTexID()),a,b,{lo,lo},{hi,hi},IM_COL32(255,255,255,int(opacity*255)));}}};
    if(!composite)render(context);render(active);
    if(composite)Lines(draw,active,layer,center,extent,cx,cz,zoom,opacity,ui_scale,flags,fog);
    if(!error.empty())draw->AddText({center.x-180,center.y},IM_COL32(223,214,187,255),error.c_str());draw_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
}

Json Stats(){int used=0,retired=0,owned=0,prepared=0;for(const auto& v:views)prepared+=!v.external.empty()&&v.prepared;std::set<ImTextureID> ids,owned_ids;for(const auto& s:slots)if(s.texture){++used;retired+=s.texture->WantDestroyNextFrame;if(s.texture->Status==ImTextureStatus_OK)ids.insert(s.texture->GetTexID());if(s.texture->GetTexID()!=ImTextureID_Invalid&&s.texture->BackendUserData){++owned;owned_ids.insert(s.texture->GetTexID());}}return {{"schema",1},{"async_loading",AsyncLoading()},{"loader_jobs",int(timed_area_job.valid())+int(timed_view_job.valid())},{"loader_worker_limit",1},{"loader_requests",loader_requests},{"loader_stale_results",loader_stale},{"last_area_worker_ms",area_worker_ms},{"last_view_worker_ms",view_worker_ms},{"detail_ppu",detail_ppu},{"loaded_detail_layer",detailed_layer},{"composite",composite_active},{"line_candidates",line_candidates},{"lines_drawn",line_drawn},{"line_limit",LineSegmentLimit},{"mode",mode},{"area_loaded",area_ready},{"layer",previous},{"manual_layer",manual},{"lod",last_lod},{"visible_tiles",visible},{"backend_ready_tiles",backend_ready},{"resident_slots",used},{"distinct_backend_textures",ids.size()},{"backend_owned_slots",owned},{"distinct_owned_backend_ids",owned_ids.size()},{"prepared_external_views",prepared},{"texture_creations_total",created_total},{"evictions_total",evicted_total},{"collected_slots_total",collected_total},{"retiring_slots",retired},{"slot_limit",CacheSlots},{"cpu_pixel_bytes",used*TileBytes},{"requested_gpu_rgba_byte_bound",CacheSlots*TileBytes},{"uploads_this_frame",uploads},{"hits",hits},{"misses",misses},{"integrity_failures",failures},{"local_candidates",grid.last_candidates},{"candidate_bound",grid.max_candidates},{"submit_ms",draw_ms},{"error",error}};}
void Shutdown(){if(timed_area_job.valid())try{timed_area_job.get();}catch(...){}if(timed_view_job.valid())try{timed_view_job.get();}catch(...){}for(auto& s:slots)if(s.texture){if(s.texture->GetTexID()!=ImTextureID_Invalid||s.texture->BackendUserData)continue;ImGui::UnregisterUserTexture(s.texture.get());s.texture.reset();}grid={};views.clear();context={};line_cache={};detailed_layer=-1;loaded.clear();area_ready=false;area_target.clear();view_target=-1;}
}
