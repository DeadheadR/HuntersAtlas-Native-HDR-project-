// SPDX-License-Identifier: GPL-2.0-or-later
#include "core.h"
#include <iostream>
#include <functional>
#include <set>
#include <chrono>
using namespace Atlas2;
void Check(bool b,const char* e){if(!b)throw std::runtime_error(e);}
void Reject(const std::function<void()>& f){bool caught=false;try{f();}catch(...){caught=true;}Check(caught,"expected rejection");}
// Literal V1 float algorithm, independently retained for conformance.
int Reference(const Grid& g,float x,float y,float z){int nearest=-1,local=-1;float distance=INFINITY,local_distance=INFINITY;size_t t=0;
    for(size_t i=0;i<g.anchors.size();++i){float d=std::abs(y-g.anchors[i]);if(d<distance){distance=d;nearest=int(i);}while(t<g.surfaces.size()&&g.surfaces[t].layer==int(i)){const auto& s=g.surfaces[t++];auto&v=s.v;
        if(x<std::min({v[0],v[2],v[4]})||x>std::max({v[0],v[2],v[4]})||z<std::min({v[1],v[3],v[5]})||z>std::max({v[1],v[3],v[5]}))continue;
        auto cross=[&](int u,int w){return(v[w]-v[u])*(z-v[u+1])-(v[w+1]-v[u+1])*(x-v[u]);};float ab=cross(0,2),bc=cross(2,4),ca=cross(4,0);if(!((ab>=-.0001f&&bc>=-.0001f&&ca>=-.0001f)||(ab<=.0001f&&bc<=.0001f&&ca<=.0001f)))continue;
        float den=(v[3]-v[5])*(v[0]-v[4])+(v[4]-v[2])*(v[1]-v[5]);if(std::abs(den)<1e-8f)continue;float a=((v[3]-v[5])*(x-v[4])+(v[4]-v[2])*(z-v[5]))/den,b=((v[5]-v[1])*(x-v[4])+(v[0]-v[4])*(z-v[5]))/den,c=1-a-b,h=a*s.y[0]+b*s.y[1]+c*s.y[2];if(!std::isfinite(h))continue;d=std::abs(y-h);if(d<local_distance){local_distance=d;local=int(i);}
    }}return local>=0?local:nearest;}
int main(int argc,char**argv){try{
    Check(argc==3,"usage: core-test packs output-json");Transform tr{-500,800,8,16000,12000};tr.Validate();for(auto p:std::vector<std::array<double,2>>{{-600,900},{-500,800},{1.234,-5.678},{1500,-700}}){auto uv=tr.Image(p[0],p[1]),w=tr.World(uv[0],uv[1]);Check(std::abs(w[0]-p[0])<1e-10&&std::abs(w[1]-p[1])<1e-10,"roundtrip");}Check(tr.Image(-499,801)==std::array<double,2>{8,-8},"orientation");Reject([&](){auto bad=tr;bad.ppu=-1;bad.Validate();});Check(Lod(9,8,8)==0&&Lod(.15,8,8)==5,"LOD");Reject([](){Lod(0,8,8);});
    std::vector<unsigned char> pixels(TileBytes,123);auto b=Encode(pixels);Check(Decode(b,Hash(b))==pixels,"tile roundtrip");auto bad=b;bad.back()^=1;Reject([&](){Decode(bad,Hash(b));});bad=b;bad[4]=0;Reject([&](){Decode(bad,Hash(bad));});bad=b;bad.push_back(0);Reject([&](){Decode(bad,Hash(bad));});Reject([](){Read("missing-Area00.a2t");});
    Grid synthetic;synthetic.anchors={0,4};synthetic.surfaces={{{0,0,4,0,0,4},{0,4,0},0},{{0,0,4,0,0,4},{2,2,2},1}};synthetic.Build();Check(synthetic.Select(1,1.1f,1)==0,"stair");Check(synthetic.Select(1,1.6f,1)==1,"bridge");Check(synthetic.Select(1,1.6f,1,0,.35f)==0,"hysteresis");Check(synthetic.Select(1,1.6f,1,-1,0,0)==0,"manual");Check(synthetic.Select(100,4,100)==1,"offmap fallback");Check(synthetic.Select(NAN,0,0)==-1,"nonfinite pose");
    Json report={{"schema",1},{"synthetic_pass",true},{"areas",Json::array()},{"native_gameplay_tested",false},{"finite_anchor_sample",true}};size_t total=0,layers=0,tiles=0;double max_roundtrip=0;
    auto index=ReadJson(fs::path(argv[1])/"atlas2-index.json");for(const auto& row:index.at("areas")){auto area=fs::path(argv[1])/row.at("area").get<std::string>();auto raw=Read(area/"manifest.json");Check(Hash(raw)==row.at("manifest_sha256").get<std::string>(),"manifest hash");auto m=Json::parse(raw);raw=Read(area/"grid.json");Check(Hash(raw)==m.at("grid_sha256").get<std::string>(),"grid hash");Grid g;g.FromJson(Json::parse(raw));Transform t{m["bounds"][0],m["bounds"][3],m["ppu"],m["width"],m["height"]};t.Validate();size_t anchors=0,layer_count=0;std::vector<std::array<double,3>> anchor_rows;auto start=std::chrono::steady_clock::now();
        for(size_t li=0;li<g.anchors.size();++li){std::vector<size_t> ids;for(size_t i=0;i<g.surfaces.size();++i)if(g.surfaces[i].layer==int(li))ids.push_back(i);if(ids.empty())continue;++layer_count;
            for(size_t i:std::set<size_t>{ids.front(),ids[ids.size()/2],ids.back()}){const auto&s=g.surfaces[i];for(int k=-1;k<3;++k){float x=k<0?(s.v[0]+s.v[2]+s.v[4])/3:s.v[k*2],z=k<0?(s.v[1]+s.v[3]+s.v[5])/3:s.v[k*2+1],y=k<0?(s.y[0]+s.y[1]+s.y[2])/3:s.y[k];
                for(float dy:{0.f,.1f,-.1f}){Check(g.Select(x,y+dy,z)==Reference(g,x,y+dy,z),"V1 layer disagreement");++anchors;}auto uv=t.Image(x,z),w=t.World(uv[0],uv[1]);double delta=std::hypot(w[0]-x,w[1]-z);Check(delta<1e-8,"area roundtrip");max_roundtrip=std::max(max_roundtrip,delta);anchor_rows.push_back({x,y,z});}
            }
        }
        size_t checked_tiles=0;auto validate=[&](const Json& v,fs::path base){for(const auto& group:v.at("groups"))for(const auto& tile:group.at("tiles")){auto data=Read(base/tile.at("file").get<std::string>(),TileBytes+1024);Check(Decode(data,tile.at("sha256").get<std::string>()).size()==TileBytes,"tile decode");++checked_tiles;}};
        validate(m.at("context"),area/"context");for(size_t i=0;i<m.at("views").size();++i)validate(m["views"][i],area/("F"+std::to_string(i)));
        WriteJson(area/"anchors.json",{{"schema",1},{"area",m.at("area")},{"native_teleport_targets",false},{"poses",anchor_rows}});
        report["areas"].push_back({{"area",m.at("area")},{"layers",g.anchors.size()},{"layers_with_anchors",layer_count},{"comparison_poses",anchors},{"tiles_verified",checked_tiles},{"candidate_bound",g.max_candidates},{"offline_seconds",std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()}});total+=anchors;layers+=layer_count;tiles+=checked_tiles;
    }
    report["comparison_poses"]=total;report["layers_with_anchors"]=layers;report["tiles_verified"]=tiles;report["max_roundtrip_world_delta"]=max_roundtrip;report["cache_pixel_byte_bound"]=CacheSlots*TileBytes;report["pass"]=true;WriteJson(argv[2],report);std::cout<<"ATLAS2_OFFLINE_PASS areas="<<index["areas"].size()<<" layers="<<layers<<" comparison_poses="<<total<<" tiles="<<tiles<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<"ATLAS2_TEST_FAIL "<<e.what()<<"\n";return 1;}}
