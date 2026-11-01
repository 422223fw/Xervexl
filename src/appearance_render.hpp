#pragma once
inline json default_appearance(){return {{"skin",{.69,.49,.34}},{"hair",{.19,.15,.11}},{"cloth",{.21,.34,.32}},{"trousers",{.18,.18,.16}},{"accent",{.91,.64,.29}},{"tunic_pattern","plain"},{"hair_style","cropped"},{"cape",{{"style","none"},{"colour",{.25,.12,.16}},{"trim",{.91,.64,.29}},{"pattern","plain"},{"length",1.15}}}};}
inline Colour rgb(const json& value,Colour fallback){if(!value.is_array()||value.size()!=3)return fallback;return {value[0].get<float>(),value[1].get<float>(),value[2].get<float>()};}
inline Colour appearance_colour(const json& f,const char* key,Colour fallback){auto a=f.value("appearance",json::object());return a.contains(key)?rgb(a[key],fallback):fallback;}
inline void character_cape(Canvas& c,const json& f,Vec p,Vec front,Vec side,float time,bool distant=false){
    auto a=f.value("appearance",json::object());auto cape=a.value("cape",json::object());std::string style=cape.value("style",std::string("none"));if(style=="none")return;
    Colour cloth=rgb(cape.value("colour",json{}),{.25f,.12f,.16f}),trim=rgb(cape.value("trim",json{}),GOLD);std::string pattern=cape.value("pattern",std::string("plain"));
    float length=std::clamp(cape.value("length",1.15f),.6f,1.35f)*(style=="short"?.57f:1.f),speed=std::min(1.f,std::hypot(f.value("move_x",0.f),f.value("move_z",0.f))/4.4f);int rows=distant?4:10,columns=distant?4:8;
    auto point=[&](float u,float v){float across=(u-.5f)*(.68f+v*.30f),wind=std::sin(time*2.5f-v*4.2f+u*2.2f)*v*v*(.04f+.08f*speed),trail=.30f+v*v*(.07f+speed*.40f)+wind;return p+side*across-front*trail+Vec{0,1.48f-v*length+std::sin(time*3.1f+u*2)*.018f*v,0};};
    for(int y=0;y<rows;y++)for(int x=0;x<columns;x++){
        float u=x/float(columns),v=y/float(rows),du=1.f/columns,dv=1.f/rows,mid=u+du*.5f,down=v+dv*.5f;
        if(style=="split"&&v>.5f&&std::abs(mid-.5f)<.12f)continue;
        bool emblem=(pattern=="stripe"&&std::abs(mid-.5f)<.13f)||(pattern=="chevron"&&std::abs(down-(.28f+std::abs(mid-.5f)*.7f))<.07f)||(pattern=="sun"&&std::hypot((mid-.5f)*1.5f,down-.45f)<.18f);
        bool edge=x==0||x==columns-1||y==rows-1;Colour col=(emblem||edge)?trim:cloth;col=col*(.92f+.08f*std::cos(mid*PI*3));
        c.quad(point(u,v),point(u+du,v),point(u+du,v+dv),point(u,v+dv),col);
    }
    Colour clasp=appearance_colour(f,"accent",GOLD);for(int sign:{-1,1})c.ellipsoid(p+side*(sign*.29f)-front*.25f+Vec{0,1.47f,0},{.045f,.045f,.045f},clasp,0,3,5);
}
inline void tunic_decoration(Canvas& c,const json& f,Vec p,Vec front,Vec side){
    std::string pattern=f.value("appearance",json::object()).value("tunic_pattern",std::string("plain"));if(pattern=="plain")return;
    Colour trim=appearance_colour(f,"accent",GOLD);Vec chest=p+front*.24f+Vec{0,1.22f,0};
    if(pattern=="stripe")c.beam(chest-Vec{0,.25f,0},chest+Vec{0,.25f,0},.035f,trim);
    else if(pattern=="chevron"){c.beam(chest-side*.22f+Vec{0,.15f,0},chest-Vec{0,.05f,0},.025f,trim);c.beam(chest+side*.22f+Vec{0,.15f,0},chest-Vec{0,.05f,0},.025f,trim);}
    else{for(int i=0;i<12;i++){float a=i*PI/6,b=(i+1)*PI/6;c.beam(chest+side*(std::cos(a)*.10f)+Vec{0,std::sin(a)*.10f,0},chest+side*(std::cos(b)*.10f)+Vec{0,std::sin(b)*.10f,0},.012f,trim);}}
}
