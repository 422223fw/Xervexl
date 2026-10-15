    void modes_view(){
        canvas.rect(0,0,1280,800,{.025f,.041f,.044f,.98f});canvas.text(47,29,"CHOOSE YOUR BATTLE",3.5f,GOLD);
        canvas.text(47,77,"SQUADS, SURVIVAL, DUELS AND WORLDS BUILT IN THE WORKSHOP. ENTRY IS FREE.",1.35f,MUTED);
        if(button(894,24,220,46,"WORLD WORKSHOP")){screen=Screen::Workshop;focus=-1;}
        if(button(1127,24,106,46,"BACK")){screen=Screen::Home;focus=-1;}
        int pages=std::max(1,(static_cast<int>(modes.size())+7)/8);modePage=std::clamp(modePage,0,pages-1);
        for(int i=0;i<8;i++){int index=modePage*8+i;if(index>=static_cast<int>(modes.size()))break;const auto& mode=modes[index];float x=47+(i%4)*301,y=157+(i/4)*263;
            canvas.rect(x,y,285,245,{.08f,.12f,.13f});canvas.border(x,y,285,245,{.24f,.32f,.30f});
            canvas.text(x+14,y+15,mode.value("ranked",true)?"OFFICIAL / XP + CROWNS + SKILL":"WORKSHOP / MATCH REWARDS",1.05f,GOLD);
            canvas.text(x+14,y+50,mode.value("name",std::string{}),1.7f,WHITE);
            canvas.text(x+14,y+86,std::to_string(mode.value("players",100))+" FIGHTERS / "+std::to_string(mode.value("team_size",4))+" PER TEAM",1.2f,MUTED);
            canvas.text(x+14,y+116,mode.value("survival",true)?"LAST TEAM STANDING":"FIRST TO "+std::to_string(mode.value("goal",20))+" ELIMINATIONS",1.25f,WHITE);
            canvas.text(x+14,y+143,mode.value("revives",false)?"HOLD H NEAR A TEAMMATE TO REVIVE":"BOTS FILL EMPTY PLACES",1.1f,MUTED);
            if(button(x+14,y+177,257,37,"PLAY",true))enter_mode(mode.value("id",std::string{}));
            if(!mode.value("ranked",true)&&button(x+14,y+219,257,23,"OPEN IN EDITOR")){screen=Screen::Workshop;net.queue("/workshop/load",{{"id",mode["id"]}});}
        }
        canvas.text(47,716,"PAGE "+std::to_string(modePage+1)+" / "+std::to_string(pages),1.4f,MUTED);
        if(button(931,711,139,38,"PREVIOUS")&&modePage>0)modePage--;if(button(1083,711,149,38,"NEXT")&&modePage+1<pages)modePage++;
        canvas.text(47,764,"OFFICIAL SURVIVAL VICTORY: 650 XP / 350 CROWNS / 25 SKILL FOR EACH SQUAD MEMBER.",1.3f,GOLD);
    }
    void workshop_view(){
        static const char* biomes[]={"DESERT","FOREST","SNOW","COAST","VOLCANIC","AUTUMN","MOONLIT","MARSH"};
        static const char* kinds[]={"rock","tree","ruin","pillar"};
        canvas.rect(0,0,1280,800,{.025f,.041f,.044f,.99f});canvas.text(47,29,"WORLD & MODE WORKSHOP",3.3f,GOLD);
        canvas.text(47,77,"DESIGN A WORLD. WRITE EVENT RULES. SAVE IT AND PLAY WITH BOTS OR FRIENDS.",1.3f,MUTED);
        if(button(1010,24,106,46,"NEW")){editorId.clear();fields[5]="My Arena";editorProps=json::array();focus=-1;}
        if(button(1127,24,106,46,"BACK")){screen=Screen::Modes;focus=-1;}
        for(int i=0;i<4;i++)if(button(47+i*174,117,164,35,kinds[i],editorKind==i)){editorKind=i;focus=-1;}
        if(button(770,117,463,35,std::string("BIOME: ")+biomes[editorBiome]))editorBiome=(editorBiome+1)%8;
        canvas.rect(47,165,700,490,{.10f,.15f,.13f});canvas.circle(397,410,228,{.17f,.23f,.19f});
        for(int i=-6;i<=6;i++){canvas.line(397+i*30,190,397+i*30,630,1,{.24f,.30f,.25f,.6f});canvas.line(177,410+i*30,617,410+i*30,1,{.24f,.30f,.25f,.6f});}
        for(const auto& prop:editorProps){float x=397+prop.value("x",0.f)*6,y=410+prop.value("z",0.f)*6;std::string kind=prop.value("kind",std::string{});Colour tint=kind=="tree"?Colour{.35f,.55f,.30f}:kind=="rock"?Colour{.55f,.58f,.53f}:GOLD;canvas.circle(x,y,prop.value("radius",1.f)*6,tint);if(kind=="ruin")canvas.rect(x-4,y-4,8,8,tint);}
        canvas.text(66,180,"TOP VIEW / CLICK TO PLACE / RIGHT CLICK TO ERASE",1.1f,MUTED);
        if(hover(47,210,700,420)&&(clicked||rightClicked)){
            float x=std::round((mouseX-397)/6),z=std::round((mouseY-410)/6);focus=-1;
            if(rightClicked){int nearest=-1;float distance=4;for(int i=0;i<static_cast<int>(editorProps.size());i++){float d=std::hypot(editorProps[i].value("x",0.f)-x,editorProps[i].value("z",0.f)-z);if(d<distance){nearest=i;distance=d;}}if(nearest>=0)editorProps.erase(nearest);}
            else if(std::hypot(x,z)<=32&&editorProps.size()<80){bool free=true;for(auto& p:editorProps)if(std::hypot(p.value("x",0.f)-x,p.value("z",0.f)-z)<editorRadius+p.value("radius",1.f)+.6f)free=false;if(free)editorProps.push_back({{"x",x},{"z",z},{"radius",editorRadius},{"height",editorHeight},{"kind",kinds[editorKind]}});else toast("Leave walking space between objects.");}
        }
        field(770,173,463,"WORLD NAME",5);
        if(button(770,255,220,32,"PLAYERS: "+std::to_string(editorPlayers))){int choices[]={8,20,40,100};int i=0;while(i<3&&choices[i]!=editorPlayers)i++;editorPlayers=choices[(i+1)%4];if(editorPlayers%editorTeam)editorTeam=4;}
        if(button(1005,255,228,32,"TEAM SIZE: "+std::to_string(editorTeam))){int choices[]={1,2,4,10};int i=0;while(i<3&&choices[i]!=editorTeam)i++;do{i=(i+1)%4;}while(editorPlayers%choices[i]);editorTeam=choices[i];}
        canvas.text(770,308,"EVENT CODE / CLICK TO TYPE / ENTER: NEW LINE",1.2f,GOLD);
        canvas.rect(770,337,463,180,{.035f,.06f,.065f});canvas.border(770,337,463,180,focus==6?GOLD:MUTED);if(hover(770,337,463,180)&&clicked)focus=6;
        std::istringstream lines(fields[6]);std::vector<std::string> code;std::string line;while(std::getline(lines,line))code.push_back(line);int begin=std::max(0,static_cast<int>(code.size())-8);
        for(int i=begin;i<static_cast<int>(code.size());i++)canvas.text(782,347+(i-begin)*20,code[i].substr(0,53),1.15f,WHITE);
        canvas.text(770,531,"on kill if head heal 20\non revive score 25 / on start weapon bow\nEvents: start kill down revive win\nActions: heal stamina score xp coins weapon",1.1f,MUTED);
        if(button(770,626,463,35,editorSurvival?"SURVIVAL / LAST TEAM STANDING":"RESPAWNS / FIRST TO 20 ELIMINATIONS"))editorSurvival=!editorSurvival;
        if(button(47,670,150,36,"SIZE -"))editorRadius=std::max(.5f,editorRadius-.5f);if(button(207,670,150,36,"SIZE +"))editorRadius=std::min(3.f,editorRadius+.5f);
        if(button(367,670,150,36,"HEIGHT -"))editorHeight=std::max(1.f,editorHeight-1);if(button(527,670,150,36,"HEIGHT +"))editorHeight=std::min(8.f,editorHeight+1);
        canvas.text(47,720,std::to_string(editorProps.size())+" / 80 OBJECTS / RADIUS "+std::to_string(editorRadius).substr(0,3)+" / HEIGHT "+std::to_string(static_cast<int>(editorHeight)),1.3f,MUTED);
        if(button(770,682,220,47,"SAVE WORLD",true)&&!require_sign_in())net.queue("/workshop/save",{{"id",editorId},{"name",fields[5]},{"biome",editorBiome},{"props",editorProps},{"code",fields[6]},{"players",editorPlayers},{"team_size",editorTeam},{"survival",editorSurvival}});
        if(button(1005,682,228,47,"PLAY SAVED WORLD",true)){if(editorId.empty())toast("Save your world first.");else enter_mode(editorId);}
        canvas.text(47,765,"WORKSHOP SCRIPTS CHANGE THIS MATCH. GLOBAL ACCOUNT REWARDS COME FROM OFFICIAL MODES.",1.25f,MUTED);
    }
