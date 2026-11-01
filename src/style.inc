    json& style_colour(){const char* parts[]={"skin","hair","cloth","trousers","accent"};return stylePart<5?styleDraft[parts[stylePart]]:styleDraft["cape"][stylePart==5?"colour":"trim"];}
    void style_view(){
        canvas.rect(22,18,465,720,{.035f,.055f,.06f,.97f});canvas.border(22,18,465,720,{.3f,.35f,.31f});canvas.text(43,36,"STYLE STUDIO",3.3f,GOLD);canvas.text(43,80,"YOUR SKIN / YOUR COLOURS / YOUR CAPE",1.25f,MUTED);
        const char* parts[]={"SKIN","HAIR","TUNIC","TROUSERS","ACCENT","CAPE","CAPE TRIM"};
        for(int i=0;i<7;i++)if(button(43+(i%3)*143.f,116+(i/3)*44.f,133,35,parts[i],stylePart==i))stylePart=i;
        const Colour palette[]={{.12f,.15f,.17f},{.91f,.88f,.78f},{.67f,.20f,.18f},{.20f,.37f,.65f},{.23f,.47f,.33f},{.48f,.26f,.59f},{.92f,.65f,.25f},{.45f,.27f,.15f},{.69f,.49f,.34f},{.90f,.72f,.57f},{.35f,.23f,.18f},{.35f,.65f,.69f}};
        for(int i=0;i<12;i++){float x=43+(i%6)*71.f,y=257+(i/6)*43.f;canvas.rect(x,y,60,33,palette[i]);canvas.border(x,y,60,33,MUTED);if(hover(x,y,60,33)&&clicked&&!busy)style_colour()={palette[i].r,palette[i].g,palette[i].b};}
        const char* channels[]={"RED","GREEN","BLUE"};for(int i=0;i<3;i++){float y=352+i*41.f;float value=style_colour()[i];canvas.text(43,y+10,channels[i],1.45f,MUTED);canvas.rect(122,y+13,205,8,{.15f,.19f,.18f});canvas.rect(122,y+13,205*value,8,GOLD);
            if(button(343,y,51,30,"-"))style_colour()[i]=std::max(0.f,value-.05f);if(button(407,y,51,30,"+"))style_colour()[i]=std::min(1.f,value+.05f);
        }
        const char* capes[]={"none","short","long","split"};for(int i=0;i<4;i++)if(button(43+i*107.f,493,99,34,capes[i],styleDraft["cape"].value("style",std::string{})==capes[i]))styleDraft["cape"]["style"]=capes[i];
        const char* patterns[]={"plain","stripe","chevron","sun"};for(int i=0;i<4;i++)if(button(43+i*107.f,537,99,34,patterns[i],styleDraft["cape"].value("pattern",std::string{})==patterns[i]))styleDraft["cape"]["pattern"]=patterns[i];
        canvas.text(43,589,"CAPE LENGTH",1.4f,MUTED);float length=styleDraft["cape"].value("length",1.15f);canvas.text(202,589,std::to_string(length).substr(0,4)+"M",1.4f,GOLD);
        if(button(343,578,51,32,"-"))styleDraft["cape"]["length"]=std::max(.6f,length-.05f);if(button(407,578,51,32,"+"))styleDraft["cape"]["length"]=std::min(1.35f,length+.05f);
        if(button(43,633,415,53,"SAVE SKIN & CAPE",true)){if(require_sign_in())return;net.queue("/appearance/save",{{"appearance",styleDraft}});}
        canvas.text(43,705,"COSMETIC ONLY / VISIBLE TO OTHER PLAYERS",1.15f,MUTED);
        if(button(1082,24,151,43,"BACK")){screen=Screen::Home;focus=-1;}
        if(button(535,675,177,43,"TURN LEFT"))styleYaw-=.6f;if(button(727,675,177,43,"TURN RIGHT"))styleYaw+=.6f;
        if(button(535,728,369,43,styleWalking?"PREVIEW / WALKING":"PREVIEW / STANDING"))styleWalking=!styleWalking;
        if(button(974,580,259,42,"TUNIC PATTERN")){std::string current=styleDraft.value("tunic_pattern",std::string("plain"));for(int i=0;i<4;i++)if(current==patterns[i]){styleDraft["tunic_pattern"]=patterns[(i+1)%4];break;}}
        canvas.text(974,635,styleDraft.value("tunic_pattern",std::string("plain")),1.5f,GOLD);
        if(button(974,686,259,42,"HAIR STYLE")){const char* hair[]={"cropped","crest","bald"};std::string current=styleDraft.value("hair_style",std::string("cropped"));for(int i=0;i<3;i++)if(current==hair[i]){styleDraft["hair_style"]=hair[(i+1)%3];break;}}
        canvas.text(974,744,styleDraft.value("hair_style",std::string("cropped")),1.5f,GOLD);
    }
    void techniques_view(){
        realm_header("RANK TECHNIQUES","EVERY NEW RANK UNLOCKS ANOTHER COMBINATION / P CHOOSE / O PERFORM");
        int pages=techniques.value("pages",1);auto items=techniques.value("items",json::array());int selected=profile.value("selected_technique",0);
        canvas.text(47,119,"RANK "+std::to_string(level)+" / "+std::to_string(profile.value("technique_count",0))+" TECHNIQUES UNLOCKED",1.7f,GOLD);
        for(int i=0;i<int(items.size());i++){
            auto t=items[i];float x=47+(i%2)*602.f,y=167+(i/2)*120.f;bool unlocked=t.value("unlocked",false);int rank=t.value("rank",2);bool active=selected==rank;
            canvas.rect(x,y,584,106,{.075f,.11f,.12f});canvas.border(x,y,584,106,active?GOLD:Colour{.20f,.27f,.25f});canvas.text(x+14,y+10,t.value("name",std::string{}),1.9f,unlocked?WHITE:MUTED);
            std::string chain;for(auto& move:t["moves"]){if(!chain.empty())chain+=" / ";chain+=move.get<std::string>();}if(chain.size()>65)chain=chain.substr(0,62)+"...";
            canvas.text(x+14,y+40,chain,1.15f,MUTED);canvas.text(x+14,y+75,"RANK "+std::to_string(rank)+" / "+std::to_string(t.value("stamina",0))+" STAMINA",1.2f,GOLD);
            if(button(x+365,y+66,205,29,!unlocked?"LOCKED":active?"SELECTED":"SELECT",active)&&unlocked)net.queue("/techniques/select",{{"rank",rank}});
        }
        if(button(47,673,139,41,"PREVIOUS"))open_techniques(std::max(0,techniques.value("page",0)-1));if(button(200,673,139,41,"NEXT"))open_techniques(std::min(pages-1,techniques.value("page",0)+1));
        canvas.text(367,689,"PAGE "+std::to_string(techniques.value("page",0)+1)+" / "+std::to_string(pages),1.4f,MUTED);
        canvas.text(47,744,"Normal stamina and recovery apply to every swing. Block, dodge or use a manual attack to cancel.",1.35f,MUTED);
    }
