    json item_info(const std::string& id){for(const auto& item:catalog)if(item.value("id",std::string{})==id)return item;return json::object();}
    void weapon_icon(float x,float y,const std::string& id,float scale=1){
        auto item=item_info(id);std::string family=item.value("family",std::string{}),kind=item.value("kind",std::string("weapon"));
        Colour metal{.75f,.78f,.75f};bool magic=item.contains("magic")||kind=="spell";
        if(magic)canvas.circle(x,y,35*scale,{.25f,.48f,.70f,.16f});
        if(kind=="shield"){canvas.circle(x,y,23*scale,{.34f,.38f,.37f});canvas.circle(x,y,17*scale,{.18f,.24f,.22f});canvas.circle(x,y,7*scale,GOLD);}
        else if(kind=="armour"){canvas.rect(x-18*scale,y-24*scale,36*scale,48*scale,{.46f,.50f,.47f});canvas.triangle(x-18*scale,y-24*scale,x,y-35*scale,x+18*scale,y-24*scale,{.59f,.62f,.57f});canvas.rect(x-20*scale,y+14*scale,40*scale,5*scale,GOLD);}
        else if(kind=="helmet"){canvas.circle(x,y,24*scale,metal);canvas.rect(x-25*scale,y,50*scale,20*scale,INK);canvas.line(x-19*scale,y+2*scale,x+19*scale,y+2*scale,5*scale,metal);canvas.line(x,y-10*scale,x,y+16*scale,6*scale,metal);}
        else if(kind=="upgrade"){canvas.circle(x,y,29*scale,{.52f,.15f,.13f});canvas.rect(x-5*scale,y-17*scale,10*scale,34*scale,WHITE);canvas.rect(x-17*scale,y-5*scale,34*scale,10*scale,WHITE);}
        else if(kind=="spell"){canvas.circle(x,y,25*scale,{.20f,.43f,.61f});canvas.circle(x,y,17*scale,{.10f,.23f,.35f});canvas.line(x-10*scale,y+8*scale,x+2*scale,y-15*scale,4*scale,GOLD);canvas.line(x+2*scale,y-15*scale,x+11*scale,y+13*scale,4*scale,GOLD);}
        else if(family=="bow"){for(int i=0;i<12;i++){float a=-1.15f+i*2.3f/12,b=-1.15f+(i+1)*2.3f/12;canvas.line(x+std::cos(a)*28*scale-13*scale,y+std::sin(a)*45*scale,x+std::cos(b)*28*scale-13*scale,y+std::sin(b)*45*scale,4*scale,GOLD);}canvas.line(x,y-41*scale,x,y+41*scale,1*scale,WHITE);canvas.line(x-20*scale,y,x+42*scale,y,2*scale,metal);canvas.triangle(x+42*scale,y,x+32*scale,y-5*scale,x+32*scale,y+5*scale,metal);}
        else if(family=="crossbow"){canvas.line(x,y+38*scale,x,y-33*scale,7*scale,GOLD);canvas.line(x-34*scale,y-12*scale,x+34*scale,y-12*scale,5*scale,metal);canvas.line(x-34*scale,y-12*scale,x,y+9*scale,1*scale,WHITE);canvas.line(x+34*scale,y-12*scale,x,y+9*scale,1*scale,WHITE);}
        else if(family=="slingshot"){canvas.line(x,y+30*scale,x,y-4*scale,6*scale,GOLD);canvas.line(x,y-4*scale,x-22*scale,y-28*scale,5*scale,GOLD);canvas.line(x,y-4*scale,x+22*scale,y-28*scale,5*scale,GOLD);canvas.line(x-22*scale,y-28*scale,x,y-12*scale,2*scale,WHITE);canvas.line(x+22*scale,y-28*scale,x,y-12*scale,2*scale,WHITE);}
        else{float length=id=="knife"||id=="dagger"?27:family=="spear"||family=="staff"?55:48;canvas.line(x,y+26*scale,x,y-length*scale,5*scale,magic?Colour{.42f,.73f,.94f}:metal);canvas.line(x-14*scale,y+16*scale,x+14*scale,y+16*scale,4*scale,GOLD);canvas.line(x,y+18*scale,x,y+35*scale,6*scale,{.30f,.22f,.15f});if(family=="axe")canvas.triangle(x,y-43*scale,x+28*scale,y-37*scale,x+24*scale,y-15*scale,metal);else if(family=="mace")canvas.circle(x,y-33*scale,14*scale,metal);else if(family=="staff")canvas.circle(x,y-48*scale,12*scale,{.95f,.47f,.18f});else canvas.triangle(x-3*scale,y-length*scale,x+3*scale,y-length*scale,x,y-(length+8)*scale,WHITE);}
    }
    void shop(){
        canvas.rect(0,0,1280,800,{.025f,.041f,.044f,.98f});canvas.text(46,27,"THE ARMOURY",3.6f,GOLD);
        canvas.text(47,77,"BLADES, RANGED WEAPONS, DEFENCE AND RARE ARCANE EQUIPMENT",1.45f,MUTED);
        canvas.text(936,38,std::to_string(coins)+" CROWNS",1.9f,GOLD);if(button(1127,24,106,46,"BACK"))screen=Screen::Home;
        const char* categories[]={"MELEE","RANGED","ARMOUR & SHIELDS","ARCANE","HEALTH"};
        for(int i=0;i<5;i++)if(button(47+i*241,110,225,45,categories[i],shopCategory==i)){shopCategory=i;shopPage=0;}
        std::vector<json> items;
        for(const auto& item:catalog){std::string kind=item.value("kind",std::string("weapon")),family=item.value("family",std::string{});bool ranged=family=="bow"||family=="crossbow"||family=="slingshot"||family=="staff";bool magic=item.contains("magic")||kind=="spell";
            if((shopCategory==0&&kind=="weapon"&&!ranged&&!magic)||(shopCategory==1&&ranged&&!magic)||(shopCategory==2&&(kind=="armour"||kind=="shield"||kind=="helmet"))||(shopCategory==3&&magic)||(shopCategory==4&&kind=="upgrade"))items.push_back(item);
        }
        int pages=std::max(1,(static_cast<int>(items.size())+7)/8);shopPage=std::min(shopPage,pages-1);
        if(catalog.empty())canvas.text(48,187,"CONNECT TO A SERVER TO LOAD THE ARMOURY.",1.8f,WHITE);
        for(int slot=0;slot<8;slot++){
            int index=shopPage*8+slot;if(index>=static_cast<int>(items.size()))break;auto item=items[index];std::string id=item["id"],kind=item.value("kind",std::string("weapon"));
            float x=47+(slot%4)*301,y=180+(slot/4)*252;bool upgrade=kind=="upgrade",owned=false;
            if(profile.contains("inventory"))for(auto& v:profile["inventory"])if(v==id)owned=true;
            bool equipped=!upgrade&&profile.value(kind,std::string{})==id;int price=upgrade?profile.value("health_upgrade_price",12000):item.value("price",0);
            canvas.rect(x,y,285,234,{.085f,.12f,.125f});canvas.border(x,y,285,234,equipped?GOLD:Colour{.20f,.27f,.26f});
            canvas.text(x+14,y+12,equipped?"EQUIPPED":upgrade?"PERMANENT UPGRADE":owned?"OWNED":item.contains("magic")?"RARE ARCANE":"AVAILABLE",1.1f,equipped?GOLD:MUTED);
            weapon_icon(x+142,y+87,id,.76f);std::string title=item.value("name",std::string{});float titleScale=Canvas::text_width(title,1.85f)>257?1.6f:1.85f;canvas.text(x+14,y+136,title,titleScale,WHITE);
            std::string detail;
            if(kind=="weapon")detail=std::to_string(item.value("damage",0))+" DMG / "+std::to_string(static_cast<int>(item.value("reach",1.f)*10)/10.f).substr(0,3)+"M REACH";
            else if(kind=="shield")detail="BLOCKS "+std::to_string(static_cast<int>(item.value("reduction",0.f)*100))+"% / NORMAL BLOCK";
            else if(kind=="armour"||kind=="helmet")detail=std::to_string(static_cast<int>(item.value("reduction",0.f)*100))+"% DEFENCE"+(kind=="helmet"?" / HEAD":" / BODY");
            else if(kind=="spell")detail=std::to_string(item.value("cost",0))+" STAMINA / "+std::to_string(static_cast<int>(item.value("cooldown",0.f)))+"S COOLDOWN / B";
            else detail="MAX HP "+std::to_string(static_cast<int>(maxHp))+" -> "+std::to_string(static_cast<int>(maxHp)+20);
            canvas.text(x+14,y+159,detail,1.2f,MUTED);
            if(kind=="weapon")canvas.text(x+14,y+178,"RECOVERY "+std::to_string(item.value("cooldown",0.f)).substr(0,4)+"S",1.0f,MUTED);
            std::string label=equipped?"EQUIPPED":owned?"EQUIP":std::to_string(price)+" CROWNS";
            if(button(x+14,y+190,257,32,label,owned&&!equipped)&&!equipped){if(profile.empty())toast("Enter the arena or sign in first.");else net.queue(owned?"/shop/equip":"/shop/buy",{{"item",id}});}
        }
        canvas.text(47,704,"PAGE "+std::to_string(shopPage+1)+" / "+std::to_string(pages),1.4f,MUTED);
        if(button(931,697,139,38,"PREVIOUS")&&shopPage>0)shopPage--;
        if(button(1083,697,149,38,"NEXT")&&shopPage+1<pages)shopPage++;
        canvas.text(47,755,shopCategory==4?"HEALTH IS EXPENSIVE: 12,000 x (UPGRADES + 1) SQUARED. EACH PURCHASE ADDS 20 MAX HP.":"HEAD, BODY AND LEG HITS DIFFER. NO SINGLE HIT KILLS A FULL-HEALTH FIGHTER.",1.3f,MUTED);
    }
    void leaderboard_view(){
        canvas.rect(0,0,1280,800,{.025f,.041f,.044f,.98f});canvas.text(46,26,"ARENA LEADERBOARDS",3.5f,GOLD);
        canvas.text(47,75,"THIS SERVER / REGISTERED FIGHTERS AND ACTIVE BOTS / LIVE SCORES",1.35f,MUTED);
        if(button(1127,24,106,46,"BACK"))screen=Screen::Home;
        const char* labels[]={"SKILL POINTS","RANK","TOTAL XP","CROWNS","ELIMINATIONS"};const char* keys[]={"skill","level","xp","coins","kills"};
        for(int i=0;i<5;i++)if(button(47+i*241,108,225,45,labels[i],leaderTab==i))leaderTab=i;
        canvas.text(50,183,"#",1.4f,MUTED);canvas.text(98,183,"FIGHTER",1.4f,MUTED);canvas.text(455,183,"TYPE",1.4f,MUTED);
        canvas.text(576,183,"RANK",1.4f,MUTED);canvas.text(711,183,"SKILL",1.4f,MUTED);canvas.text(855,183,"XP",1.4f,MUTED);canvas.text(1008,183,"CROWNS",1.4f,MUTED);canvas.text(1164,183,"KILLS",1.4f,MUTED);
        if(boards.contains(keys[leaderTab])){int i=0;for(const auto& row:boards[keys[leaderTab]]){float y=219+i*35;canvas.rect(47,y-5,1185,33,{.07f+(i%2)*.017f,.105f+(i%2)*.017f,.11f+(i%2)*.017f});Colour nameColour=i<3?GOLD:WHITE;
            canvas.text(58,y,std::to_string(i+1),1.6f,nameColour);canvas.text(99,y,row.value("username",std::string{}),1.6f,nameColour);canvas.text(455,y,row.value("bot",false)?"BOT":"PLAYER",1.4f,MUTED);
            float x[]={581,716,855,1011,1168};for(int j=0;j<5;j++)canvas.text(x[j],y,std::to_string(row.value(keys[j==0?1:j==1?0:j],0)),1.5f,leaderTab==(j==0?1:j==1?0:j)?GOLD:WHITE);i++;
        }}else canvas.text(48,242,busy?"LOADING LEADERBOARDS...":"CONNECT TO YOUR ARENA SERVER.",1.7f,WHITE);
        canvas.text(48,672,"YOU: RANK "+std::to_string(level)+" / "+std::to_string(xp)+" XP / "+std::to_string(skill)+" SKILL / "+std::to_string(coins)+" CROWNS",1.6f,GOLD);
        canvas.text(48,718,"KILL: TARGET RANK IN SKILL. XP AND CROWNS ALSO SCALE WITH TARGET RANK.",1.4f,MUTED);
        canvas.text(48,752,"LOSING TO A LOWER RANK COSTS MORE SKILL. PERFECT PARRIES AND DISARMS EARN XP + SKILL.",1.3f,MUTED);
    }
