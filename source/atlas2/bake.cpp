// SPDX-License-Identifier: GPL-2.0-or-later
// Offline only. No game process, memory access or GPU API.
#include "core.h"
#include <iostream>
#include <chrono>
#include <set>
using namespace Atlas2;
struct Primitive {std::array<float,6> v;std::array<float,3> shade;std::array<int,3> rgb{204,202,200};int alpha=255;std::string signature;};
struct Raster {
    Transform tr;int lod=0,tx=0,ty=0;std::vector<unsigned char> pixels=std::vector<unsigned char>(TileBytes);
    void Triangle(const Primitive& t){
        std::array<double,6> v;double factor=std::ldexp(1.,-lod);for(int k=0;k<3;++k){auto p=tr.Image(t.v[2*k],t.v[2*k+1]);v[2*k]=p[0]*factor-tx*Tile+Gutter;v[2*k+1]=p[1]*factor-ty*Tile+Gutter;}
        double d=(v[3]-v[5])*(v[0]-v[4])+(v[4]-v[2])*(v[1]-v[5]);if(std::abs(d)<1e-12)return;
        int x0=std::max(0,int(std::floor(std::min({v[0],v[2],v[4]})))),x1=std::min(Dimension-1,int(std::ceil(std::max({v[0],v[2],v[4]}))));
        int y0=std::max(0,int(std::floor(std::min({v[1],v[3],v[5]})))),y1=std::min(Dimension-1,int(std::ceil(std::max({v[1],v[3],v[5]}))));
        for(int y=y0;y<=y1;++y)for(int x=x0;x<=x1;++x){double px=x+.5,py=y+.5;double a=((v[3]-v[5])*(px-v[4])+(v[4]-v[2])*(py-v[5]))/d,b=((v[5]-v[1])*(px-v[4])+(v[0]-v[4])*(py-v[5]))/d,c=1-a-b;if(a<0||b<0||c<0)continue;
            float tint=float(a*t.shade[0]+b*t.shade[1]+c*t.shade[2]);size_t at=(y*Dimension+x)*4;
            float sa=t.alpha/255.f,da=pixels[at+3]/255.f,oa=sa+da*(1-sa);if(oa==0)continue;
            for(int k=0;k<3;++k)pixels[at+k]=uint8_t(std::clamp((t.rgb[k]*tint*sa+pixels[at+k]*da*(1-sa))/oa,0.f,255.f));pixels[at+3]=uint8_t(oa*255+.5f);
        }
    }
};
static std::string Signature(const Json& feature,const std::vector<std::array<float,3>>& pts,std::map<std::string,Json>& signatures){
    std::set<int>s;for(auto p:pts){int r=Region(feature,p[0],p[1],p[2]);if(r!=-2)s.insert(r);}std::string key;Json ids=Json::array();for(int r:s){key+=std::to_string(r)+",";ids.push_back(r);}if(key.empty())key="always";signatures[key]=ids;return key;
}
static void Line(std::vector<Primitive>& out,float x0,float z0,float x1,float z1,float width,int alpha,std::array<int,3>rgb,std::string signature){float dx=x1-x0,dz=z1-z0,n=std::hypot(dx,dz);if(n<1e-8)return;float ox=-dz/n*width*.5f,oz=dx/n*width*.5f;
    out.push_back({{x0+ox,z0+oz,x1+ox,z1+oz,x0-ox,z0-oz},{1,1,1},rgb,alpha,signature});out.push_back({{x1+ox,z1+oz,x1-ox,z1-oz,x0-ox,z0-oz},{1,1,1},rgb,alpha,signature});}
static Json BakeView(const fs::path& dest,const std::vector<Primitive>& primitives,Transform tr,int levels,const std::map<std::string,Json>& signatures){
    Json view={{"groups",Json::array()}};int group=0;
    for(const auto& [signature,requirements]:signatures){
        std::vector<size_t> indices;for(size_t i=0;i<primitives.size();++i)if(primitives[i].signature==signature)indices.push_back(i);if(indices.empty())continue;
        std::string groupName="S"+std::to_string(group++);Json g={{"requires",requirements},{"tiles",Json::array()}};
        for(int level=0;level<levels;++level){double factor=std::ldexp(1.,-level);std::map<std::pair<int,int>,std::vector<size_t>> buckets;
            int nx=int(std::ceil(tr.width*factor/Tile)),ny=int(std::ceil(tr.height*factor/Tile));
            for(auto index:indices){const auto& v=primitives[index].v;double x0=1e30,y0=x0,x1=-x0,y1=-x0;for(int k=0;k<3;++k){auto p=tr.Image(v[2*k],v[2*k+1]);x0=std::min(x0,p[0]*factor);y0=std::min(y0,p[1]*factor);x1=std::max(x1,p[0]*factor);y1=std::max(y1,p[1]*factor);}
                int ax=std::max(0,int(std::floor((x0-Gutter)/Tile))),bx=std::min(nx-1,int(std::floor((x1+Gutter)/Tile))),ay=std::max(0,int(std::floor((y0-Gutter)/Tile))),by=std::min(ny-1,int(std::floor((y1+Gutter)/Tile)));
                for(int x=ax;x<=bx;++x)for(int y=ay;y<=by;++y)buckets[{x,y}].push_back(index);
            }
            for(const auto& [tile,items]:buckets){Raster r;r.tr=tr;r.lod=level;r.tx=tile.first;r.ty=tile.second;for(auto i:items)r.Triangle(primitives[i]);
                bool nonempty=false;for(size_t i=3;i<r.pixels.size();i+=4)if(r.pixels[i]){nonempty=true;break;}if(!nonempty)continue;
                std::string name=groupName+"/L"+std::to_string(level)+"/"+std::to_string(tile.first)+"_"+std::to_string(tile.second)+".a2t";auto bytes=Encode(r.pixels);Write(dest/name,bytes);g["tiles"].push_back({{"lod",level},{"x",tile.first},{"y",tile.second},{"file",name},{"sha256",Hash(bytes)}});
            }
        }view["groups"].push_back(std::move(g));
    }return view;
}
int main(int argc,char**argv){try{
    if(argc!=7)throw std::runtime_error("usage: bake source-json features-json output-area AreaNN ppu source-identity");
    auto start=std::chrono::steady_clock::now();fs::path source=argv[1],dest=argv[3];if(fs::exists(dest))throw std::runtime_error("output must be fresh");
    auto map=ReadJson(source),features=ReadJson(argv[2]);std::string id=map.at("id"),label=argv[4];Json feature=features.at("areas").at(id);
    auto bounds=map.at("bounds").get<std::array<double,4>>();double ppu=std::stod(argv[5]);Transform tr{bounds[0],bounds[3],ppu,int(std::ceil((bounds[2]-bounds[0])*ppu)),int(std::ceil((bounds[3]-bounds[1])*ppu))};tr.Validate();
    Grid grid;std::vector<std::vector<Primitive>> floors;std::vector<Primitive> context;std::map<std::string,Json> signatures;Json layers=Json::array();double largest=0;int primary=-1;
    for(size_t li=0;li<map.at("layers").size();++li){const auto& l=map["layers"][li];float anchor=l.at("anchor");grid.anchors.push_back(anchor);floors.emplace_back();float lo=anchor,hi=anchor;
        for(const auto& h:l.at("heights"))for(auto y:h){lo=std::min(lo,y.get<float>());hi=std::max(hi,y.get<float>());}double footprint=0;
        for(size_t i=0;i<l.at("triangles").size();++i){Surface s{l["triangles"][i].get<std::array<float,6>>(),l["heights"][i].get<std::array<float,3>>(),int(li)};grid.surfaces.push_back(s);const auto&v=s.v;
            float minx=std::min({v[0],v[2],v[4]}),minz=std::min({v[1],v[3],v[5]}),maxx=std::max({v[0],v[2],v[4]}),maxz=std::max({v[1],v[3],v[5]});
            std::vector<std::array<float,3>>pts={{{(v[0]+v[2]+v[4])/3,(s.y[0]+s.y[1]+s.y[2])/3,(v[1]+v[3]+v[5])/3}},{{v[0],s.y[0],v[1]}},{{v[2],s.y[1],v[3]}},{{v[4],s.y[2],v[5]}},{{minx,anchor,minz}},{{maxx,anchor,maxz}},{{(minx+maxx)/2,anchor,(minz+maxz)/2}}};
            std::array<float,3>shade;for(int k=0;k<3;++k)shade[k]=(118+120*std::clamp((s.y[k]-lo)/std::max(.01f,hi-lo),0.f,1.f))/255.f;
            Primitive p{v,shade,{242,240,238},255,Signature(feature,pts,signatures)};floors.back().push_back(p);p.alpha=27;context.push_back(p);
            footprint+=std::abs((v[2]-v[0])*(v[5]-v[1])-(v[4]-v[0])*(v[3]-v[1]))*.5;
        }
        for(const auto& ring:l.at("outlines"))for(size_t i=0;i<ring.size();++i){const auto&a=ring[i],b=ring[(i+1)%ring.size()];float x0=a[0],z0=a[1],x1=b[0],z1=b[1];auto sig=Signature(feature,{{{std::min(x0,x1),anchor,std::min(z0,z1)}},{{std::max(x0,x1),anchor,std::max(z0,z1)}},{{(x0+x1)/2,anchor,(z0+z1)/2}}},signatures);Line(floors.back(),x0,z0,x1,z1,.12f,220,{204,193,163},sig);Line(context,x0,z0,x1,z1,.10f,49,{213,203,177},sig);}
        for(const auto& w:l.at("walls")){float x0=w[0],z0=w[1],x1=w[2],z1=w[3];auto sig=Signature(feature,{{{std::min(x0,x1),anchor,std::min(z0,z1)}},{{std::max(x0,x1),anchor,std::max(z0,z1)}},{{(x0+x1)/2,anchor,(z0+z1)/2}}},signatures);Line(floors.back(),x0,z0,x1,z1,.32f,255,{15,18,19},sig);}
        layers.push_back({{"height",l.at("height")},{"span",l.at("span")},{"anchor",anchor},{"footprint",footprint}});if(footprint>largest){largest=footprint;primary=int(li);}
    }
    grid.Build();WriteJson(dest/"grid.json",grid.ToJson());int levels=1;while(std::max(tr.width,tr.height)/std::pow(2,levels-1)>Tile)++levels;
    Json manifest={{"schema",1},{"area",label},{"region_id",id},{"source_sha256",Hash(Read(source))},{"feature_sha256",Hash(Read(argv[2]))},{"generator_identity",argv[6]},{"bounds",bounds},{"valid_extent",bounds},{"units","native-game-world-units"},{"vertical_axis","Y"},{"horizontal_axes",{"X","Z"}},{"orientation","+X right, +Z up"},{"world_to_image",{ppu,0,-bounds[0]*ppu,0,-ppu,bounds[3]*ppu}},{"width",tr.width},{"height",tr.height},{"ppu",ppu},{"tile_size",Tile},{"gutter",Gutter},{"levels",levels},{"primary",primary},{"layers",layers},{"grid_sha256",Hash(Read(dest/"grid.json"))},{"grid_max_candidates",grid.max_candidates},{"context",BakeView(dest/"context",context,tr,levels,signatures)},{"views",Json::array()}};
    size_t tiles=0;for(size_t i=0;i<floors.size();++i){auto v=BakeView(dest/("F"+std::to_string(i)),floors[i],tr,levels,signatures);manifest["views"].push_back(v);}
    for(const auto& g:manifest["context"]["groups"])tiles+=g["tiles"].size();for(const auto& v:manifest["views"])for(const auto& g:v["groups"])tiles+=g["tiles"].size();
    manifest["tile_count"]=tiles;manifest["bake_seconds"]=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();WriteJson(dest/"manifest.json",manifest);
    std::cout<<label<<" layers="<<layers.size()<<" triangles="<<grid.surfaces.size()<<" tiles="<<tiles<<" candidate_bound="<<grid.max_candidates<<" seconds="<<manifest["bake_seconds"]<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<"ATLAS2_BAKE_ERROR: "<<e.what()<<"\n";return 1;}}
