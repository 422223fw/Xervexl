#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif
#include "poses.hpp"
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>

void write_pose(std::ostream& out,const CombatPose& p){
    out<<'['<<p.hand.x<<','<<p.hand.y<<','<<p.hand.z<<','<<p.direction.x<<','<<p.direction.y<<','<<p.direction.z<<','<<p.twist<<','<<p.spin<<','<<p.lunge<<']';
}
int main(int argc,char** argv){
    if(argc!=2)return 2;
    std::filesystem::path target(argv[1]),temporary=target;temporary+=".tmp";
    std::ofstream out(temporary);out<<std::setprecision(7)<<"{\"version\":1,\"intervals\":256,\"idle\":";write_pose(out,combat_pose({}));
    out<<",\"guards\":{";bool first=true;
    for(const std::string guard:{"centre","left","right","up"}){
        if(!first)out<<',';first=false;out<<'"'<<guard<<"\":";write_pose(out,combat_pose({"",guard,true}));
    }
    out<<"},\"moves\":{";first=true;
    for(const std::string move:{"left","right","overhead","thrust","spin","reverse_spin","disarm","rising","pommel","feint"}){
        if(!first)out<<',';first=false;auto timing=move_timing(move);
        out<<'"'<<move<<"\":{\"windup\":"<<timing.windup<<",\"duration\":"<<timing.duration<<",\"aims\":{";
        bool firstAim=true;
        for(const std::string aim:{"body","head","legs"}){
            if(!firstAim)out<<',';firstAim=false;out<<'"'<<aim<<"\":[";
            for(int i=0;i<=256;i++){
                if(i)out<<',';write_pose(out,combat_pose({move,"centre",false,timing.duration*i/256,timing.windup,timing.duration,aim}));
            }
            out<<']';
        }
        out<<"}}";
    }
    out<<"}}\n";out.close();if(!out)return 3;
#ifdef _WIN32
    bool published=false;
    for(int retry=0;retry<6;retry++){
        if(MoveFileExW(temporary.c_str(),target.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){published=true;break;}
        Sleep(20*(retry+1));
    }
    if(!published)return 4;
#else
    std::filesystem::rename(temporary,target);
#endif
    std::cout<<"Exported authoritative collision poses from the native animation curves.\n";
}
