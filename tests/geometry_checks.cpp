#include "render.hpp"
#include "json.hpp"
using json=nlohmann::json;
#include "scene.hpp"
#include <cassert>
#include <fstream>
#include <iostream>

int main(int argc,char** argv){
    if(argc!=2)return 2;json rows=json::array();
    for(const std::string weapon:{"knife","arming","longsword"})for(const std::string move:{"left","right","overhead","thrust","spin","reverse_spin","disarm","rising","pommel","feint","guard_left","guard_right","guard_up","guard_centre","idle"}){
        bool block=move.rfind("guard_",0)==0;auto timing=move_timing(move);
        for(float phase:{.73f,1.f,1.15f})for(float yaw:{0.f,1.3f}){
            json f={{"weapon",weapon},{"shield",""},{"x",2.f},{"z",3.f},{"yaw",yaw},{"body_yaw",yaw-.12f},{"attack",block||move=="idle"?"":move},{"attack_started",0.f},{"attack_windup",timing.windup},{"attack_duration",timing.duration},{"block",block},{"guard_dir",block?move.substr(6):"centre"},{"aim_zone","body"},{"jump",.275f},{"move_x",move=="idle"?3.1f:0.f},{"move_z",move=="idle"?1.2f:0.f},{"gait",.7f}};
            float clock=timing.windup*phase;auto pose=pose_for(f,clock);float basisYaw=(block||!f.value("attack",std::string{}).empty()?yaw:yaw-.12f)+pose.spin;
            Vec front{std::sin(basisYaw),0,std::cos(basisYaw)},side{std::cos(basisYaw),0,-std::sin(basisYaw)},origin{2,.65f,3};
            float bodyYaw=yaw-.12f+pose.spin+pose.twist;Vec bodySide{std::cos(bodyYaw),0,-std::sin(bodyYaw)};
            Vec right=origin+bodySide*.34f+Vec{0,1.43f,0},left=origin-bodySide*.34f+Vec{0,1.43f,0},hand,tip;
            blade_pose(f,clock,origin,front,side,weapon_length(weapon),hand,tip,&pose,&right,&left);
            // Pommel uses the visible rear grip rather than the cutting edge.
            if(move=="pommel")tip=hand-norm(tip-hand)*.20f;
            rows.push_back({{"fighter",f},{"time",clock},{"hand",{hand.x,hand.y,hand.z}},{"tip",{tip.x,tip.y,tip.z}}});
        }
    }
    PoseInput guard{"","right",true};guard.guardFrom=combat_pose({"","up",true});guard.guardAge=.06f;
    auto halfway=combat_pose(guard),target=blend_pose(guard.guardFrom,combat_pose({"","right",true}),.5f);
    assert(dot(halfway.hand-target.hand,halfway.hand-target.hand)<.000001f);
    std::ofstream out(argv[1]);out<<rows.dump();if(!out)return 3;
    std::cout<<rows.size()<<" actual renderer weapon segments exported for server/native parity checks.\n";
}
