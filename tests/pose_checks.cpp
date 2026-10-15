#include "poses.hpp"
#include <cassert>
#include <iostream>

int main(){
    int checked=0;
    CombatPose idle=combat_pose({});
    for(const std::string move:{"left","right","overhead","thrust","spin","disarm","rising","reverse_spin","pommel","feint"}){
      for(const std::string aim:{"body","head","legs"}){
        auto timing=move_timing(move);float windup=timing.windup;
        float duration=timing.duration;
        CombatPose previous=combat_pose({move,"centre",false,0,windup,duration,aim});
        assert(dot(previous.hand-idle.hand,previous.hand-idle.hand)<.000001f);
        assert(dot(previous.direction-idle.direction,previous.direction-idle.direction)<.000001f);
        assert(previous.spin==0);
        for(int frame=0;frame<=1000;frame++){
            auto pose=combat_pose({move,"centre",false,duration*frame/1000,windup,duration,aim});
            assert(std::isfinite(pose.hand.x)&&std::isfinite(pose.hand.y)&&std::isfinite(pose.hand.z));
            assert(std::abs(dot(pose.direction,pose.direction)-1)<.0001f);
            Vec guardAxis=blade_cross_axis(pose.direction,{1,0,0});
            assert(std::abs(dot(guardAxis,pose.direction))<.00001f);
            assert(std::abs(dot(guardAxis,guardAxis)-1)<.0001f);
            Vec shoulder{.34f,1.43f,0},hand=limit_reach(shoulder,pose.hand,.70f);
            Vec elbow=solve_joint(shoulder,hand,{1,-.6f,0},.36f);
            assert(std::abs(dot(elbow-shoulder,elbow-shoulder)-.36f*.36f)<.0001f);
            assert(std::abs(dot(hand-elbow,hand-elbow)-.36f*.36f)<.0001f);
            assert(dot(pose.hand-previous.hand,pose.hand-previous.hand)<.002f);
            assert(dot(pose.direction-previous.direction,pose.direction-previous.direction)<.002f);
            assert(std::abs(angle_delta(previous.spin,pose.spin))<.025f);
            assert(pose.lunge>=-.001f&&pose.lunge<=.16f);
            // Check the actual two-hand grip against the twisting shoulder roots.
            Vec right{.34f*std::cos(pose.twist),1.43f,-.34f*std::sin(pose.twist)},left{-right.x,1.43f,-right.z};
            for(bool twoHands:{false,true}){
                auto grip=weapon_grip(pose.hand,pose.direction,right,left,1.5f,twoHands);
                assert(dot(grip.hand-right,grip.hand-right)<=.7001f*.7001f);
                assert(std::abs(dot(grip.tip-grip.hand,grip.tip-grip.hand)-2.25f)<.00001f);
                if(twoHands){
                    assert(dot(grip.offhand-left,grip.offhand-left)<=.7001f*.7001f);
                    assert(dot(grip.offhand-(grip.hand-pose.direction*.11f),grip.offhand-(grip.hand-pose.direction*.11f))<.000001f);
                }
            }
            previous=pose;checked++;
        }
        auto end=combat_pose({move,"centre",false,duration,windup,duration,aim});
        assert(dot(end.hand-idle.hand,end.hand-idle.hand)<.0001f);
        assert(dot(end.direction-idle.direction,end.direction-idle.direction)<.0001f);
        auto contact=combat_pose({move,"centre",false,windup,windup,duration,aim});
        if(move=="left"||move=="right"||move=="overhead"){
            assert(std::abs(contact.direction.x)<.001f&&contact.direction.z>.7f);
            float epsilon=.0001f;
            auto before=combat_pose({move,"centre",false,windup-epsilon,windup,duration,aim});
            auto after=combat_pose({move,"centre",false,windup+epsilon,windup,duration,aim});
            Vec incoming=(contact.direction-before.direction)*(1/epsilon),outgoing=(after.direction-contact.direction)*(1/epsilon);
            assert(dot(incoming,incoming)>1); // A real cut keeps moving through contact.
            assert(dot(incoming-outgoing,incoming-outgoing)<.08f);
            incoming=(contact.hand-before.hand)*(1/epsilon);outgoing=(after.hand-contact.hand)*(1/epsilon);
            assert(dot(incoming-outgoing,incoming-outgoing)<.08f);
        }
        if(move=="thrust")assert(contact.hand.z>.65f&&std::abs(contact.direction.x)<.001f);
      }
    }
    for(const std::string guard:{"centre","left","right","up"}){
        auto pose=combat_pose({"left",guard,true,.13f,.18f,.46f});
        assert(std::abs(dot(pose.direction,pose.direction)-1)<.0001f);checked++;
    }
    auto hook=combat_pose({"disarm","centre",false,.24f,.24f,.52f});
    for(Vec direction:{Vec{1,0,0},Vec{0,1,0},Vec{0,0,1}}){auto across=blade_cross_axis(direction,{1,0,0});assert(std::abs(dot(across,direction))<.00001f&&dot(across,across)>.999f);}
    auto cut=combat_pose({"right","centre",false,.18f,.18f,.46f});
    assert(dot(hook.direction-cut.direction,hook.direction-cut.direction)>.05f);
    // The overhead passes above the head in its vertical plane, without a sideways flip.
    auto raised=combat_pose({"overhead","centre",false,.12f,.26f,.58f});
    assert(raised.direction.y>.9f&&std::abs(raised.direction.x)<.10f);
    PoseTransition transition;
    transition.sample({},0,0);
    auto start=transition.sample({"left","centre",false,.13f,.18f,.46f},1,.01f);
    assert(dot(start.hand-idle.hand,start.hand-idle.hand)<.000001f);
    auto swinging=transition.sample({"left","centre",false,.16f,.18f,.46f},1,.04f);
    PoseInput blocking{"","up",true};
    auto cancel=transition.sample(blocking,1,.05f);
    assert(dot(cancel.hand-swinging.hand,cancel.hand-swinging.hand)<.000001f);
    auto guard=transition.sample(blocking,1,.11f),expected=combat_pose(blocking);
    assert(dot(guard.hand-expected.hand,guard.hand-expected.hand)<.000001f);
    assert(dot(guard.direction-expected.direction,guard.direction-expected.direction)<.000001f);
    // Even a late attack update reaches its contact pose on time.
    transition.sample({"right","centre",false,.17f,.18f,.46f},2,.12f);
    auto timely=transition.sample({"right","centre",false,.18f,.18f,.46f},2,.131f);
    assert(dot(timely.direction-cut.direction,timely.direction-cut.direction)<.000001f);
    VisualCombatClock clock;
    assert(clock.sample(10,1)==10);
    float a=clock.sample(10,1.016f),b=clock.sample(10,1.032f);
    assert(a>10&&b>a); // Native frames interpolate between HTTP state packets.
    assert(clock.sample(10,2)<=10.09001f);
    assert(clock.sample(10,3)==clock.sample(10,2)); // Freeze stale-state extrapolation.
    assert(clock.sample(10.06f,3.01f)>=b);
    assert(clock.sample(0,3.02f)==0); // A restarted backend has a new clock origin.
    std::cout<<checked<<" animation samples passed, plus contact velocity, attached two-hand grips, guard cancellation and bounded visual-clock checks.\n";
}
