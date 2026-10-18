#include "parity_style.h"
#include <iostream>
using namespace Atlas2Parity;
void Check(bool ok){static int test=0;++test;if(!ok)throw std::runtime_error("parity style regression at check "+std::to_string(test));}
int main(){try{
    Check(HeightTint(0,0,10,255,true)==std::array<int,4>{122,120,118,255});Check(HeightTint(10,0,10,38,true)==std::array<int,4>{242,240,238,38});Check(HeightTint(10,0,10,255,false)==std::array<int,4>{208,206,204,255});
    Check(std::abs(WallWidth(37.5f,1.5f)-4.875f)<1e-5f);Check(WallWidth(.225f,1.5f)==3.75f);Check(std::abs(OutlineWidth(1.5f)-1.275f)<1e-5f);Check(!Visible({-1},0)&&!Visible({0},0)&&Visible({0},1)&&Visible({-1},-1));
    Raster r;r.transform={0,256,1,256,256};Primitive a,b;a.v={0,256,16,256,16,240};b.v={0,256,16,240,0,240};for(auto* p:{&a,&b})p->color={std::array<int,4>{120,120,120,128},std::array<int,4>{120,120,120,128},std::array<int,4>{120,120,120,128}};r.Draw(a);r.Draw(b);
    for(int y=Gutter;y<Gutter+16;++y)for(int x=Gutter;x<Gutter+16;++x)Check(r.pixels[(y*Dimension+x)*4+3]==128);
    std::cout<<"PARITY_STYLE_PASS shared_edge_pixels=256\n";return 0;
}catch(const std::exception& e){std::cout<<"PARITY_STYLE_FAIL "<<e.what()<<"\n";return 1;}}
