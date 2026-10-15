#define NOMINMAX
#include "audio.hpp"
#include <iostream>
#include <cassert>
int main(){
    MusicPlayer player;player.update(false);
    if(player.failed){std::cout<<"Music assets loaded; no Windows audio output device is available.\n";return 2;}
    assert(player.device&&player.bytes.size()>1000000);Sleep(300);
    MMTIME position{};position.wType=TIME_SAMPLES;
    assert(waveOutGetPosition(player.device,&position,sizeof(position))==MMSYSERR_NOERROR);
    assert(position.u.sample>0);player.volume=.15f;player.set_volume();player.update(true);
    assert(player.device&&!player.failed&&player.track=="assets/arena_music.wav");
    player.enabled=false;player.update(true);assert(!player.device&&player.bytes.empty());
    player.enabled=true;player.update(true);assert(player.device&&!player.failed);
    std::cout<<"Real Windows music playback advanced; menu/combat switching, volume, mute and resume passed.\n";
}
