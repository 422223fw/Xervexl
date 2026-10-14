#pragma once
#include <algorithm>
#include <cmath>
#include <string>

constexpr float PI=3.14159265f;
struct Vec {float x,y,z;Vec operator+(Vec v)const{return{x+v.x,y+v.y,z+v.z};}Vec operator-(Vec v)const{return{x-v.x,y-v.y,z-v.z};}Vec operator-()const{return{-x,-y,-z};}Vec operator*(float f)const{return{x*f,y*f,z*f};}};
inline float dot(Vec a,Vec b){return a.x*b.x+a.y*b.y+a.z*b.z;}
inline Vec cross(Vec a,Vec b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
inline Vec norm(Vec a){float d=std::sqrt(dot(a,a));return a*(1/std::max(.0001f,d));}
inline float smooth(float t){t=std::clamp(t,0.f,1.f);return t*t*(3-2*t);}
inline Vec mix(Vec a,Vec b,float t){return a*(1-t)+b*t;}
inline Vec limit_reach(Vec root,Vec end,float maximum){Vec d=end-root;float length=std::sqrt(dot(d,d));return length>maximum?root+d*(maximum/length):end;}
inline Vec solve_joint(Vec root,Vec end,Vec bend,float length){
    Vec delta=end-root;float distance=std::clamp(std::sqrt(dot(delta,delta)),.001f,2*length-.001f);Vec axis=norm(delta);
    Vec outward=bend-axis*dot(bend,axis);if(dot(outward,outward)<.0001f)outward=cross(axis,{1,0,0});
    return root+axis*(distance*.5f)+norm(outward)*std::sqrt(std::max(0.f,length*length-distance*distance*.25f));
}
struct PoseInput{std::string attack,guard="centre";bool block=false;float age=0,windup=.18f,duration=.46f;std::string aim="body";};
struct CombatPose{Vec hand{.32f,1.18f,.30f},direction{-.12f,.90f,.42f};float twist=0,spin=0,lunge=0;};
inline CombatPose combat_pose(const PoseInput& input){
    CombatPose idle;idle.direction=norm(idle.direction);
    if(input.block){
        CombatPose guard;guard.hand={.12f,1.44f,.43f};
        guard.direction=norm(input.guard=="up"?Vec{.96f,.12f,.16f}:input.guard=="left"?Vec{-.66f,.73f,.16f}:input.guard=="right"?Vec{.66f,.73f,.16f}:Vec{-.72f,.68f,.12f});
        if(input.guard=="up"){guard.hand={-.04f,1.96f,.19f};guard.direction=norm({.96f,.14f,.20f});}
        return guard;
    }
    if(input.attack.empty()||input.age<0||input.age>=input.duration)return idle;
    float windup=std::max(.04f,input.windup),duration=std::max(windup+.06f,input.duration),follow=duration-windup;
    CombatPose loaded,contact,finish;
    if(input.attack=="overhead"){
        loaded.hand={.12f,1.76f,.17f};loaded.direction={.08f,.93f,-.36f};loaded.twist=-.1f;
        contact.hand={.18f,1.40f,.56f};contact.direction={.02f,-.29f,.96f};contact.lunge=.09f;
        finish.hand={.24f,1.07f,.42f};finish.direction={.08f,-.61f,.79f};finish.twist=.13f;
    }else if(input.attack=="thrust"){
        loaded.hand={.28f,1.22f,.14f};loaded.direction={-.04f,.03f,1};loaded.twist=-.22f;
        contact.hand={.17f,1.30f,.68f};contact.direction={0,0,1};contact.lunge=.13f;
        finish=contact;finish.hand.z=.43f;finish.lunge=.06f;
    }else if(input.attack=="spin"){
        float t=std::clamp(input.age/duration,0.f,1.f);CombatPose pose;
        float offset=input.aim=="head"?.28f:input.aim=="legs"?-.22f:0;float tilt=input.aim=="head"?.4f:input.aim=="legs"?-.35f:0;
        float extent=std::sin(t*PI);pose.hand={.42f,1.28f+offset*extent,.35f+extent*.14f};pose.direction=norm({.62f,-.04f+tilt*extent,.78f});pose.spin=2*PI*smooth(t);
        float recover=smooth((t-.80f)/.20f);pose.hand=mix(pose.hand,idle.hand,recover);pose.direction=norm(mix(pose.direction,idle.direction,recover));return pose;
    }else{
        float side=input.attack=="left"?-1.f:1.f;
        loaded.hand={side<0?-.13f:.51f,1.39f,.20f};loaded.direction={side*.93f,.18f,-.28f};loaded.twist=side*.30f;
        contact.hand={.17f,1.27f,.59f};contact.direction={0,.06f,1};contact.lunge=.07f;
        finish.hand={side<0?.50f:-.15f,1.13f,.29f};finish.direction={-side*.96f,-.23f,.13f};finish.twist=-side*.25f;
    }
    float offset=input.aim=="head"?.28f:input.aim=="legs"?-.22f:0,tilt=input.aim=="head"?.4f:input.aim=="legs"?-.35f:0;
    contact.hand.y+=offset;contact.direction.y+=tilt;finish.hand.y+=offset*.6f;finish.direction.y+=tilt*.6f;
    CombatPose a,b;float t;
    if(input.age<windup*.48f){a=idle;b=loaded;t=smooth(input.age/(windup*.48f));}
    else if(input.age<windup){a=loaded;b=contact;t=smooth((input.age-windup*.48f)/(windup*.52f));}
    else if(input.age<windup+follow*.42f){a=contact;b=finish;t=smooth((input.age-windup)/(follow*.42f));}
    else{a=finish;b=idle;t=smooth((input.age-windup-follow*.42f)/(follow*.58f));}
    return {mix(a.hand,b.hand,t),norm(mix(a.direction,b.direction,t)),a.twist*(1-t)+b.twist*t,0,a.lunge*(1-t)+b.lunge*t};
}
