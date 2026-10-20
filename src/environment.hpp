#pragma once

inline Colour colour_mix(Colour a,Colour b,float t){return {a.r+(b.r-a.r)*t,a.g+(b.g-a.g)*t,a.b+(b.b-a.b)*t,a.a+(b.a-a.a)*t};}
struct WorldPalette {
    Colour ground,stone,skyTop,horizon,foliage,water;
    float ambient=.52f,direct=.48f,haze=130;
};
inline WorldPalette world_palette(const std::string& biome){
    if(biome=="forest")return {{.31f,.39f,.25f},{.48f,.48f,.40f},{.26f,.43f,.53f},{.71f,.77f,.65f},{.24f,.39f,.23f},{.26f,.43f,.44f}};
    if(biome=="snow")return {{.79f,.84f,.85f},{.54f,.62f,.65f},{.29f,.48f,.65f},{.80f,.86f,.89f},{.28f,.42f,.37f},{.35f,.58f,.67f},.61f,.39f,160};
    if(biome=="coast")return {{.68f,.64f,.46f},{.57f,.57f,.48f},{.22f,.48f,.65f},{.77f,.85f,.83f},{.32f,.43f,.25f},{.16f,.44f,.54f},.55f,.45f,155};
    if(biome=="volcanic")return {{.27f,.25f,.24f},{.34f,.32f,.31f},{.23f,.20f,.23f},{.58f,.39f,.28f},{.23f,.27f,.22f},{.95f,.32f,.055f},.46f,.49f,100};
    if(biome=="autumn")return {{.46f,.36f,.23f},{.59f,.51f,.40f},{.39f,.40f,.49f},{.90f,.69f,.46f},{.69f,.35f,.13f},{.34f,.44f,.43f},.56f,.44f,125};
    if(biome=="night")return {{.25f,.30f,.31f},{.42f,.48f,.51f},{.035f,.065f,.12f},{.22f,.32f,.40f},{.20f,.31f,.28f},{.18f,.33f,.41f},.43f,.32f,110};
    if(biome=="marsh")return {{.26f,.34f,.26f},{.42f,.46f,.38f},{.29f,.42f,.43f},{.66f,.73f,.61f},{.26f,.40f,.28f},{.25f,.41f,.38f},.59f,.34f,85};
    return {{.65f,.55f,.39f},{.64f,.56f,.43f},{.30f,.48f,.62f},{.88f,.79f,.62f},{.35f,.42f,.25f},{.22f,.45f,.54f},.52f,.48f,145};
}
inline float scenery_random(int seed,int index){
    unsigned n=static_cast<unsigned>(seed)^((static_cast<unsigned>(index)+1)*747796405u);
    n=(n^(n>>16))*2246822519u;n=(n^(n>>13))*3266489917u;n^=n>>16;
    return (n&0xffffff)/16777216.f;
}
inline void ground_shadow(Canvas& c,Vec p,float rx,float rz,float alpha){
    for(int i=0;i<12;i++){float a=i*2*PI/12,b=(i+1)*2*PI/12;
        c.tri3(p,p+Vec{std::sin(a)*rx,0,std::cos(a)*rz},p+Vec{std::sin(b)*rx,0,std::cos(b)*rz},{.09f,.12f,.10f,alpha},false);
    }
}
inline void scenery_tree(Canvas& c,Vec p,float radius,float height,Colour leaves,float time,int variation,bool snow=false){
    Colour bark{.30f,.24f,.17f};
    c.cylinder(p,radius*.58f,height*.85f,bark,7,radius*.22f);
    Vec crown=p+Vec{0,height*.80f,0},sway{std::sin(time*.85f+variation)*.09f,0,std::cos(time*.67f+variation)*.06f};
    Vec sight=c.focus-c.camera;float t=std::clamp(dot(crown-c.camera,sight)/std::max(.001f,dot(sight,sight)),0.f,1.f);
    if(dot(crown-c.camera,crown-c.camera)<radius*radius*10.2f||(c.following&&dot(c.camera+sight*t-crown,c.camera+sight*t-crown)<radius*radius*7.3f))leaves.a=.15f;
    int lobes=dot(crown-c.camera,crown-c.camera)>32*32?1:3;
    for(int j=0;j<lobes;j++){
        float a=j*2*PI/3+variation*.7f;Vec branch{std::sin(a)*radius*.90f,height*(.57f+j*.055f),std::cos(a)*radius*.90f};
        if(lobes>1)c.beam(p+Vec{0,height*.45f,0},p+branch,radius*.10f,bark);
        Vec top=lobes==1?crown:p+branch+Vec{0,height*.18f,0};
        Vec scale=lobes==1?Vec{radius*2.4f,height*.38f,radius*2.4f}:Vec{radius*1.75f,height*.30f,radius*1.65f};
        c.ellipsoid(top+sway,scale,leaves*(.90f+j*.065f),a,3,8);
        if(snow)c.ellipsoid(top+sway+Vec{0,scale.y*.48f,0},{scale.x*.85f,scale.y*.47f,scale.z*.85f},{.81f,.86f,.85f,leaves.a},a,2,8);
    }
}
inline void environment(Canvas& c,float time,const json& world=json::object()){
    std::string biome=world.value("biome",std::string("desert"));int seed=world.value("seed",0);
    bool snow=biome=="snow",forest=biome=="forest",coast=biome=="coast",lava=biome=="volcanic",autumn=biome=="autumn",night=biome=="night",marsh=biome=="marsh";
    auto palette=world_palette(biome);
    c.ambient=palette.ambient;c.sunlight=palette.direct;c.fogColour=palette.horizon;c.fogStart=night||marsh?24:36;c.fogRange=palette.haze;
    c.sunDirection=norm({-.48f,autumn?.54f:.85f,.32f});
    for(int i=0;i<40;i++)c.rect(0,i*20.f,1280,20,colour_mix(palette.skyTop,palette.horizon,std::min(1.f,i/24.f)));
    // Celestial bodies and clouds have world bearings, so they follow camera turns.
    float sx,sy,sd;Vec sun=c.camera+c.sunDirection*180;
    if(c.project(sun,sx,sy,sd)){
        c.circle(sx,sy,night?19:48,night?Colour{.72f,.81f,.90f,.10f}:Colour{1,.84f,.54f,.07f});
        c.circle(sx,sy,night?11:22,night?Colour{.86f,.91f,.92f}:Colour{1,.91f,.71f});
        if(night)c.circle(sx+4,sy-3,10,palette.skyTop);
    }
    if(night)for(int i=0;i<80;i++){
        float a=scenery_random(seed,i)*2*PI,h=.17f+scenery_random(seed,i+190)*.78f;
        Vec star=c.camera+Vec{std::sin(a)*std::sqrt(1-h*h),h,std::cos(a)*std::sqrt(1-h*h)}*160;
        if(c.project(star,sx,sy,sd))c.circle(sx,sy,i%9==0?1.5f:.7f,{.83f,.88f,.95f,.45f});
    }
    if(!night)for(int i=0;i<7;i++){
        float a=i*2*PI/7+.20f;Vec cloud{std::sin(a)*125+std::sin(time*.008f+i)*8,44.f+i%3*8,std::cos(a)*125};
        c.ellipsoid(cloud,{17,2.8f,7},{.91f,.91f,.85f,.42f},a,2,8);
    }
    // Layered ridgelines outside the walkable arena keep its collision floor flat.
    for(int layer=0;layer<2;layer++)for(int i=0;i<48;i++){
        float a=i*2*PI/48,b=(i+1)*2*PI/48,r=layer?110.f:80.f;
        float h=7+scenery_random(seed,i+layer*70)*22,h2=7+scenery_random(seed,(i+1)%48+layer*70)*22;
        Colour ridge=colour_mix(palette.stone,palette.horizon,layer?.63f:.33f);
        c.quad({std::sin(a)*r,-2,std::cos(a)*r},{std::sin(b)*r,-2,std::cos(b)*r},{std::sin(b)*r,h2,std::cos(b)*r},{std::sin(a)*r,h,std::cos(a)*r},ridge);
        if(snow)c.tri3({std::sin(a)*r,h,std::cos(a)*r},{std::sin(b)*r,h2,std::cos(b)*r},{std::sin(b)*r,h2-3,std::cos(b)*r},{.85f,.88f,.87f});
    }
    c.flush_layer();
    for(int x=-90;x<90;x+=6)for(int z=-90;z<90;z+=6){
        if(coast&&z<-48)continue;
        float shade=.94f+.10f*scenery_random(seed,(x+90)*31+z+90);
        Colour soil=palette.ground*shade;
        c.quad({float(x),-.05f,float(z)},{float(x+6),-.05f,float(z)},{float(x+6),-.05f,float(z+6)},{float(x),-.05f,float(z+6)},soil);
    }
    // These flat surfaces need stable layers in the shared painter renderer.
    // Sorting coplanar triangles by their centroids makes large floor wedges
    // overwrite paving and fighters as the camera moves.
    c.flush_layer();
    // Worn, unevenly coloured paving is surface decoration, never a hidden obstacle.
    for(int ring=0;ring<4;ring++)for(int i=0;i<40;i++){
        float a=(i+(ring%2)*.5f)*2*PI/40+.003f,b=a+2*PI/40-.006f,inner=ring*2.35f+.045f,outer=(ring+1)*2.35f-.045f;
        Colour stone=colour_mix(palette.stone,palette.ground,.20f)*(.87f+scenery_random(seed,i+ring*40)*.16f);
        c.quad({std::sin(a)*inner,-.025f,std::cos(a)*inner},{std::sin(b)*inner,-.025f,std::cos(b)*inner},{std::sin(b)*outer,-.025f,std::cos(b)*outer},{std::sin(a)*outer,-.025f,std::cos(a)*outer},stone);
    }
    if(coast){
        c.quad({-100,-.10f,-110},{100,-.10f,-110},{100,-.10f,-46},{-100,-.10f,-46},palette.water,false);
        for(int i=0;i<16;i++){float z=-48-i*2.8f+std::sin(time*.6f+i)*.20f;
            c.quad({-80,-.08f,z},{80,-.08f,z},{80,-.08f,z-.10f},{-80,-.08f,z-.10f},{.74f,.84f,.79f,.24f},false);}
    }
    if(marsh)for(int i=0;i<12;i++){
        float a=i*2*PI/12,r=17+(i%3)*5;Vec p{std::sin(a)*r,-.015f,std::cos(a)*r};
        for(int j=0;j<12;j++){float u=j*PI/6,v=(j+1)*PI/6;c.tri3(p,p+Vec{std::sin(u)*2.6f,0,std::cos(u)*1.7f},p+Vec{std::sin(v)*2.6f,0,std::cos(v)*1.7f},{palette.water.r,palette.water.g,palette.water.b,.82f},false);}
    }
    if(lava)for(int i=0;i<9;i++){float a=i*2*PI/9;Vec p{std::sin(a)*47,.015f,std::cos(a)*47};c.box(p,{8,.04f,1.5f},palette.water,a);}
    c.flush_layer();
    // Chipped stone courses, capstones and battlements share the existing boundary.
    for(int i=0;i<64;i++){
        float a=i*2*PI/64;Vec p{std::sin(a)*40,1.25f,std::cos(a)*40};Colour wall=palette.stone*(.92f+scenery_random(seed,i+400)*.12f);
        c.box(p,{3.9f,2.5f,1.6f},wall,a);c.box(p+Vec{0,1.35f,0},{3.9f,.20f,1.85f},palette.stone*1.08f,a);
        Vec inward{-std::sin(a),0,-std::cos(a)};
        c.box(p+inward*.81f,{3.87f,.045f,.025f},wall*.65f,a);
        if(i%2==0)c.box(p+Vec{0,1.70f,0},{1.25f,.55f,1.65f},wall,a);
        if(i%4==0){c.cylinder({p.x,0,p.z},1.10f,4.9f,wall,8);c.cylinder({p.x,4.9f,p.z},1.40f,.30f,palette.stone*1.08f,8);}
        if(i%8==0){
            Vec flag=p+Vec{0,3.2f,0};c.beam(flag-Vec{0,.4f,0},flag+Vec{0,2.8f,0},.045f,{.30f,.26f,.19f});
            for(int j=0;j<5;j++){float u=j/5.f,v=(j+1)/5.f,w=std::sin(time*1.9f+u*3+i)*u*.20f,w2=std::sin(time*1.9f+v*3+i)*v*.20f;
                c.quad(flag+Vec{u*1.6f,2.5f,w},flag+Vec{v*1.6f,2.5f,w2},flag+Vec{v*1.6f,1.05f-v*.12f,w2},flag+Vec{u*1.6f,1.05f-u*.12f,w},i%16?Colour{.22f,.36f,.36f}:Colour{.46f,.20f,.14f});}
            Vec torch=p+inward*1.1f+Vec{0,.3f,0};c.beam(torch-Vec{0,.6f,0},torch,.05f,{.25f,.20f,.15f});
            if(night||autumn||lava){float flicker=1+.08f*std::sin(time*8+i);c.ellipsoid(torch+Vec{0,.20f,0},{.10f,.26f*flicker,.10f},{1,.64f,.22f},0,3,6);}
        }
    }
    int trees=forest||autumn?32:18;
    for(int i=0;i<trees;i++){
        float a=i*2*PI/trees+seed*.00001f,r=49+scenery_random(seed,i+500)*8;
        Vec p{std::sin(a)*r,0,std::cos(a)*r};
        scenery_tree(c,p,.65f,5.5f+scenery_random(seed,i+700)*3,palette.foliage,time,i,snow);
    }
    if(world.contains("props"))for(const auto& prop:world["props"]){
        Vec p{prop.value("x",0.f),0,prop.value("z",0.f)};float radius=prop.value("radius",1.f),height=prop.value("height",2.f);
        std::string kind=prop.value("kind",std::string{});
        if(dot(p-c.camera,p-c.camera)<32*32)ground_shadow(c,p+Vec{.15f,.005f,.15f},radius*1.25f,radius*.85f,.18f);
        if(kind=="tree")scenery_tree(c,p,radius,height,palette.foliage,time,int(p.x*13+p.z*7),snow);
        else if(kind=="ruin"){
            c.box(p+Vec{0,height*.5f,0},{radius*1.7f,height,radius*1.3f},palette.stone);
            int courses=std::max(2,int(height/.45f));
            for(int j=1;j<courses;j++)c.box(p+Vec{0,j*height/courses,.006f},{radius*1.72f,.035f,radius*1.32f},palette.stone*.73f);
            c.box(p+Vec{radius*.20f,height+.09f,0},{radius*1.3f,.18f,radius*1.4f},palette.stone*1.13f);
            if(snow)c.box(p+Vec{radius*.20f,height+.21f,0},{radius*1.30f,.06f,radius*1.4f},{.86f,.89f,.87f});
        }else if(kind=="pillar"){
            c.cylinder(p,radius,height,palette.stone,10,radius*.87f);
            c.cylinder(p,radius*1.04f,.18f,palette.stone*.87f,10);
            c.box(p+Vec{0,height,0},{radius*2.05f,.20f,radius*2.05f},palette.stone*1.12f);
        }else{
            c.ellipsoid(p+Vec{0,height*.40f,0},{radius,height*.55f,radius},palette.stone*.76f,seed*.001f,3,7);
            if(snow)c.ellipsoid(p+Vec{0,height*.74f,0},{radius*.80f,height*.25f,radius*.80f},{.83f,.87f,.86f},0,2,7);
        }
    }
    // Small nearby ground cover gives scale while keeping opponents readable.
    for(int i=0;i<170;i++){
        float a=scenery_random(seed,i+1000)*2*PI,r=11+scenery_random(seed,i+1300)*25;Vec p{std::sin(a)*r,-.015f,std::cos(a)*r};
        if(dot(p-c.camera,p-c.camera)>24*24)continue;
        float h=.10f+scenery_random(seed,i+1600)*.14f,wind=std::sin(time*1.6f+i)*.045f;
        if(forest||autumn||marsh||coast){
            Colour grass=palette.foliage*(1.03f+scenery_random(seed,i+1800)*.25f);
            for(int j=0;j<3;j++){float spread=(j-1)*.09f;Vec root=p+Vec{spread,0,0};c.tri3(root-Vec{.022f,0,0},root+Vec{.022f,0,0},root+Vec{wind+spread*.3f,h*(j==1?1:.7f),.03f},grass);}
        }else if(i%3==0)c.box(p+Vec{0,.018f,0},{.12f,.035f,.09f},palette.stone*.80f,a);
        if(autumn&&i%2==0)c.tri3(p,p+Vec{.14f,.005f,.08f},p+Vec{.04f,.005f,.20f},{.72f,.39f,.15f});
    }
}
