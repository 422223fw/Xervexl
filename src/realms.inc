    void realm_header(const std::string& title,const std::string& subtitle){
        canvas.rect(0,0,1280,800,{.035f,.055f,.059f,.98f});canvas.text(45,28,title,3.6f,GOLD);canvas.text(47,80,subtitle,1.4f,MUTED);
        if(button(1125,26,110,45,"BACK")){screen=Screen::Home;focus=-1;}
    }
    void friends_view(){
        realm_header("FRIENDS","REAL PLAYERS / MUTUAL REQUESTS / JOIN YOUR FRIENDS' WORLDS ON THIS SERVER");
        field(47,115,375,"REGISTERED USERNAME",7);if(button(438,137,180,43,"SEND REQUEST",true)){net.queue("/social/request",{{"username",fields[7]}});focus=-1;}
        if(button(850,137,385,43,"MY WORLDS"))open_realms();
        auto friends=social.value("friends",json::array());auto incoming=social.value("incoming",json::array());auto outgoing=social.value("outgoing",json::array());
        canvas.text(47,213,"YOUR FRIENDS / "+std::to_string(friends.size()),2,GOLD);canvas.text(701,213,"INCOMING REQUESTS / "+std::to_string(incoming.size()),2,GOLD);
        int pages=std::max(1,(int(friends.size())+5)/6);friendPage=std::clamp(friendPage,0,pages-1);
        for(int i=0;i<6;i++){int index=friendPage*6+i;if(index>=int(friends.size()))break;const auto& f=friends[index];float y=253+i*67.f;std::string name=f.value("username",std::string{});
            canvas.rect(47,y,600,58,{.08f,.12f,.125f});canvas.circle(65,y+19,4,f.value("online",false)?Colour{.39f,.78f,.55f}:MUTED);canvas.text(81,y+10,name,1.8f,WHITE);
            canvas.text(81,y+34,f.value("online",false)?f.value("world_name",std::string("ONLINE")):"OFFLINE",1.15f,MUTED);
            std::string id=f.value("realm_id",std::string{});if(!id.empty()&&button(426,y+9,100,38,"JOIN",true))join_realm(id);
            if(button(536,y+9,100,38,"REMOVE"))net.queue("/social/remove",{{"username",name}});
        }
        for(int i=0;i<std::min(5,int(incoming.size()));i++){float y=253+i*67.f;std::string name=incoming[i].value("username",std::string{});canvas.rect(701,y,534,58,{.08f,.12f,.125f});canvas.text(716,y+19,name,1.7f);
            if(button(995,y+9,112,38,"ACCEPT",true))net.queue("/social/respond",{{"username",name},{"accept",true}});
            if(button(1117,y+9,106,38,"DECLINE"))net.queue("/social/respond",{{"username",name},{"accept",false}});
        }
        if(friends.empty())canvas.text(47,266,"Send a request. Your friend must accept it.",1.6f,MUTED);
        canvas.text(701,615,"OUTGOING / "+std::to_string(outgoing.size()),1.5f,MUTED);for(int i=0;i<std::min(3,int(outgoing.size()));i++)canvas.text(701,645+i*24.f,outgoing[i].value("username",std::string{})+" / WAITING",1.35f,MUTED);
        if(button(47,713,125,38,"PREVIOUS"))friendPage=std::max(0,friendPage-1);if(button(184,713,125,38,"NEXT"))friendPage=std::min(pages-1,friendPage+1);
        canvas.text(47,770,"Bots cannot receive requests. Friends must connect to the same server address.",1.3f,MUTED);
    }
    void realms_view(){
        realm_header("MY WORLDS","BUILD / MINE / CRAFT / EXPLORE / YOUR CONFIRMED FRIENDS CAN JOIN");
        canvas.text(47,125,"WORLDS YOU CAN ENTER",2,GOLD);int pages=std::max(1,(int(realms.size())+5)/6);realmPage=std::clamp(realmPage,0,pages-1);
        for(int i=0;i<6;i++){int index=realmPage*6+i;if(index>=int(realms.size()))break;auto r=realms[index];std::string id=r.value("id",std::string{});float y=167+i*76.f;
            canvas.rect(47,y,635,66,{.075f,.115f,.12f});canvas.text(61,y+10,r.value("name",std::string{}),2,WHITE);canvas.text(61,y+38,r.value("owner",std::string{})+" / "+std::to_string(r.value("online",0))+" ONLINE / "+(r.value("mine",false)?"YOURS":"FRIEND'S WORLD"),1.2f,MUTED);
            if(button(561,y+13,108,40,"ENTER",true))join_realm(id);
            if(r.value("mine",false)&&button(436,y+13,113,40,"SETTINGS")){selectedRealm=id;fields[8]=r.value("name",std::string{});auto s=r["settings"];realmMobs=s.value("mobs",true);realmBots=s.value("bots",false);realmPvp=s.value("pvp",false);realmFriendsBuild=s.value("friends_build",true);focus=-1;}
        }
        if(realms.empty())canvas.text(47,177,"Create your first world, or accept a friend's request.",1.5f,MUTED);
        canvas.rect(715,122,520,548,{.07f,.105f,.11f});canvas.text(739,142,selectedRealm.empty()?"CREATE A WORLD":"WORLD SETTINGS",2.2f,GOLD);
        field(739,191,470,"WORLD NAME",8);
        if(button(739,283,470,43,std::string("WILD CREATURES / ")+(realmMobs?"ON":"OFF"),realmMobs))realmMobs=!realmMobs;
        if(button(739,337,470,43,std::string("SPARRING BOTS / ")+(realmBots?"ON":"OFF"),realmBots))realmBots=!realmBots;
        if(button(739,391,470,43,std::string("FRIENDS CAN BUILD / ")+(realmFriendsBuild?"YES":"NO"),realmFriendsBuild))realmFriendsBuild=!realmFriendsBuild;
        if(button(739,445,470,43,std::string("PLAYER COMBAT / ")+(realmPvp?"ON":"OFF"),realmPvp))realmPvp=!realmPvp;
        if(button(739,513,470,53,selectedRealm.empty()?"CREATE WORLD":"SAVE SETTINGS",true)){
            json body={{"name",fields[8]},{"mobs",realmMobs},{"bots",realmBots},{"pvp",realmPvp},{"friends_build",realmFriendsBuild}};
            if(selectedRealm.empty())net.queue("/realms/create",body);else{body["id"]=selectedRealm;net.queue("/realms/settings",body);}focus=-1;
        }
        if(button(739,583,225,40,"NEW WORLD")){selectedRealm.clear();fields[8]="My World";focus=-1;}
        if(button(977,583,232,40,"FRIENDS"))open_friends();
        if(button(47,657,125,38,"PREVIOUS"))realmPage=std::max(0,realmPage-1);if(button(185,657,125,38,"NEXT"))realmPage=std::min(pages-1,realmPage+1);
        canvas.text(47,721,"Worlds and crafted equipment are saved on this server. Arena equipment stays in the arena.",1.4f,MUTED);
        canvas.text(47,750,"TAB build / fight. Hold left click to mine; right click to place. E opens crafting and building shapes.",1.3f,GOLD);
    }
    void crafting_view(){
        realm_header("CRAFT & BUILD","GATHER MATERIALS / FORGE EQUIPMENT / FIVE BUILDING SHAPES");
        if(!survival()){canvas.text(47,150,"Enter one of your survival worlds first.",2,MUTED);return;}
        auto s=world["survival"];auto resources=s.value("resources",json::object());auto recipes=s.value("recipes",json::object());
        std::string bag;for(auto it=resources.begin();it!=resources.end();++it)bag+=it.key()+": "+std::to_string(it.value().get<int>())+"   ";if(bag.empty())bag="No materials yet. TAB enters building mode. Mine wood, leaves and stone to begin.";
        canvas.text(47,120,bag.substr(0,130),1.4f,GOLD);
        std::vector<std::pair<std::string,json>> list;for(auto it=recipes.begin();it!=recipes.end();++it)list.push_back({it.key(),it.value()});int pages=std::max(1,(int(list.size())+7)/8);craftPage=std::clamp(craftPage,0,pages-1);
        for(int i=0;i<8;i++){int index=craftPage*8+i;if(index>=int(list.size()))break;auto [id,cost]=list[index];float x=47+(i%2)*353.f,y=169+(i/2)*118.f;bool enough=true,owned=false;std::string needs;
            if(profile.contains("inventory"))for(auto& item:profile["inventory"])if(item==id)owned=true;
            for(auto it=cost.begin();it!=cost.end();++it){int count=it.value();if(resources.value(it.key(),0)<count)enough=false;needs+=it.key()+" "+std::to_string(count)+"  ";}
            canvas.rect(x,y,337,105,{.08f,.12f,.125f});canvas.text(x+13,y+10,id,1.9f,WHITE);canvas.text(x+13,y+39,needs.substr(0,43),1.2f,MUTED);
            if(button(x+13,y+63,311,31,owned?"EQUIP":enough?"CRAFT & EQUIP":"MATERIALS NEEDED",enough||owned)&&(enough||owned))net.queue(owned?"/realms/equip":"/realms/craft",{{"item",id}});
        }
        canvas.text(776,169,"BUILDING KIT",2.2f,GOLD);canvas.text(776,206,"MATERIAL / [,] CYCLE IN WORLD",1.3f,MUTED);
        for(int i=0;i<5;i++)if(button(776+(i%2)*231.f,236+(i/2)*46.f,218,36,std::string(materials[i])+" / "+std::to_string(resources.value(materials[i],0)),buildMaterial==i))buildMaterial=i;
        canvas.text(776,392,"SHAPE / [ AND ] CYCLE IN WORLD",1.3f,MUTED);
        for(int i=0;i<5;i++)if(button(776+(i%2)*231.f,421+(i/2)*46.f,218,36,shapes[i],buildShape==i))buildShape=i;
        if(button(776,576,449,40,"ROTATE / R / "+std::to_string(buildRotation*90)+" DEGREES"))buildRotation=(buildRotation+1)%4;
        if(button(776,632,449,48,"RETURN TO WORLD",true)){screen=Screen::Home;focus=-1;}
        if(button(47,672,139,40,"PREVIOUS"))craftPage=std::max(0,craftPage-1);if(button(200,672,139,40,"NEXT"))craftPage=std::min(pages-1,craftPage+1);
        canvas.text(47,742,"Hold to mine. A pickaxe mines hard materials faster. Leaves provide fibre; ore can be forged into iron.",1.35f,MUTED);
    }
    void survival_hud(){
        if(!survival())return;auto s=world["survival"];canvas.rect(330,207,620,58,{.035f,.055f,.06f,.94f});
        canvas.text(346,217,buildMode?"BUILD / HOLD LMB MINE / RMB PLACE / TAB FIGHT":"SURVIVAL / TAB BUILD / E CRAFT / J FRIENDS",1.45f,GOLD);
        canvas.text(346,241,std::string(materials[buildMaterial])+" / "+shapes[buildShape]+" / R ROTATE / [ ] SHAPE / , . MATERIAL",1.2f,MUTED);
        if(buildMode){float p=s.value("mine_progress",0.f);canvas.rect(560,437,160,5,{.1f,.14f,.14f});canvas.rect(560,437,160*p,5,GOLD);}
    }
