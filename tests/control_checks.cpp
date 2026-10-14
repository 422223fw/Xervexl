#include "controls.hpp"
#include <cassert>
#include <iostream>

int main(){
    CombatControls c;CombatKeys k;k.left=true;
    for(int forward=-1;forward<=1;forward++)for(int side=-1;side<=1;side++){
        k.forward=forward;k.side=side;assert(c.attack(k)=="left");
    }
    k.middle=true;assert(c.attack(k)=="thrust");k.middle=false;
    k.overhead=true;assert(c.attack(k)=="overhead");k.overhead=false;
    k.right=true;k.spin=true;k.disarm=true;
    assert(c.attack(k).empty()); // Blocking beats every attack, including holding LMB.
    k={};c.easy=false;k.forward=1;k.left=true;assert(c.attack(k)=="overhead");
    k.forward=-1;assert(c.attack(k)=="thrust");
    k.forward=0;k.side=-1;assert(c.attack(k)=="left");
    k.side=1;assert(c.attack(k)=="right");
    k={};c.attack(k);k.left=true;auto first=c.attack(k);c.attack({});auto second=c.attack(k);
    assert(first!=second); // Standing manual clicks still alternate.
    k={};k.right=true;k.mouseY=-8;c.attack(k);assert(c.guard=="up");
    c.easy=true;k.left=true;assert(c.attack(k).empty());
    std::cout<<"Combat controls: movement-independent easy cuts, manual cuts, thrust, overhead and block priority passed.\n";
}
