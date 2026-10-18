// SPDX-License-Identifier: GPL-2.0-or-later
#include "measure.h"
#include <iostream>
#include <limits>
int main(){try{
    _putenv_s("BB_ATLAS2_MEASURE","1");Atlas2Measure::Recorder r;
    r.Start("unsafe label");if(r.active)throw 1;
    r.Start("warm_static");if(!r.active||r.generation!=1)throw 2;
    r.Add(r.present_ms,-1);r.Add(r.present_ms,std::numeric_limits<double>::infinity());if(!r.present_ms.empty())throw 3;
    r.Present();if(r.present_ms.size()!=1||r.present_ms[0]<0)throw 4;
    for(size_t n=0;n<r.Limit+1;++n)r.Add(r.map_cpu_ms,2);if(!r.overflow||r.map_cpu_ms.size()!=r.Limit)throw 5;
    r.Start("cold_reference");if(r.overflow||!r.present_ms.empty()||!r.map_cpu_ms.empty()||r.generation!=2)throw 6;
    r.active=false;r.Present();if(!r.present_ms.empty())throw 7;
    if(r.Result()["gpu_timestamp_measured"]!=false)throw 8;
    std::cout<<"MEASUREMENT_COUNTER_PASS bounded_samples="<<r.Limit<<"\n";return 0;
}catch(...){std::cout<<"MEASUREMENT_COUNTER_FAIL\n";return 1;}}
