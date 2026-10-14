#include "poses.hpp"
#include <cassert>
#include <iostream>

int main(){
    int checked=0;
    for(const std::string move:{"left","right","overhead","thrust","spin","disarm"}){
      for(const std::string aim:{"body","head","legs"}){
        float windup=move=="overhead"?.26f:move=="spin"?.36f:.18f;
        float duration=move=="overhead"?.58f:move=="spin"?.80f:.46f;
        CombatPose previous=combat_pose({move,"centre",false,0,windup,duration,aim});
        for(int frame=0;frame<=1000;frame++){
            auto pose=combat_pose({move,"centre",false,duration*frame/1000,windup,duration,aim});
            assert(std::isfinite(pose.hand.x)&&std::isfinite(pose.hand.y)&&std::isfinite(pose.hand.z));
            assert(std::abs(dot(pose.direction,pose.direction)-1)<.0001f);
            Vec shoulder{.34f,1.43f,0},hand=limit_reach(shoulder,pose.hand,.70f);
            Vec elbow=solve_joint(shoulder,hand,{1,-.6f,0},.36f);
            assert(std::abs(dot(elbow-shoulder,elbow-shoulder)-.36f*.36f)<.0001f);
            assert(std::abs(dot(hand-elbow,hand-elbow)-.36f*.36f)<.0001f);
            assert(dot(pose.hand-previous.hand,pose.hand-previous.hand)<.002f);
            previous=pose;checked++;
        }
        auto end=combat_pose({move,"centre",false,duration,windup,duration,aim});
        auto idle=combat_pose({});assert(dot(end.hand-idle.hand,end.hand-idle.hand)<.0001f);
      }
    }
    for(const std::string guard:{"centre","left","right","up"}){
        auto pose=combat_pose({"left",guard,true,.13f,.18f,.46f});
        assert(std::abs(dot(pose.direction,pose.direction)-1)<.0001f);checked++;
    }
    std::cout<<checked<<" animation samples passed: fixed blade length, bounded arm reach, fixed bones and smooth recovery.\n";
}
