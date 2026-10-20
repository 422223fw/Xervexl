#pragma once
#include <algorithm>
#include <cmath>
#include <string>

constexpr float PI=3.14159265f;
struct Vec {float x,y,z;Vec operator+(Vec v)const{return{x+v.x,y+v.y,z+v.z};}Vec operator-(Vec v)const{return{x-v.x,y-v.y,z-v.z};}Vec operator-()const{return{-x,-y,-z};}Vec operator*(float f)const{return{x*f,y*f,z*f};}};
inline float dot(Vec a,Vec b){return a.x*b.x+a.y*b.y+a.z*b.z;}
inline Vec cross(Vec a,Vec b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
inline Vec norm(Vec a){float d=std::sqrt(dot(a,a));return a*(1/std::max(.0001f,d));}
inline float smooth(float t){t=std::clamp(t,0.f,1.f);return t*t*t*(10+t*(-15+6*t));}
inline Vec mix(Vec a,Vec b,float t){return a*(1-t)+b*t;}
inline Vec limit_reach(Vec root,Vec end,float maximum){Vec d=end-root;float length=std::sqrt(dot(d,d));return length>maximum?root+d*(maximum/length):end;}
inline Vec solve_joint(Vec root,Vec end,Vec bend,float length){
    Vec delta=end-root;float distance=std::clamp(std::sqrt(dot(delta,delta)),.001f,2*length-.001f);Vec axis=norm(delta);
    Vec outward=bend-axis*dot(bend,axis);if(dot(outward,outward)<.0001f)outward=cross(axis,{1,0,0});
    return root+axis*(distance*.5f)+norm(outward)*std::sqrt(std::max(0.f,length*length-distance*distance*.25f));
}
struct MoveTiming{float windup,duration;};
inline MoveTiming move_timing(const std::string& move){
    if(move=="overhead")return {.34f,.76f};if(move=="spin"||move=="reverse_spin")return {.46f,1.04f};
    if(move=="disarm")return {.30f,.66f};if(move=="thrust")return {.24f,.58f};if(move=="rising")return {.28f,.66f};
    if(move=="pommel")return {.22f,.52f};if(move=="feint")return {.12f,.32f};return {.24f,.60f};
}
struct CombatPose{Vec hand{.30f,1.22f,.31f},direction{-.16f,.78f,.61f};float twist=0,spin=0,lunge=0;};
struct PoseInput{std::string attack,guard="centre";bool block=false;float age=0,windup=.24f,duration=.60f;std::string aim="body";float moveSide=0,moveForward=0,gait=0,guardAge=999;CombatPose guardFrom;};
inline float angle_delta(float a,float b){return std::remainder(b-a,2*PI);}
inline float blade_yaw(Vec d){return std::atan2(d.x,d.z);}
inline float blade_pitch(Vec d){return std::atan2(d.y,std::hypot(d.x,d.z));}
inline float curve_yaw(Vec d,bool overhead){return overhead&&d.z<0&&d.y>0?std::remainder(blade_yaw(d)+PI,2*PI):blade_yaw(d);}
inline float curve_pitch(Vec d,bool overhead){return overhead&&d.z<0&&d.y>0?PI-blade_pitch(d):blade_pitch(d);}
inline Vec blade_direction(float yaw,float pitch){return {std::sin(yaw)*std::cos(pitch),std::sin(pitch),std::cos(yaw)*std::cos(pitch)};}
inline CombatPose walking_pose(const PoseInput& input){
    CombatPose pose;pose.direction=norm(pose.direction);
    float magnitude=std::hypot(input.moveSide,input.moveForward),scale=1/std::max(1.f,magnitude);
    float side=input.moveSide*scale,forward=input.moveForward*scale,speed=std::min(1.f,magnitude),stride=std::sin(input.gait);
    pose.hand=pose.hand+Vec{side*.075f+stride*.025f*speed,(.02f+(1-std::cos(input.gait*2))*.012f)*speed,forward*.06f-std::abs(side)*.025f+std::cos(input.gait)*.018f*speed};
    pose.direction=blade_direction(blade_yaw(pose.direction)+side*.32f+stride*.045f*speed,blade_pitch(pose.direction)-forward*.16f+std::cos(input.gait)*.035f*speed);
    pose.twist=side*.06f;return pose;
}
inline Vec blade_cross_axis(Vec direction,Vec side){
    direction=norm(direction);Vec across=side-direction*dot(side,direction);
    if(dot(across,across)<.00001f)across=cross(direction,std::abs(direction.y)<.9f?Vec{0,1,0}:Vec{0,0,1});
    return norm(across);
}
inline CombatPose blend_pose(const CombatPose& a,const CombatPose& b,float t){
    return {mix(a.hand,b.hand,t),blade_direction(blade_yaw(a.direction)+angle_delta(blade_yaw(a.direction),blade_yaw(b.direction))*t,blade_pitch(a.direction)*(1-t)+blade_pitch(b.direction)*t),
            a.twist+angle_delta(a.twist,b.twist)*t,a.spin+angle_delta(a.spin,b.spin)*t,a.lunge*(1-t)+b.lunge*t};
}
inline float hermite(float a,float b,float va,float vb,float t,float span){
    // Quintic Hermite: preserve contact velocity, with zero endpoint acceleration.
    float t2=t*t,t3=t2*t,t4=t3*t,t5=t4*t;
    return (1-10*t3+15*t4-6*t5)*a+(t-6*t3+8*t4-3*t5)*va*span
          +(10*t3-15*t4+6*t5)*b+(-4*t3+7*t4-3*t5)*vb*span;
}
struct FootStep{float travel=0,lift=0;};
inline FootStep foot_step(float gait,float speed,int leg){
    speed=std::clamp(speed,0.f,1.f);
    float phase=gait/(2*PI)+(leg<0?.5f:0);phase-=std::floor(phase);
    // A supported foot stays on the floor; the returning foot lifts at the toe.
    // Matching endpoint velocities avoids a jerk at lift-off and landing.
    if(phase<.60f)return {(.27f-.9f*phase)*speed,0};
    float t=(phase-.60f)/.40f,sine=std::sin(PI*t);
    return {hermite(-.27f,.27f,-.9f,-.9f,t,.40f)*speed,.13f*sine*sine*speed};
}
inline Vec free_hand_offset(bool block,bool shield,float gait,float speed){
    if(block)return shield?Vec{-.18f,1.37f,.48f}:Vec{-.28f,1.08f,.03f};
    return {-.37f,1.19f+(1-std::cos(gait*2))*.012f*speed,.21f+std::sin(gait)*.12f*speed};
}
struct PoseRate{Vec hand{0,0,0};float yaw=0,pitch=0,twist=0,lunge=0;};
inline CombatPose pose_segment(const CombatPose& a,const CombatPose& b,float t,float span,PoseRate va={},PoseRate vb={},bool overhead=false){
    t=std::clamp(t,0.f,1.f);float yaw=curve_yaw(a.direction,overhead);
    return {{hermite(a.hand.x,b.hand.x,va.hand.x,vb.hand.x,t,span),hermite(a.hand.y,b.hand.y,va.hand.y,vb.hand.y,t,span),hermite(a.hand.z,b.hand.z,va.hand.z,vb.hand.z,t,span)},
            blade_direction(hermite(yaw,yaw+angle_delta(yaw,curve_yaw(b.direction,overhead)),va.yaw,vb.yaw,t,span),hermite(curve_pitch(a.direction,overhead),curve_pitch(b.direction,overhead),va.pitch,vb.pitch,t,span)),
            hermite(a.twist,b.twist,va.twist,vb.twist,t,span),0,hermite(a.lunge,b.lunge,va.lunge,vb.lunge,t,span)};
}
inline CombatPose combat_pose(const PoseInput& input){
    CombatPose idle=walking_pose(input);
    if(input.block){
        CombatPose guard;guard.hand={.32f,1.29f,.48f};guard.direction=norm({-.97f,.12f,.20f});
        if(input.guard=="left"){guard.hand={.02f,1.30f,.60f};guard.direction=norm({-.95f,.26f,.18f});}
        if(input.guard=="right"){guard.hand={.34f,1.08f,.48f};guard.direction=norm({.10f,.98f,.12f});}
        if(input.guard=="up"){guard.hand={.03f,2.0f,.15f};guard.direction=norm({-.98f,0.f,.18f});}
        if(input.guardAge>=0&&input.guardAge<.12f)return blend_pose(input.guardFrom,guard,smooth(input.guardAge/.12f));
        return guard;
    }
    if(input.attack.empty()||input.age<0||input.age>=input.duration)return idle;
    float windup=std::max(.04f,input.windup),duration=std::max(windup+.06f,input.duration),follow=duration-windup;
    float offset=input.aim=="head"?.17f:input.aim=="legs"?-.20f:0,tilt=input.aim=="head"?.30f:input.aim=="legs"?-.46f:0;
    CombatPose loaded,contact,finish;
    if(input.attack=="overhead"){
        loaded.hand={.11f,1.82f,.20f};loaded.direction={.04f,.90f,-.44f};loaded.twist=-.16f;
        contact.hand={.16f,1.36f,.57f};contact.direction={0,-.12f,1};contact.lunge=.10f;
        finish.hand={.20f,.98f,.38f};finish.direction={.08f,-.66f,.75f};finish.twist=.17f;
    }else if(input.attack=="thrust"){
        loaded.hand={.33f,1.23f,.13f};loaded.direction={.07f,.10f,1};loaded.twist=-.20f;
        contact.hand={.20f,1.28f,.67f};contact.direction={0,0,1};contact.lunge=.15f;
        finish=contact;finish.hand.z=.61f;finish.lunge=.12f;
    }else if(input.attack=="disarm"){
        loaded.hand={.37f,1.26f,.19f};loaded.direction={.65f,.68f,.24f};loaded.twist=.15f;
        contact.hand={.07f,1.25f,.59f};contact.direction={-.55f,.05f,1};contact.lunge=.07f;
        finish.hand={.40f,1.43f,.28f};finish.direction={.74f,.52f,.43f};finish.twist=.22f;
        offset=tilt=0;
    }else if(input.attack=="rising"){
        loaded.hand={.46f,1.00f,.22f};loaded.direction={.65f,-.60f,.46f};loaded.twist=.24f;
        contact.hand={.18f,1.25f,.56f};contact.direction={0,.18f,1};contact.lunge=.10f;
        finish.hand={.03f,1.63f,.26f};finish.direction={-.66f,.71f,.24f};finish.twist=-.22f;
    }else if(input.attack=="pommel"){
        loaded.hand={.31f,1.38f,.16f};loaded.direction={.22f,.97f,.10f};loaded.twist=-.16f;
        contact.hand={.23f,1.35f,.66f};contact.direction={.15f,.98f,-.1f};contact.lunge=.09f;
        finish=loaded;finish.hand.z=.32f;
    }else if(input.attack=="feint"){
        loaded.hand={.45f,1.45f,.24f};loaded.direction=norm({.85f,.40f,.34f});loaded.twist=.18f;
        if(input.age<windup)return blend_pose(idle,loaded,smooth(input.age/windup));
        return blend_pose(loaded,idle,smooth((input.age-windup)/follow));
    }else if(input.attack=="spin"||input.attack=="reverse_spin"){
        loaded.hand={.43f,1.28f+offset,.30f};loaded.direction=norm({.83f,.08f+tilt,.55f});loaded.twist=-.12f;
        float prepare=windup*.30f,sweepEnd=windup+follow*.50f;CombatPose pose;
        if(input.age<prepare)pose=blend_pose(idle,loaded,smooth(input.age/prepare));
        else if(input.age<sweepEnd){pose=loaded;float t=(input.age-prepare)/(sweepEnd-prepare);pose.spin=2*PI*smooth(t);pose.lunge=.07f*std::sin(t*PI);}
        else{pose=blend_pose(loaded,idle,smooth((input.age-sweepEnd)/(duration-sweepEnd)));pose.spin=2*PI;}
        if(input.attack=="reverse_spin"){pose.spin=-pose.spin;pose.twist=-pose.twist;}return pose;
    }else{
        float side=input.attack=="left"?-1.f:1.f;
        loaded.hand={side<0?.02f:.48f,1.47f,.22f};loaded.direction={side*.94f,.32f,-.20f};loaded.twist=side*.28f;
        contact.hand={.19f,1.30f,.58f};contact.direction={0,.02f,1};contact.lunge=.08f;
        finish.hand={side<0?.45f:-.04f,1.08f,.31f};finish.direction={-side*.93f,-.32f,.17f};finish.twist=-side*.26f;
    }
    contact.hand.y+=offset;contact.direction.y+=tilt;finish.hand.y+=offset*.65f;finish.direction.y+=tilt*.55f;
    loaded.direction=norm(loaded.direction);contact.direction=norm(contact.direction);finish.direction=norm(finish.direction);
    float loadTime=windup*.34f,finishTime=windup+follow*.38f,swingSpan=finishTime-loadTime;
    // Match angular and hand velocity across contact; the blade cuts through it.
    bool overhead=input.attack=="overhead";
    PoseRate velocity{(finish.hand-loaded.hand)*(1/swingSpan),angle_delta(curve_yaw(loaded.direction,overhead),curve_yaw(finish.direction,overhead))/swingSpan,
                      (curve_pitch(finish.direction,overhead)-curve_pitch(loaded.direction,overhead))/swingSpan,(finish.twist-loaded.twist)/swingSpan,0};
    // Left/right cuts travel through forward, including when the total arc exceeds pi.
    if(input.attack=="left"||input.attack=="right")velocity.yaw=(blade_yaw(finish.direction)-blade_yaw(loaded.direction))/swingSpan;
    if(input.attack=="thrust")velocity={}; // A thrust extends and withdraws on one line.
    if(input.age<loadTime)return pose_segment(idle,loaded,input.age/loadTime,loadTime,{}, {},overhead);
    if(input.age<windup)return pose_segment(loaded,contact,(input.age-loadTime)/(windup-loadTime),windup-loadTime,{},velocity,overhead);
    if(input.age<finishTime)return pose_segment(contact,finish,(input.age-windup)/(finishTime-windup),finishTime-windup,velocity,{},overhead);
    return pose_segment(finish,idle,(input.age-finishTime)/(duration-finishTime),duration-finishTime,{}, {},overhead);
}

struct WeaponGrip{Vec hand,tip,offhand;};
inline WeaponGrip weapon_grip(Vec desired,Vec direction,Vec shoulder,Vec otherShoulder,float length,bool twoHanded){
    direction=norm(direction);Vec hand=desired;
    // Keep both hands attached to a two-handed hilt without stretching either arm.
    for(int i=0;i<(twoHanded?24:1);i++){
        hand=limit_reach(shoulder,hand,.70f);
        if(twoHanded)hand=limit_reach(otherShoulder,hand-direction*.11f,.70f)+direction*.11f;
    }
    return {hand,hand+direction*length,hand-direction*.11f};
}

struct VisualCombatClock{
    float observed=-1,received=0,value=0;
    float sample(float serverTime,float localTime){
        if(observed<0||serverTime<observed-.3f){observed=serverTime;received=localTime;value=serverTime;}
        else if(serverTime!=observed){observed=serverTime;received=localTime;}
        value=std::max(value,observed+std::clamp(localTime-received,0.f,.09f));return value;
    }
};
struct PoseTransition{
    CombatPose displayed,from;PoseInput previous;int previousAttack=-1;float changed=0,span=0,lastSeen=0,motionSide=0,motionForward=0,motionGait=0;bool ready=false;
    CombatPose sample(const PoseInput& input,int attackId,float localTime){
        float dt=std::clamp(localTime-lastSeen,0.f,.1f);lastSeen=localTime;
        if(!ready){motionSide=input.moveSide;motionForward=input.moveForward;motionGait=input.gait;}
        else{float blend=1-std::exp(-dt*16);motionSide+=(input.moveSide-motionSide)*blend;motionForward+=(input.moveForward-motionForward)*blend;motionGait+=(input.gait-motionGait)*blend;}
        PoseInput visual=input;visual.moveSide=motionSide;visual.moveForward=motionForward;visual.gait=motionGait;
        CombatPose target=combat_pose(visual);
        if(!ready){ready=true;previous=input;previousAttack=attackId;displayed=target;return target;}
        bool changedState=input.block!=previous.block||(input.block&&input.guard!=previous.guard)||input.attack!=previous.attack||attackId!=previousAttack;
        if(changedState){
            from=displayed;changed=localTime;span=input.block?(input.guardAge<999?0.f:.12f):.075f;
            if(!input.block&&!input.attack.empty())span=std::min(.05f,std::max(0.f,input.windup-input.age));
        }
        previous=input;previousAttack=attackId;
        displayed=span>0?blend_pose(from,target,smooth((localTime-changed)/span)):target;return displayed;
    }
};
