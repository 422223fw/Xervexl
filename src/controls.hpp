#pragma once
#include <cmath>
#include <string>

struct CombatKeys {
    float forward=0,side=0,mouseX=0,mouseY=0;
    bool left=false,right=false,middle=false,overhead=false,disarm=false,spin=false;
    bool rising=false,reverseSpin=false,pommel=false,feint=false;
};
struct CombatControls {
    bool easy=true,leftWasDown=false;
    int cut=0;
    std::string guard="centre";
    std::string attack(const CombatKeys& k){
        if(easy){
            // The server alternates completed cuts; walking never changes them.
            cut=0;guard="centre";
        }else{
            if(k.side<-.1f)cut=0;else if(k.side>.1f)cut=1;else if(k.forward>.1f)cut=2;else if(k.forward<-.1f)cut=3;
            else if(k.left&&!leftWasDown)cut=cut==0?1:0;
            guard=k.side<-.1f?"left":k.side>.1f?"right":k.forward>.1f?"up":k.forward<-.1f?"centre":guard;
            if(k.right&&k.forward==0&&k.side==0&&(std::abs(k.mouseX)>3||std::abs(k.mouseY)>3))
                guard=std::abs(k.mouseX)>std::abs(k.mouseY)?(k.mouseX<0?"left":"right"):(k.mouseY<0?"up":"centre");
        }
        leftWasDown=k.left;
        if(k.right)return {}; // Block wins and clears any queued attack.
        if(k.disarm)return "disarm";
        if(k.spin)return "spin";
        if(k.reverseSpin)return "reverse_spin";if(k.rising)return "rising";if(k.pommel)return "pommel";if(k.feint)return "feint";
        if(k.middle){cut=3;return "thrust";}
        if(k.overhead){cut=2;return "overhead";}
        const char* cuts[]={"left","right","overhead","thrust"};
        return k.left?cuts[cut]:"";
    }
};
