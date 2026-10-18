// SPDX-License-Identifier: GPL-2.0-or-later
// CPU-only parity tier. Reuses V1's topology/hatch helpers; never loads a GPU API.
#include "parity_style.h"
#include <chrono>
#include <iostream>
#include <unordered_set>
using namespace Atlas2Parity;
struct LayerData {
    float anchor,span,low,high;
    std::vector<Surface> floors;
    std::vector<BbAtlasInteriors::Ring> rings;
    std::vector<BbAtlasStyle::Line> walls;
};
struct Baker {
    fs::path out;Json source,feature;std::array<double,4> bounds;
    Transform transform;Texture parchment;std::vector<LayerData> layers;
    BbAtlasStyle::CutCache cut;BbAtlasInteriors::Cache interiors;
    std::unordered_set<std::string> objects;
    uint64_t new_bytes=0,new_objects=0;size_t primitive_count=0;
    explicit Baker(fs::path output,Json map,Json rules,const fs::path& art,double ppu)
      :out(output),source(std::move(map)),feature(std::move(rules)),parchment(art/"parchment.bbra") {
        bounds=source.at("bounds").get<std::array<double,4>>();transform={bounds[0],bounds[3],ppu,int(std::ceil((bounds[2]-bounds[0])*ppu)),int(std::ceil((bounds[3]-bounds[1])*ppu))};transform.Validate();
        std::vector<BbAtlasStyle::Triangle> all;
        std::vector<BbAtlasStyle::FloorIndex> per_layer;
        std::vector<std::vector<BbAtlasInteriors::Ring>> rings;
        for(size_t li=0;li<source.at("layers").size();++li){
            const auto& l=source["layers"][li];LayerData data;data.anchor=l.at("anchor");data.span=l.at("span");data.low=INFINITY;data.high=-INFINITY;std::vector<BbAtlasStyle::Triangle> floors;
            for(size_t i=0;i<l.at("triangles").size();++i){Surface s{l["triangles"][i].get<std::array<float,6>>(),l["heights"][i].get<std::array<float,3>>(),int(li)};data.floors.push_back(s);for(float y:s.y){data.low=std::min(data.low,y);data.high=std::max(data.high,y);}floors.push_back({{{{s.v[0],s.v[1]},{s.v[2],s.v[3]},{s.v[4],s.v[5]}}}});}
            if(data.floors.empty())data.low=data.high=data.anchor;
            for(const auto& ring:l.at("outlines")){BbAtlasInteriors::Ring r;for(const auto& p:ring)r.push_back({p[0],p[1]});data.rings.push_back(std::move(r));}
            for(const auto& w:l.at("walls"))data.walls.push_back({{w[0],w[1]},{w[2],w[3]}});
            all.insert(all.end(),floors.begin(),floors.end());per_layer.emplace_back();per_layer.back().Build(std::move(floors));rings.push_back(data.rings);layers.push_back(std::move(data));
        }
        cut.Build(std::move(all),layers.size());interiors.Build(rings,per_layer);
    }
    std::string Store(const std::vector<unsigned char>& pixels){
        auto bytes=Encode(pixels);std::string hash=Hash(bytes),name="objects/"+hash+".a2t";
        if(objects.insert(hash).second){const auto path=out/name;if(fs::exists(path)){if(Hash(Read(path,TileBytes+1024))!=hash)throw std::runtime_error("existing object mismatch");}else{if(new_bytes+bytes.size()>2ull*1024*1024*1024)throw std::runtime_error("parity output budget exceeded");Write(path,bytes);new_bytes+=bytes.size();++new_objects;}}
        return name;
    }
    std::vector<Primitive> Primitives(int active,int level,bool shaded){
        std::vector<Primitive> p;const float anchor=layers[active].anchor,style_zoom=9.f/std::pow(2.f,float(level));int hatch_lod=BbAtlasStyle::CutCache::Level(style_zoom,1);
        float low=anchor,high=anchor;for(const auto& l:layers)if(std::abs(l.anchor-anchor)<=6){low=std::min(low,l.low);high=std::max(high,l.high);}
        auto fill=[&](const BbAtlasStyle::Triangle& t,std::array<int,4> color,float y){Primitive q;q.v={t.p[0].x,t.p[0].z,t.p[1].x,t.p[1].z,t.p[2].x,t.p[2].z};q.color={color,color,color};q.required=BoxRequirements(feature,std::min({t.p[0].x,t.p[1].x,t.p[2].x}),std::min({t.p[0].z,t.p[1].z,t.p[2].z}),std::max({t.p[0].x,t.p[1].x,t.p[2].x}),std::max({t.p[0].z,t.p[1].z,t.p[2].z}),y);p.push_back(std::move(q));};
        auto line=[&](const BbAtlasStyle::Line& l,float width,std::array<int,4> color,float y){if(std::hypot(l.b.x-l.a.x,l.b.z-l.a.z)<1e-8)return;p.push_back(Stroke(l.a.x,l.a.z,l.b.x,l.b.z,width,color,BoxRequirements(feature,std::min(l.a.x,l.b.x),std::min(l.a.z,l.b.z),std::max(l.a.x,l.b.x),std::max(l.a.z,l.b.z),y)));};
        auto floor=[&](const LayerData& l,int alpha){for(const auto& t:l.floors){Primitive q;q.v=t.v;q.textured=true;for(int k=0;k<3;++k)q.color[k]=HeightTint(t.y[k],low,high,alpha,shaded);const auto&v=t.v;float x0=std::min({v[0],v[2],v[4]}),z0=std::min({v[1],v[3],v[5]}),x1=std::max({v[0],v[2],v[4]}),z1=std::max({v[1],v[3],v[5]});q.required=Requirements(feature,{{(v[0]+v[2]+v[4])/3,(t.y[0]+t.y[1]+t.y[2])/3,(v[1]+v[3]+v[5])/3},{v[0],t.y[0],v[1]},{v[2],t.y[1],v[3]},{v[4],t.y[2],v[5]},{x0,l.anchor,z0},{x1,l.anchor,z1},{(x0+x1)/2,l.anchor,(z0+z1)/2}});p.push_back(std::move(q));}};
        // Preserve the V1 pass order, including context exclusion of the active floor.
        for(int pass=0;pass<2;++pass)for(size_t li=0;li<layers.size();++li)if((int(li)==active)==(pass==1))for(const auto& t:interiors.layers[li])fill(t,pass==1?std::array<int,4>{53,48,39,255}:std::array<int,4>{44,41,34,255},anchor);
        for(size_t li=0;li<layers.size();++li)for(const auto& l:interiors.Get(li,hatch_lod))line(l,.72f/style_zoom,{135,119,90,int(li)==active?28+int(l.wear%20):15+int(l.wear%13)},anchor);
        for(size_t li=0;li<layers.size();++li)if(int(li)!=active){const auto& l=layers[li];bool near=std::abs(l.anchor-anchor)<=6;floor(l,near?38:27);for(const auto& ring:l.rings)for(size_t k=0;k<ring.size();++k)line({ring[k],ring[(k+1)%ring.size()]},.7f/style_zoom,{213,203,177,near?62:49},l.anchor);}
        for(const auto& l:cut.Get(active,hatch_lod,layers[active].walls))line(l,.72f/style_zoom,{166,160,143,23+int(l.wear%30)},anchor);
        floor(layers[active],255);primitive_count=std::max(primitive_count,p.size());return p;
    }
    Json Bake(int active){
        int levels=1;while(std::max(transform.width,transform.height)/std::pow(2,levels-1)>Tile)++levels;
        int rules=int(feature.value("reveal_regions",Json::array()).size());if(rules>3)throw std::runtime_error("parity reveal variant bound");bool always=feature.value("always_visible",false);
        Json groups=Json::array();
        for(int shaded=0;shaded<2;++shaded){
            std::map<int,size_t> group_ids;
            for(int mask=-1;mask<(always?0:1<<rules);++mask){Json yes=Json::array(),no=Json::array();if(mask>=0)for(int i=0;i<rules;++i)((mask&(1<<i))?yes:no).push_back(i);group_ids[mask]=groups.size();groups.push_back({{"requires",yes},{"forbids",no},{"fog_mode",always?"any":mask<0?"off":"on"},{"shaded",shaded},{"tiles",Json::array()}});}
            for(int level=0;level<levels;++level){auto primitives=Primitives(active,level,shaded!=0);double factor=std::ldexp(1.,-level);int nx=int(std::ceil(transform.width*factor/Tile)),ny=int(std::ceil(transform.height*factor/Tile));std::map<std::pair<int,int>,std::vector<size_t>> buckets;
                for(size_t i=0;i<primitives.size();++i){const auto& p=primitives[i];double x0=1e30,y0=x0,x1=-x0,y1=-x0;for(int k=0;k<(p.stroke?2:3);++k){auto v=transform.Image(p.v[k*2],p.v[k*2+1]);x0=std::min(x0,v[0]*factor);y0=std::min(y0,v[1]*factor);x1=std::max(x1,v[0]*factor);y1=std::max(y1,v[1]*factor);}double pad=Gutter+1+(p.stroke?p.width*transform.ppu*factor*.5:0);
                    int ax=std::max(0,int(std::floor((x0-pad)/Tile))),bx=std::min(nx-1,int(std::floor((x1+pad)/Tile))),ay=std::max(0,int(std::floor((y0-pad)/Tile))),by=std::min(ny-1,int(std::floor((y1+pad)/Tile)));for(int x=ax;x<=bx;++x)for(int y=ay;y<=by;++y)buckets[{x,y}].push_back(i);
                }
                for(const auto& [tile,ids]:buckets){std::map<std::vector<size_t>,Json> reused;
                    for(const auto& [mask,gi]:group_ids){std::vector<size_t> visible;for(size_t id:ids)if(Visible(primitives[id].required,mask))visible.push_back(id);if(visible.empty())continue;Json record;
                        auto old=reused.find(visible);if(old!=reused.end())record=old->second;else{Raster r;r.transform=transform;r.level=level;r.tx=tile.first;r.ty=tile.second;r.texture=&parchment;r.material_x=float((bounds[0]+bounds[2])*.5);r.material_z=float((bounds[1]+bounds[3])*.5);r.material_span=float(std::max(bounds[2]-bounds[0],bounds[3]-bounds[1]));for(size_t id:visible)r.Draw(primitives[id]);bool occupied=false;for(size_t at=3;at<r.pixels.size();at+=4)if(r.pixels[at]){occupied=true;break;}if(!occupied)continue;std::string file=Store(r.pixels);record={{"lod",level},{"x",tile.first},{"y",tile.second},{"file",file},{"sha256",fs::path(file).stem().string()}};reused.emplace(std::move(visible),record);}
                        groups[gi]["tiles"].push_back(record);
                    }
                }
            }
        }
        return {{"kind","composite"},{"ppu",transform.ppu},{"levels",levels},{"width",transform.width},{"height",transform.height},{"world_to_image",{transform.ppu,0,-bounds[0]*transform.ppu,0,-transform.ppu,bounds[3]*transform.ppu}},{"groups",groups},{"detail_tier","parity-"+std::to_string(int(transform.ppu))}};
    }
    Json Lines(int active){Json lines=Json::array(),cells=Json::array();std::map<std::pair<int,int>,std::vector<int>> grid;auto add=[&](int kind,BbAtlasStyle::Line l){if(std::hypot(l.b.x-l.a.x,l.b.z-l.a.z)<1e-8)return;int id=int(lines.size());auto required=BoxRequirements(feature,std::min(l.a.x,l.b.x),std::min(l.a.z,l.b.z),std::max(l.a.x,l.b.x),std::max(l.a.z,l.b.z),layers[active].anchor);lines.push_back({kind,{l.a.x,l.a.z,l.b.x,l.b.z},required});int x0=int(std::floor(std::min(l.a.x,l.b.x)/32)),x1=int(std::floor(std::max(l.a.x,l.b.x)/32)),z0=int(std::floor(std::min(l.a.z,l.b.z)/32)),z1=int(std::floor(std::max(l.a.z,l.b.z)/32));for(int x=x0;x<=x1;++x)for(int z=z0;z<=z1;++z)grid[{x,z}].push_back(id);};
        for(const auto& ring:layers[active].rings)for(size_t k=0;k<ring.size();++k)add(1,{ring[k],ring[(k+1)%ring.size()]});for(auto l:layers[active].walls)add(0,l);if(lines.size()>8192||grid.size()>16384)throw std::runtime_error("bounded line overlay exceeds budget");
        for(const auto& [key,ids]:grid)cells.push_back({key.first,key.second,ids});Json j={{"schema",1},{"cell",32},{"lines",lines},{"cells",cells}};std::string file="lines/F"+std::to_string(active)+".json";WriteJson(out/file,j);return {{"file",file},{"sha256",Hash(Read(out/file,8*1024*1024))},{"count",lines.size()}};
    }
};
int main(int argc,char**argv){try{
    if(argc!=10)throw std::runtime_error("usage: parity-bake source features base-manifest output AreaNN ppu layers-csv art identity");
    auto started=std::chrono::steady_clock::now();Json map=ReadJson(argv[1]),features=ReadJson(argv[2]),manifest=ReadJson(argv[3]);std::string label=argv[5],region=map.at("id");fs::path out=argv[4];double ppu=std::stod(argv[6]);if(ppu!=8&&ppu!=16&&ppu!=32)throw std::runtime_error("unsupported quality tier");
    // Wrapper creates a real copied baseline: never edit linked source metadata.
    if(!fs::exists(out/"grid.json")||!fs::exists(out/"manifest.json"))throw std::runtime_error("copied baseline required");
    if(manifest.at("region_id")!=region||manifest.at("source_sha256").get<std::string>()!=Hash(Read(argv[1])))throw std::runtime_error("baseline geometry identity mismatch");
    if(manifest.at("schema")==1){auto rebase=[](Json& view,std::string prefix){for(auto& group:view["groups"])for(auto& t:group["tiles"])t["file"]=prefix+t["file"].get<std::string>();view["kind"]="legacy";};rebase(manifest["context"],"context/");for(size_t i=0;i<manifest["views"].size();++i)rebase(manifest["views"][i],"F"+std::to_string(i)+"/");}
    Baker baker(out,map,features.at("areas").at(region),argv[8],ppu);std::cout<<label<<" topology_ready holes="<<baker.interiors.holes<<" rejected="<<baker.interiors.rejected<<" budget_skips="<<baker.interiors.budget_skips<<"\n"<<std::flush;
    std::set<int> selected;std::istringstream list(argv[7]);std::string value;while(std::getline(list,value,','))selected.insert(std::stoi(value));Json coverage=Json::array();
    for(int active:selected){if(active<0||active>=int(baker.layers.size()))throw std::runtime_error("layer index");auto view=baker.Bake(active);view["line_overlay"]=baker.Lines(active);manifest["views"][active]=std::move(view);coverage.push_back(active);std::cout<<label<<" parity_floor="<<active<<" ppu="<<ppu<<" unique_new_bytes="<<baker.new_bytes<<"\n"<<std::flush;}
    manifest["schema"]=2;manifest["parity_generator_identity"]=argv[9];manifest["parity_shading_variants"]={"on","off"};manifest["parity_coverage"]=coverage;manifest["parity_limits"]={"Hatch/context outline style is calibrated to normalized zoom 9 per raster LOD; max-zoom style still needs review","Dynamic glyph-footprint hatch masking is not yet implemented","CPU raster edge coverage can differ from native reference"};
    manifest["parity_bake_seconds"]=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();manifest["parity_new_object_bytes"]=baker.new_bytes;manifest["parity_new_objects"]=baker.new_objects;manifest["parity_peak_primitive_count"]=baker.primitive_count;WriteJson(out/"manifest.json",manifest);
    std::cout<<label<<" PARITY_CPU_READY seconds="<<manifest["parity_bake_seconds"]<<" bytes="<<baker.new_bytes<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<"PARITY_BAKE_FAIL "<<e.what()<<"\n";return 1;}}
