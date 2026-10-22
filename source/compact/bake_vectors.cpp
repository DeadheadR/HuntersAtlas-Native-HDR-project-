// SPDX-License-Identifier: GPL-2.0-or-later
// Offline compiler. Topology and decorative strokes are never built in game.
#include "parity_style.h"
#include <iostream>
#include <cstring>
using namespace Atlas2Parity;
struct Vertex {float x,z,u,v;uint32_t colour;};
struct Mesh {
 std::vector<Vertex> vertices;std::vector<uint32_t> indices;Json groups=Json::array();
 void Group(std::vector<int> required,uint32_t count){if(!count)return;if(!groups.empty()&&groups.back()[2]==required){groups.back()[1]=groups.back()[1].get<uint32_t>()+count;}else groups.push_back({uint32_t(indices.size())-count,count,required});}
 void Triangle(std::array<float,6> v,std::array<float,3> y,std::vector<int> required){uint32_t base=uint32_t(vertices.size());for(int k=0;k<3;++k)vertices.push_back({v[k*2],-v[k*2+1],y[k],0,0xffffffffu});for(int k=0;k<3;++k)indices.push_back(base+k);Group(std::move(required),3);}
 void Line(BbAtlasStyle::Line line,std::vector<int> required,int wear1=0,int wear2=0){
  const float dx=line.b.x-line.a.x,dz=-(line.b.z-line.a.z),length=std::hypot(dx,dz);if(length<1e-8)return;
  const float nx=-dz/length,nz=dx/length;uint32_t base=uint32_t(vertices.size());
  for(auto p:{line.a,line.b})for(int k=0;k<4;++k){float sign=k<2?1.f:-1.f;uint32_t alpha=(k==0||k==3)?0:255;vertices.push_back({p.x,-p.z,sign*nx,sign*nz,uint32_t(wear1)|(uint32_t(wear2)<<8)|(alpha<<24)});}
  for(int k=0;k<3;++k)for(int i:{k,k+4,k+5,k,k+5,k+1})indices.push_back(base+i);Group(std::move(required),18);
 }
 Json Pack(){std::vector<uint8_t> v(vertices.size()*sizeof(Vertex)),i(indices.size()*4);if(!v.empty())std::memcpy(v.data(),vertices.data(),v.size());if(!i.empty())std::memcpy(i.data(),indices.data(),i.size());return {{"vertices",Json::binary(v)},{"indices",Json::binary(i)},{"groups",groups}};}
};
void Store(fs::path path,const Json& value){auto raw=Json::to_msgpack(value);uLongf size=compressBound(uLong(raw.size()));std::vector<unsigned char> data={'A','3','Z','1'};U32(data,uint32_t(raw.size()));data.resize(size+8);if(compress2(data.data()+8,&size,raw.data(),uLong(raw.size()),9)!=Z_OK)throw std::runtime_error("compression");data.resize(size+8);Write(path,data);}
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("usage source features baseline-manifest output");
 auto source=ReadJson(argv[1]),rules=ReadJson(argv[2]).at("areas").at(source.at("id").get<std::string>()),old=ReadJson(argv[3]);fs::path out=argv[4];fs::create_directories(out);
 std::vector<BbAtlasStyle::Triangle> all;std::vector<BbAtlasStyle::FloorIndex> per;std::vector<std::vector<BbAtlasInteriors::Ring>> rings;std::vector<std::vector<BbAtlasStyle::Line>> walls;
 Json base={{"schema",1},{"layers",Json::array()}};
 for(size_t li=0;li<source["layers"].size();++li){const auto& layer=source["layers"][li];const float anchor=layer.at("anchor");Mesh floors,outlines,wall;std::vector<BbAtlasStyle::Triangle> tris;std::vector<BbAtlasInteriors::Ring> rs;std::vector<BbAtlasStyle::Line> ws;float low=anchor,high=anchor;
  for(size_t i=0;i<layer["triangles"].size();++i){auto v=layer["triangles"][i].get<std::array<float,6>>();auto y=layer["heights"][i].get<std::array<float,3>>();for(auto h:y){low=std::min(low,h);high=std::max(high,h);}float x0=std::min({v[0],v[2],v[4]}),z0=std::min({v[1],v[3],v[5]}),x1=std::max({v[0],v[2],v[4]}),z1=std::max({v[1],v[3],v[5]});floors.Triangle(v,y,Requirements(rules,{{(v[0]+v[2]+v[4])/3,(y[0]+y[1]+y[2])/3,(v[1]+v[3]+v[5])/3},{v[0],y[0],v[1]},{v[2],y[1],v[3]},{v[4],y[2],v[5]},{x0,anchor,z0},{x1,anchor,z1},{(x0+x1)*.5f,anchor,(z0+z1)*.5f}}));tris.push_back({{{{v[0],v[1]},{v[2],v[3]},{v[4],v[5]}}}});}
  auto req=[&](BbAtlasStyle::Line l){return BoxRequirements(rules,std::min(l.a.x,l.b.x),std::min(l.a.z,l.b.z),std::max(l.a.x,l.b.x),std::max(l.a.z,l.b.z),anchor);};
  for(const auto& ring:layer["outlines"]){BbAtlasInteriors::Ring r;for(auto p:ring)r.push_back({p[0],p[1]});for(size_t k=0;k<r.size();++k){BbAtlasStyle::Line l{r[k],r[(k+1)%r.size()]};outlines.Line(l,req(l));}rs.push_back(std::move(r));}
  for(auto w:layer["walls"]){BbAtlasStyle::Line l{{w[0],w[1]},{w[2],w[3]}};wall.Line(l,req(l));ws.push_back(l);}
  base["layers"].push_back({{"anchor",anchor},{"span",layer["span"]},{"low",low},{"high",high},{"floors",floors.Pack()},{"outlines",outlines.Pack()},{"walls",wall.Pack()}});
  all.insert(all.end(),tris.begin(),tris.end());per.emplace_back();per.back().Build(std::move(tris));rings.push_back(std::move(rs));walls.push_back(std::move(ws));
 }
 BbAtlasStyle::CutCache cut;cut.Build(std::move(all),rings.size());BbAtlasInteriors::Cache interiors;interiors.Build(rings,per);
 for(size_t li=0;li<rings.size();++li){Mesh fills;float y=base["layers"][li]["anchor"];for(auto t:interiors.layers[li]){auto p=t.p;fills.Triangle({p[0].x,p[0].z,p[1].x,p[1].z,p[2].x,p[2].z},{y,y,y},BoxRequirements(rules,std::min({p[0].x,p[1].x,p[2].x}),std::min({p[0].z,p[1].z,p[2].z}),std::max({p[0].x,p[1].x,p[2].x}),std::max({p[0].z,p[1].z,p[2].z}),y));}base["layers"][li]["interiors"]=fills.Pack();}
 Store(out/"base.a3z",base);base=nullptr;
 // The UI's supported normalized zoom is .15..25; corresponding hatch LODs 2..15.
 for(int lod=2;lod<=17;++lod){if(fs::exists(out/("hatch-"+std::to_string(lod)+".a3z")))continue;Json layers=Json::array();for(size_t li=0;li<rings.size();++li){Mesh hatch,interior;float y=source["layers"][li]["anchor"];auto req=[&](BbAtlasStyle::Line l){return BoxRequirements(rules,std::min(l.a.x,l.b.x),std::min(l.a.z,l.b.z),std::max(l.a.x,l.b.x),std::max(l.a.z,l.b.z),y);};for(auto l:cut.Get(li,lod,walls[li]))hatch.Line(l,req(l),23+l.wear%30,0);for(auto l:interiors.Get(li,lod))interior.Line(l,req(l),28+l.wear%20,15+l.wear%13);layers.push_back({{"cut",hatch.Pack()},{"interior",interior.Pack()}});cut.layers[li][lod].strokes.clear();interiors.hatches[li][lod].lines.clear();}Store(out/("hatch-"+std::to_string(lod)+".a3z"),{{"schema",1},{"layers",layers}});std::cout<<"BAKED_STYLE_LOD "<<lod<<"\n"<<std::flush;}
 Store(out/"grid.a3z",ReadJson(fs::path(argv[3]).parent_path()/"grid.json"));
 Json manifest={{"schema",4},{"region_id",source["id"]},{"bounds",source["bounds"]},{"primary",old["primary"]},{"layers",old["layers"]},{"files",Json::object()}};for(const auto& f:fs::directory_iterator(out))if(f.path().extension()==".a3z")manifest["files"][f.path().filename().string()]=Hash(Read(f.path(),512*1024*1024));WriteJson(out/"manifest.json",manifest);std::cout<<"COMPACT_VECTOR_AREA_READY\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
