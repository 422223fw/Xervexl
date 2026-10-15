#pragma once
#include <windows.h>
#include <mmsystem.h>
#include <fstream>
#include <vector>
#include <string>
#include <algorithm>
#include <cstring>

// A separate waveOut stream lets the original score play under combat effects.
struct MusicPlayer {
    HWAVEOUT device{};WAVEHDR header{};std::vector<char> bytes;std::string track;float volume=.32f;bool enabled=true,failed=false;
    ~MusicPlayer(){stop();}
    void stop(){if(device){waveOutReset(device);waveOutUnprepareHeader(device,&header,sizeof(header));waveOutClose(device);device=nullptr;}header={};bytes.clear();}
    void set_volume(){if(device){DWORD v=static_cast<DWORD>(std::clamp(volume,0.f,1.f)*65535);waveOutSetVolume(device,v|(v<<16));}}
    void update(bool battle){
        std::string wanted=battle?"assets/arena_music.wav":"assets/menu_music.wav";
        if(!enabled){if(device)stop();track.clear();return;}
        if(track==wanted)return;stop();track=wanted;failed=false;
        std::ifstream input(wanted,std::ios::binary);char raw[44]{};input.read(raw,44);
        if(!input||std::memcmp(raw,"RIFF",4)||std::memcmp(raw+8,"WAVE",4)||std::memcmp(raw+36,"data",4)){failed=true;return;}
        auto word=[&](int p){unsigned short n;std::memcpy(&n,raw+p,2);return n;};auto number=[&](int p){unsigned long n;std::memcpy(&n,raw+p,4);return n;};
        WAVEFORMATEX format{};format.wFormatTag=word(20);format.nChannels=word(22);format.nSamplesPerSec=number(24);format.nAvgBytesPerSec=number(28);format.nBlockAlign=word(32);format.wBitsPerSample=word(34);
        DWORD size=number(40);if(format.wFormatTag!=WAVE_FORMAT_PCM||format.nChannels!=2||format.wBitsPerSample!=16||!size||size>12000000){failed=true;return;}
        bytes.resize(size);input.read(bytes.data(),size);if(!input||waveOutOpen(&device,WAVE_MAPPER,&format,0,0,CALLBACK_NULL)!=MMSYSERR_NOERROR){device=nullptr;failed=true;return;}
        header.lpData=bytes.data();header.dwBufferLength=size;header.dwFlags=WHDR_BEGINLOOP|WHDR_ENDLOOP;header.dwLoops=0xffffffff;
        if(waveOutPrepareHeader(device,&header,sizeof(header))!=MMSYSERR_NOERROR){failed=true;stop();return;}
        set_volume();if(waveOutWrite(device,&header,sizeof(header))!=MMSYSERR_NOERROR){failed=true;stop();}
    }
};
