#include "controls.hpp"
#include <cassert>
#include <iostream>

int main(){
    CombatControls c;CombatKeys k;k.left=true;
    for(int forward=-1;forward<=1;forward++)for(int side=-1;side<=1;side++){
        k.forward=forward;k.side=side;
        std::string expected=side<0?"left":side>0?"right":forward>0?"overhead":forward<0?"thrust":"left";
        assert(c.attack(k)==expected&&c.primaryAttack);
    }
    k.middle=true;assert(c.attack(k)=="thrust"&&!c.primaryAttack);k.middle=false;
    k.overhead=true;assert(c.attack(k)=="overhead"&&!c.primaryAttack);k.overhead=false;
    k.right=true;k.spin=true;k.disarm=true;
    k.rising=k.reverseSpin=k.pommel=k.feint=true;
    assert(c.attack(k).empty()&&!c.primaryAttack); // Blocking beats every attack, including holding LMB.
    k={};c.easy=false;k.forward=1;k.left=true;assert(c.attack(k)=="overhead");
    k.forward=-1;assert(c.attack(k)=="thrust");
    k.forward=0;k.side=-1;assert(c.attack(k)=="left");
    k.side=1;assert(c.attack(k)=="right");
    k={};c.attack(k);k.left=true;auto first=c.attack(k);c.attack({});auto second=c.attack(k);
    assert(first!=second); // Standing manual clicks still alternate.
    k={};k.right=true;k.mouseY=-8;c.attack(k);assert(c.guard=="up");
    c.easy=true;k.left=true;assert(c.attack(k).empty());
    k={};k.rising=true;assert(c.attack(k)=="rising");k={};k.reverseSpin=true;assert(c.attack(k)=="reverse_spin");
    k={};k.pommel=true;assert(c.attack(k)=="pommel");k={};k.feint=true;assert(c.attack(k)=="feint");
    k={};k.right=true;k.side=-1;c.attack(k);assert(c.guard=="left");
    k.side=1;c.attack(k);assert(c.guard=="right");k.side=0;k.forward=1;c.attack(k);assert(c.guard=="up");
    k.forward=-1;c.attack(k);assert(c.guard=="centre");k.mouseX=-8;c.attack(k);assert(c.guard=="left");
    std::cout<<"Combat controls: nine movement directions, held primary attacks, explicit move overrides, manual guards and block priority passed.\n";
}
