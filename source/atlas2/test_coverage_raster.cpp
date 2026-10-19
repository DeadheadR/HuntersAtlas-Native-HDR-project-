// SPDX-License-Identifier: GPL-2.0-or-later
#include "coverage_raster.h"
#include <iostream>
using namespace Atlas2Coverage;
static void Check(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
static Primitive Triangle(float dx=0,float dy=0){Primitive p;p.v={2+dx,-(2+dy),26.4f+dx,-(27.6f+dy),26.4f+dx,-(28.413115f+dy)};for(auto& c:p.color)c={200,150,100,255};return p;}
static Raster Image(){Raster r;r.transform={0,0,1,512,256};return r;}
static double Alpha(const Raster& r){double result=0;for(size_t at=3;at<r.pixels.size();at+=4)result+=r.pixels[at]/255.;return result;}
int main(int argc,char**argv){try{
 Check(argc==2,"usage coverage-raster-test report");auto p=Triangle();Raster reference=Image();DrawTriangle(reference,p);auto projected=Project(reference,p);double area=std::abs((projected[1].x-projected[0].x)*(projected[2].y-projected[0].y)-(projected[1].y-projected[0].y)*(projected[2].x-projected[0].x))*.5;Check(std::abs(Alpha(reference)-area)<.15,"analytic area conservation");int recovered=0;
 for(int iy=0;iy<8;++iy)for(int ix=0;ix<8;++ix){auto q=Triangle(ix/8.f,iy/8.f);Raster old=Image(),fixed=Image();old.Draw(q);DrawTriangle(fixed,q);auto v=Project(fixed,q);int x=int(std::floor((v[0].x+v[1].x+v[2].x)/3)),y=int(std::floor((v[0].y+v[1].y+v[2].y)/3));size_t at=(y*Dimension+x)*4+3;Check(fixed.pixels[at]>0,"centroid pixel lost thin coverage");if(!old.pixels[at])++recovered;Check(std::abs(Alpha(fixed)-area)<.2,"translated area conservation");}
 Check(recovered>0,"synthetic fixture did not reproduce center-sampling gaps");auto seam=Triangle(245,20);Raster left=Image(),right=Image();right.tx=1;DrawTriangle(left,seam);DrawTriangle(right,seam);int seam_delta=0;for(int y=0;y<Dimension;++y)for(int x=0;x<4;++x)for(int k=0;k<4;++k)seam_delta=std::max(seam_delta,std::abs(int(left.pixels[(y*Dimension+256+x)*4+k])-int(right.pixels[(y*Dimension+x)*4+k])));Check(seam_delta<=1,"tile gutter coverage seam");
 Atlas2::WriteJson(argv[1],{{"schema",1},{"pass",true},{"synthetic_only",true},{"translation_cases",64},{"recovered_center_sample_gaps",recovered},{"minimum_altitude_pixels",MinimumAltitude(reference,p)},{"expected_area",area},{"integrated_alpha_area",Alpha(reference)},{"maximum_gutter_channel_delta",seam_delta}});std::cout<<"COVERAGE_RASTER_PASS translated=64 recovered="<<recovered<<" seam="<<seam_delta<<"\n";return 0;
}catch(const std::exception& e){std::cout<<"COVERAGE_RASTER_FAIL "<<e.what()<<"\n";return 1;}}
