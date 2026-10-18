// SPDX-License-Identifier: GPL-2.0-or-later
#include "../native/src/runtime_map.h"
#include "../native/src/runtime_atlas_state.h"
#include "../native/src/runtime_menu_sound.h"
extern "C" int runtime_map_menu_state(BbMapMenu* out){*out={1,runtime_map_menu_open(),3};return 1;}
extern "C" uint32_t runtime_map_confirm_button(){return 0x4000;}
extern "C" int runtime_atlas_flag(uint32_t){return -1;}
extern "C" uintptr_t runtime_atlas_player_token(){return 1;}
extern "C" int runtime_atlas_travel_request(const BbAtlasTravelDestination*){return 0;}
extern "C" int runtime_atlas_travel_status(){return 0;}
extern "C" int runtime_atlas_travel_supported(){return 1;}
extern "C" void runtime_audio_menu_stats(BbMenuSoundStats* out){*out={};}
extern "C" void runtime_audio_menu_event(int){}
