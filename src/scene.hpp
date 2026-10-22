#pragma once
#include <cmath>
#include <array>
#include <map>
#include <algorithm>
#include <cctype>
#include "poses.hpp"
struct Colour{float r,g,b,a=1;Colour operator*(float f)const{return{r*f,g*f,b*f,a};}};
const Colour GOLD{.91f,.64f,.29f},INK{.045f,.065f,.068f},WHITE{.93f,.92f,.85f},MUTED{.55f,.62f,.60f};
struct Triangle{Vec a,b,c;Colour colour;float depth;size_t worldIndex=0;};

struct Canvas{
    std::vector<Vertex> mesh;std::vector<Triangle> triangles,worldTriangles;bool nativeDepth=false;size_t backgroundEnd=0;
    Vec camera{},forward{},right{},up{},focus{},sunDirection{-.5f,1,.3f};float aspect=1.6f,ambient=.47f,sunlight=.53f,fogStart=32,fogRange=150;Colour fogColour{.61f,.67f,.65f};bool following=false;
    void begin(int w,int h){mesh.clear();triangles.clear();worldTriangles.clear();backgroundEnd=0;aspect=static_cast<float>(w)/h;}
    void triangle(float x1,float y1,float x2,float y2,float x3,float y3,Colour c){
        mesh.push_back({x1/1280,y1/800,c.r,c.g,c.b,c.a});mesh.push_back({x2/1280,y2/800,c.r,c.g,c.b,c.a});mesh.push_back({x3/1280,y3/800,c.r,c.g,c.b,c.a});
    }
    void rect(float x,float y,float w,float h,Colour c){triangle(x,y,x+w,y,x+w,y+h,c);triangle(x,y,x+w,y+h,x,y+h,c);}
    void line(float x1,float y1,float x2,float y2,float width,Colour c){float dx=x2-x1,dy=y2-y1,d=std::max(.001f,std::hypot(dx,dy));float nx=-dy/d*width/2,ny=dx/d*width/2;triangle(x1+nx,y1+ny,x2+nx,y2+ny,x2-nx,y2-ny,c);triangle(x1+nx,y1+ny,x2-nx,y2-ny,x1-nx,y1-ny,c);}
    void circle(float x,float y,float radius,Colour c,int segments=32){for(int i=0;i<segments;i++){float a=i*2*PI/segments,b=(i+1)*2*PI/segments;triangle(x,y,x+std::cos(a)*radius,y+std::sin(a)*radius,x+std::cos(b)*radius,y+std::sin(b)*radius,c);}}
    void border(float x,float y,float w,float h,Colour c){rect(x,y,w,1,c);rect(x,y+h-1,w,1,c);rect(x,y,1,h,c);rect(x+w-1,y,1,h,c);}
    struct Glyph {int advance=0;struct Span{float x,y,w,alpha;};std::vector<Span> spans;};
    static const Glyph& glyph(int size,unsigned char ch,bool display){
        static std::map<int,Glyph> cache;int key=size*512+ch+(display?256:0);auto found=cache.find(key);if(found!=cache.end())return found->second;
        HDC dc=CreateCompatibleDC(nullptr);HFONT font=CreateFontA(-size,0,0,0,display?FW_NORMAL:FW_MEDIUM,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_TT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,display?"Georgia":"Segoe UI");auto old=SelectObject(dc,font);
        MAT2 matrix{{0,1},{0,0},{0,0},{0,1}};GLYPHMETRICS gm{};TEXTMETRICA metrics{};GetTextMetricsA(dc,&metrics);
        DWORD count=GetGlyphOutlineA(dc,ch,GGO_GRAY8_BITMAP,&gm,0,nullptr,&matrix);Glyph result;result.advance=gm.gmCellIncX;
        if(count!=GDI_ERROR&&count){std::vector<unsigned char> data(count);GetGlyphOutlineA(dc,ch,GGO_GRAY8_BITMAP,&gm,count,data.data(),&matrix);int stride=(gm.gmBlackBoxX+3)&~3;
            for(unsigned row=0;row<gm.gmBlackBoxY;row++)for(unsigned col=0;col<gm.gmBlackBoxX;){unsigned char alpha=data[row*stride+col];unsigned start=col;while(col<gm.gmBlackBoxX&&data[row*stride+col]==alpha)col++;if(alpha)result.spans.push_back({static_cast<float>(gm.gmptGlyphOrigin.x+start),static_cast<float>(metrics.tmAscent-gm.gmptGlyphOrigin.y+row),static_cast<float>(col-start),alpha/64.f});}
        }
        if(!result.advance)result.advance=size/3;SelectObject(dc,old);DeleteObject(font);DeleteDC(dc);return cache.emplace(key,std::move(result)).first->second;
    }
    static float text_width(const std::string& value,float scale){int size=static_cast<int>(std::round(scale*10));float total=0;for(unsigned char ch:value)total+=glyph(size,ch,scale>=5).advance;return total;}
    void text(float x,float y,std::string text,float scale=2,Colour colour=WHITE){
        int size=static_cast<int>(std::round(scale*10));float originX=x;
        for(unsigned char ch:text){if(ch=='\n'){y+=size*1.55f;x=originX;continue;}const auto& g=glyph(size,ch,scale>=5);for(auto span:g.spans){Colour tint=colour;tint.a*=span.alpha;rect(x+span.x,y+span.y,span.w,1,tint);}x+=g.advance;}
    }
    void set_camera(Vec eye,Vec target){camera=eye;focus=target;forward=norm(target-eye);right=norm(cross({0,1,0},forward));up=cross(forward,right);}
    bool project(Vec p,float& x,float& y,float& depth)const{Vec d=p-camera;depth=dot(d,forward);if(depth<.12f)return false;x=640+dot(d,right)/depth*700/aspect;y=400-dot(d,up)/depth*438;return true;}
    void tri3(Vec a,Vec b,Vec c,Colour colour,bool shade=true){
        float depth=dot((a+b+c)*(1.f/3)-camera,forward);if(std::max({dot(a-camera,forward),dot(b-camera,forward),dot(c-camera,forward)})<.12f)return;
        if(shade){Vec n=norm(cross(b-a,c-a));float light=ambient+sunlight*std::abs(dot(n,sunDirection));colour=colour*light;}
        float fog=std::clamp((depth-fogStart)/fogRange,0.f,.88f);colour.r=colour.r*(1-fog)+fogColour.r*fog;colour.g=colour.g*(1-fog)+fogColour.g*fog;colour.b=colour.b*(1-fog)+fogColour.b*fog;
        if(worldTriangles.empty())backgroundEnd=mesh.size();
        triangles.push_back({a,b,c,colour,depth,worldTriangles.size()});worldTriangles.push_back(triangles.back());
    }
    void quad(Vec a,Vec b,Vec c,Vec d,Colour col,bool shade=true){tri3(a,b,c,col,shade);tri3(a,c,d,col,shade);}
    void box(Vec p,Vec size,Colour col,float yaw=0){
        Vec v[8];for(int i=0;i<8;i++){float x=(i&1?1:-1)*size.x*.5f,z=(i&4?1:-1)*size.z*.5f;v[i]={p.x+x*std::cos(yaw)+z*std::sin(yaw),p.y+(i&2?1:-1)*size.y*.5f,p.z-x*std::sin(yaw)+z*std::cos(yaw)};}
        quad(v[0],v[1],v[3],v[2],col);quad(v[4],v[6],v[7],v[5],col);quad(v[0],v[4],v[5],v[1],col);quad(v[2],v[3],v[7],v[6],col);quad(v[0],v[2],v[6],v[4],col);quad(v[1],v[5],v[7],v[3],col);
    }
    void beam(Vec a,Vec b,float width,Colour col){Vec axis=norm(b-a),side=norm(cross(axis,std::abs(axis.y)<.9f?Vec{0,1,0}:Vec{1,0,0}))*width,other=norm(cross(axis,side))*width;Vec v[8]={a-side-other,a+side-other,a+side+other,a-side+other,b-side-other,b+side-other,b+side+other,b-side+other};quad(v[0],v[1],v[2],v[3],col);quad(v[4],v[7],v[6],v[5],col);for(int i=0;i<4;i++)quad(v[i],v[(i+1)%4],v[(i+1)%4+4],v[i+4],col);}
    void cylinder(Vec p,float radius,float height,Colour colour,int sides=12,float topRadius=-1){
        if(topRadius<0)topRadius=radius;
        for(int i=0;i<sides;i++){float a=i*2*PI/sides,b=(i+1)*2*PI/sides;Vec v1{p.x+std::sin(a)*radius,p.y,p.z+std::cos(a)*radius},v2{p.x+std::sin(b)*radius,p.y,p.z+std::cos(b)*radius},v3{p.x+std::sin(b)*topRadius,p.y+height,p.z+std::cos(b)*topRadius},v4{p.x+std::sin(a)*topRadius,p.y+height,p.z+std::cos(a)*topRadius};quad(v1,v2,v3,v4,colour);tri3({p.x,p.y+height,p.z},v4,v3,colour);}
    }
    void ellipsoid(Vec p,Vec radius,Colour colour,float yaw=0,int rings=6,int sides=10){
        auto point=[&](float a,float b){Vec v{std::cos(a)*std::sin(b)*radius.x,std::sin(a)*radius.y,std::cos(a)*std::cos(b)*radius.z};return p+Vec{v.x*std::cos(yaw)+v.z*std::sin(yaw),v.y,-v.x*std::sin(yaw)+v.z*std::cos(yaw)};};
        for(int j=0;j<rings;j++){float a=-PI/2+j*PI/rings,b=-PI/2+(j+1)*PI/rings;for(int i=0;i<sides;i++){float c=i*2*PI/sides,d=(i+1)*2*PI/sides;quad(point(a,c),point(a,d),point(b,d),point(b,c),colour);}}
    }
    void flush3(){
        if(nativeDepth)return;
        std::sort(triangles.begin(),triangles.end(),[](const Triangle& a,const Triangle& b){return a.depth>b.depth;});
        for(auto& t:triangles){
            float da=dot(t.a-camera,forward),db=dot(t.b-camera,forward),dc=dot(t.c-camera,forward);
            if(std::min({da,db,dc})>=.13f){float x[3],y[3],d;if(project(t.a,x[0],y[0],d)&&project(t.b,x[1],y[1],d)&&project(t.c,x[2],y[2],d))triangle(x[0],y[0],x[1],y[1],x[2],y[2],t.colour);continue;}
            // One clipping plane produces at most four vertices; avoid heap work per triangle.
            Vec poly[4],v[]={t.a,t.b,t.c};int count=0;
            for(int i=0;i<3;i++){Vec a=v[i],b=v[(i+1)%3];float da=dot(a-camera,forward),db=dot(b-camera,forward);if(da>=.13f)poly[count++]=a;if((da>=.13f)!=(db>=.13f))poly[count++]=a+(b-a)*((.13f-da)/(db-da));}
            for(int i=1;i+1<count;i++){float x[3],y[3],d;bool valid=project(poly[0],x[0],y[0],d)&&project(poly[i],x[1],y[1],d)&&project(poly[i+1],x[2],y[2],d);if(valid)triangle(x[0],y[0],x[1],y[1],x[2],y[2],t.colour);}
        }
    }
    void flush_layer(){flush3();triangles.clear();}
};

#include "environment.hpp"

inline std::string weapon_family(const std::string& id){
    if(id=="fists")return "unarmed";if(id=="bow"||id=="longbow"||id=="moonbow")return "bow";
    if(id=="crossbow"||id=="slingshot")return id;if(id=="emberstaff")return "staff";
    if(id=="axe"||id=="halberd"||id=="pickaxe")return "axe";if(id=="warhammer")return "mace";if(id=="grappling_rope"||id=="lasso")return "rope";if(id=="mace"||id=="spear")return id;return "blade";
}
inline float weapon_length(const std::string& id){return id=="knife"||id=="dagger"?.55f:id=="greatsword"?1.85f:id=="spear"||id=="halberd"?2.3f:id=="longsword"?1.5f:id=="estoc"?1.35f:1.15f;}
inline void held_equipment(Canvas& c,const std::string& id,Vec hand,Vec tip,Vec side,Vec front){
    std::string family=weapon_family(id);if(family=="unarmed")return;Colour metal{.56f,.59f,.57f},wood{.34f,.23f,.12f};
    bool magic=id=="stormblade"||id=="frostsabre"||id=="sunblade"||id=="moonbow"||id=="emberstaff";
    if(magic)metal=id=="sunblade"?Colour{.98f,.66f,.26f}:Colour{.39f,.75f,.95f};
    Vec direction=norm(tip-hand),up{0,1,0};
    if(family=="rope"){
        for(int i=0;i<20;i++){float a=i*2*PI/20,b=(i+1)*2*PI/20;c.beam(hand+side*(std::cos(a)*.17f)+up*(std::sin(a)*.17f),hand+side*(std::cos(b)*.17f)+up*(std::sin(b)*.17f),.018f,wood);}c.beam(hand,hand+front*.22f,.015f,wood);
    }else if(family=="bow"){
        for(int i=0;i<12;i++){float a=-PI/2+i*PI/12,b=-PI/2+(i+1)*PI/12;Vec p=hand+up*(std::sin(a)*.65f)+front*(std::cos(a)*.28f),q=hand+up*(std::sin(b)*.65f)+front*(std::cos(b)*.28f);c.beam(p,q,.027f,magic?metal:wood);}
        c.beam(hand-up*.65f,hand+up*.65f,.007f,{.81f,.80f,.67f});c.beam(hand-front*.28f,hand+front*.74f,.009f,metal);
    }else if(family=="crossbow"){
        c.beam(hand-front*.35f,hand+front*.6f,.07f,wood);c.beam(hand+front*.28f-side*.4f,hand+front*.28f+side*.4f,.032f,metal);c.beam(hand+front*.28f-side*.4f,hand-front*.02f,.008f,WHITE);c.beam(hand+front*.28f+side*.4f,hand-front*.02f,.008f,WHITE);c.beam(hand-front*.1f,hand+front*.8f,.009f,metal);
    }else if(family=="slingshot"){
        c.beam(hand-up*.16f,hand+up*.15f,.035f,wood);c.beam(hand+up*.15f,hand+up*.38f-side*.15f,.035f,wood);c.beam(hand+up*.15f,hand+up*.38f+side*.15f,.035f,wood);c.beam(hand+up*.38f-side*.15f,hand+up*.24f-front*.15f,.01f,WHITE);c.beam(hand+up*.38f+side*.15f,hand+up*.24f-front*.15f,.01f,WHITE);
    }else if(family=="staff"){
        c.beam(hand-up*.75f,hand+up*1.0f,.055f,wood);c.ellipsoid(hand+up*1.0f,{.16f,.20f,.16f},{.97f,.44f,.11f},0,6,8);
    }else if(family=="spear"){
        c.beam(hand-direction*.65f,tip,.032f,wood);c.beam(tip-direction*.35f,tip,.06f,metal);
    }else if(family=="axe"){
        c.beam(hand-direction*.22f,tip,.045f,wood);c.box(tip-direction*.2f,{.5f,.25f,.1f},metal);
    }else if(family=="mace"){
        c.beam(hand-direction*.15f,tip,.045f,wood);c.ellipsoid(tip,{.14f,.17f,.14f},metal,0,5,8);
    }else{
        float rear=id=="knife"||id=="dagger"?.09f:id=="greatsword"?.20f:.16f;Vec across=blade_cross_axis(direction,side);
        c.beam(hand-direction*rear,hand+direction*.22f,.05f,wood);c.beam(hand-direction*(rear+.035f),hand-direction*rear,.061f,metal);
        c.beam(hand+direction*.23f-across*.18f,hand+direction*.23f+across*.18f,.035f,GOLD);
        c.beam(hand+direction*.24f,tip,.035f,metal);c.beam(hand+direction*.26f+across*.027f,tip,.009f,{.88f,.89f,.84f});
    }
}
inline void debug_hitboxes(Canvas& c,const json& world,const std::string& hiddenId={}){
    auto vec=[](const json& v){return Vec{v[0],v[1],v[2]};};
    if(!world.contains("hitboxes"))return;
    for(const auto& actor:world["hitboxes"]){
        if(actor.value("id",std::string{})==hiddenId)continue;
        for(const auto& s:actor["shapes"]){std::string zone=s[0],kind=s[1];Colour colour=zone=="head"?Colour{1,.46f,.24f}:zone=="body"?Colour{.98f,.82f,.3f}:zone=="arms"?Colour{.35f,.77f,1}:Colour{.55f,.95f,.5f};
            if(kind=="box"){
                Vec centre=vec(s[2]),axes[3]={vec(s[3][0]),vec(s[3][1]),vec(s[3][2])},half=vec(s[4]);Vec corners[8];
                for(int i=0;i<8;i++)corners[i]=centre+axes[0]*((i&1)?half.x:-half.x)+axes[1]*((i&2)?half.y:-half.y)+axes[2]*((i&4)?half.z:-half.z);
                for(int i=0;i<8;i++)for(int bit:{1,2,4})if(!(i&bit))c.beam(corners[i],corners[i|bit],.008f,colour);
            }else{
                Vec a=vec(s[2]),b=vec(s[3]),direction=norm(b-a),side=norm(cross(direction,std::abs(direction.y)<.9f?Vec{0,1,0}:Vec{1,0,0})),up=cross(direction,side);float radius=s[4];
                for(int i=0;i<8;i++){float x=i*PI/4,y=(i+1)*PI/4;Vec offset=(side*std::cos(x)+up*std::sin(x))*radius,next=(side*std::cos(y)+up*std::sin(y))*radius;c.beam(a+offset,b+offset,.006f,colour);c.beam(a+offset,a+next,.006f,colour);c.beam(b+offset,b+next,.006f,colour);}
                for(Vec radial:{side,up})for(int sign:{-1,1})for(int i=0;i<4;i++){float x=i*PI/4,y=(i+1)*PI/4;Vec centre=sign<0?a:b;c.beam(centre+(radial*std::cos(x)+direction*(sign*std::sin(x)))*radius,centre+(radial*std::cos(y)+direction*(sign*std::sin(y)))*radius,.006f,colour);}
            }
        }
        c.beam(vec(actor["blade"][0]),vec(actor["blade"][1]),.025f,actor.value("blocking",false)?Colour{.2f,1,1}:Colour{1,.3f,.8f});
    }
}
inline void battlefield_objects(Canvas& c,const json& world,float){
    if(world.contains("events"))for(const auto& e:world["events"]){float age=world.value("time",0.f)-e.value("time",0.f);std::string kind=e.value("kind",std::string{});if((kind=="parry"||kind=="block")&&age>=0&&age<.22f&&e.contains("point")&&!e["point"].is_null()){Vec p{e["point"][0],e["point"][1],e["point"][2]};for(int i=0;i<6;i++){float a=i*PI/3;c.beam(p,p+Vec{std::cos(a),std::sin(a),.25f}*(.08f+age*.8f),.008f,{1,.78f,.35f});}}}
    if(world.contains("drops"))for(const auto& d:world["drops"]){float y=d.value("y",.06f),a=d.value("age",0.f)*2;auto hint=world.value("pickup",json::object());if(y<=.22f||(d.value("vy",0.f)==0&&d.value("age",0.f)>.5f))a=1.85f;Vec p{d.value("x",0.f),y,d.value("z",0.f)},front{std::sin(a),0,std::cos(a)},side{std::cos(a),0,-std::sin(a)};held_equipment(c,d.value("weapon",std::string("knife")),p,p+front*1.1f,side,front);if(!hint.empty()&&hint.value("id",std::string{})==d.value("id",std::string{})){Colour glow{.95f,.69f,.32f,.75f};for(int i=0;i<16;i++){float t=i*PI/8;Vec marker=p+Vec{std::sin(t)*.42f,.015f,std::cos(t)*.42f};c.box(marker,{.045f,.012f,.045f},glow);}}}
    if(world.contains("projectiles"))for(const auto& p:world["projectiles"]){Vec v{p.value("x",0.f),p.value("y",1.f),p.value("z",0.f)},direction=norm({p.value("vx",0.f),p.value("vy",0.f),p.value("vz",1.f)});std::string kind=p.value("kind",std::string{});
        if(kind=="slingshot")c.ellipsoid(v,{.055f,.055f,.055f},{.53f,.55f,.51f},0,4,6);
        else if(kind=="firebolt"||kind=="frostbolt"||kind=="staff"){Colour col=kind=="frostbolt"?Colour{.35f,.77f,.95f}:Colour{1,.51f,.18f};c.ellipsoid(v,{.12f,.12f,.12f},col,0,4,8);c.beam(v-direction*.65f,v,.027f,col);}
        else{Vec side=norm(cross(direction,{0,1,0})),up=norm(cross(side,direction));c.beam(v-direction*.92f,v,.02f,{.41f,.27f,.14f});c.beam(v-direction*.14f,v,.052f,{.78f,.80f,.73f});c.quad(v-direction*.76f-side*.075f,v-direction*.96f-side*.075f,v-direction*.96f+side*.075f,v-direction*.76f+side*.075f,{.87f,.82f,.70f});c.quad(v-direction*.76f-up*.075f,v-direction*.96f-up*.075f,v-direction*.96f+up*.075f,v-direction*.76f+up*.075f,{.87f,.82f,.70f});}
    }
    if(world.contains("ropes")&&world.contains("fighters"))for(const auto& rope:world["ropes"]){json owner;for(const auto& f:world["fighters"])if(f["id"]==rope["owner"]){owner=f;break;}if(owner.is_null())continue;Vec start{owner.value("x",0.f),1.2f,owner.value("z",0.f)},end{rope.value("x",0.f),rope.value("y",1.1f),rope.value("z",0.f)};float grow=std::clamp((world.value("time",0.f)-rope.value("created",0.f))/.25f,0.f,1.f);end=start+(end-start)*grow;for(int i=0;i<12;i++){float a=i/12.f,b=(i+1)/12.f;Vec p=start+(end-start)*a+Vec{0,-std::sin(a*PI)*.3f,0},q=start+(end-start)*b+Vec{0,-std::sin(b*PI)*.3f,0};c.beam(p,q,.018f,{.64f,.50f,.28f});}}
}
inline PoseInput pose_input(const json& f,float time,bool firstPerson=false){
    PoseInput input{f.value("attack",std::string{}),f.value("guard_dir",std::string("centre")),f.value("block",false),time-f.value("attack_started",time),f.value("attack_windup",.18f),f.value("attack_duration",.46f),f.value("aim_zone",std::string("body"))};
    float yaw=firstPerson||input.block||!input.attack.empty()?f.value("yaw",0.f):f.value("body_yaw",f.value("yaw",0.f));
    float x=f.value("move_x",0.f),z=f.value("move_z",0.f);
    input.moveSide=(x*std::cos(yaw)-z*std::sin(yaw))/4.4f;input.moveForward=(x*std::sin(yaw)+z*std::cos(yaw))/4.4f;input.gait=f.value("gait",0.f);
    if(input.block&&f.contains("guard_from")&&!f["guard_from"].empty()){
        const auto& p=f["guard_from"];input.guardAge=time-f.value("guard_changed",time);
        input.guardFrom={{p[0],p[1],p[2]},{p[3],p[4],p[5]},p[6],p[7],p[8]};
    }
    if(f.value("build_mode",false)&&f.value("mine_progress",0.f)>0){input.attack="overhead";input.age=std::fmod(std::max(0.f,time-f.value("mining_started",time)),.85f);input.windup=.34f*.85f/.76f;input.duration=.85f;input.aim="legs";}
    return input;
}
inline CombatPose pose_for(const json& f,float time){return combat_pose(pose_input(f,time));}
inline bool two_handed(const json& f){auto weapon=f.value("weapon",std::string{});return f.value("shield",std::string{}).empty()&&(weapon=="longsword"||weapon=="greatsword"||weapon=="katana"||weapon=="spear"||weapon=="halberd");}
inline void blade_pose(const json& f,float time,Vec p,Vec front,Vec side,float length,Vec& hand,Vec& tip,const CombatPose* visual=nullptr,const Vec* rightRoot=nullptr,const Vec* leftRoot=nullptr){
    CombatPose pose=visual?*visual:pose_for(f,time);Vec shoulder=rightRoot?*rightRoot:p+side*.34f+Vec{0,1.43f,0},other=leftRoot?*leftRoot:p-side*.34f+Vec{0,1.43f,0};
    Vec desired=p+side*pose.hand.x+Vec{0,pose.hand.y,0}+front*pose.hand.z,direction=norm(side*pose.direction.x+Vec{0,pose.direction.y,0}+front*pose.direction.z);
    auto grip=weapon_grip(desired,direction,shoulder,other,length,two_handed(f));hand=grip.hand;tip=grip.tip;
}
inline void first_person_arms(Canvas& c,const json& f,float yaw,float pitch,float time,const CombatPose* visual=nullptr){
    if(f.value("dead",0.f)>0||f.value("fall",0.f)>0)return;
    Vec front{std::sin(yaw)*std::cos(pitch),-std::sin(pitch),std::cos(yaw)*std::cos(pitch)},side{std::cos(yaw),0,-std::sin(yaw)};
    Vec base=c.camera-Vec{0,1.6f,0}+front*.58f,hand,tip;blade_pose(f,time,base,front,side,weapon_length(f.value("weapon",std::string("knife"))),hand,tip,visual);
    Vec shoulder=base+side*.34f+Vec{0,1.43f,0},elbow=solve_joint(shoulder,hand,side-Vec{0,.6f,0},.36f);c.beam(shoulder,elbow,.075f,{.28f,.34f,.31f});c.beam(elbow,hand,.066f,{.28f,.34f,.31f});c.ellipsoid(hand,{.075f,.075f,.075f},{.68f,.47f,.34f},yaw,4,6);
    held_equipment(c,f.value("weapon",std::string("knife")),hand,tip,side,front);
    if(two_handed(f)){Vec leftRoot=base-side*.34f+Vec{0,1.43f,0},left=hand-norm(tip-hand)*.11f,joint=solve_joint(leftRoot,left,-side-Vec{0,.6f,0},.36f);c.beam(leftRoot,joint,.075f,{.28f,.34f,.31f});c.beam(joint,left,.066f,{.28f,.34f,.31f});c.ellipsoid(left,{.075f,.075f,.075f},{.68f,.47f,.34f},yaw,4,6);}
}
inline void fighter(Canvas& c,const json& f,float time,bool self=false,const CombatPose* visual=nullptr){
    if(f.value("dead",0.f)>0)return;
    CombatPose pose=visual?*visual:pose_for(f,time);float x=f.value("x",0.f),z=f.value("z",0.f),bodyYaw=f.value("body_yaw",f.value("yaw",0.f)),yaw=bodyYaw+pose.spin+pose.twist;
    float jump=f.value("jump",0.f);float lift=jump>0?std::sin((.55f-jump)/.55f*PI)*.65f:0;
    Vec p{x,lift+f.value("y",0.f),z};Vec front{std::sin(yaw),0,std::cos(yaw)},side{std::cos(yaw),0,-std::sin(yaw)};
    float hipYaw=bodyYaw+pose.spin+pose.twist*.25f,bladeYaw=(f.value("block",false)||!f.value("attack",std::string{}).empty()?f.value("yaw",bodyYaw):bodyYaw)+pose.spin;
    Vec hipFront{std::sin(hipYaw),0,std::cos(hipYaw)},hipSide{std::cos(hipYaw),0,-std::sin(hipYaw)},bladeFront{std::sin(bladeYaw),0,std::cos(bladeYaw)},bladeSide{std::cos(bladeYaw),0,-std::sin(bladeYaw)};
    std::string id=f.value("id",std::string{});unsigned hash=0;for(unsigned char a:id)hash=hash*31+a;
    Colour cloth=self?Colour{.21f,.34f,.32f}:Colour{.28f+float(hash%4)*.07f,.18f+float(hash%3)*.05f,.13f+float(hash%5)*.04f};
    Colour skin{.69f,.49f,.34f},metal{.56f,.59f,.57f},dark{.18f,.18f,.16f};
    auto mob=f.value("mob_kind",std::string{});if(mob=="golem"){skin={.48f,.49f,.44f};cloth={.34f,.36f,.32f};dark={.25f,.27f,.24f};}else if(mob=="revenant"){skin={.54f,.62f,.53f};cloth={.16f,.22f,.20f};}
    Vec relative=p+Vec{0,1,0}-c.camera;float depth=dot(relative,c.forward);
    if(!self&&(depth<-3.5f||std::abs(dot(relative,c.right))>std::max(0.f,depth)*.915f*c.aspect+3.5f||std::abs(dot(relative,c.up))>std::max(0.f,depth)*.915f+3.5f))return;
    if(!self&&dot(p-c.camera,p-c.camera)>14*14&&f.value("downed",0.f)<=0){
        c.ellipsoid(p+Vec{0,1.2f,0},{.33f,.4f,.22f},cloth,yaw,3,6);c.ellipsoid(p+Vec{0,1.87f,0},{.18f,.23f,.18f},skin,yaw,3,6);
        float speed=std::min(1.f,std::hypot(f.value("move_x",0.f),f.value("move_z",0.f))/4.4f);Vec travel=norm({f.value("move_x",0.f),0,f.value("move_z",0.f)});
        for(int leg:{-1,1}){auto step=foot_step(f.value("gait",0.f),speed,leg);Vec hip=p+hipSide*(leg*.16f)+Vec{0,.86f,0},foot=p+hipSide*(leg*.19f)+travel*step.travel+hipFront*(pose.lunge*(leg==1?1:-.4f))+Vec{0,.12f+step.lift,0};Vec knee=solve_joint(hip,foot,hipFront,.44f);c.beam(hip,knee,.095f,dark);c.beam(knee,foot,.085f,dark);}
        Vec hand,tip;blade_pose(f,time,p,bladeFront,bladeSide,weapon_length(f.value("weapon",std::string("knife"))),hand,tip,&pose);c.beam(p+bladeSide*.30f+Vec{0,1.43f,0},hand,.07f,cloth);if(two_handed(f))c.beam(p-bladeSide*.30f+Vec{0,1.43f,0},hand-norm(tip-hand)*.11f,.07f,cloth);held_equipment(c,f.value("weapon",std::string("knife")),hand,tip,bladeSide,bladeFront);return;
    }
    // Flattened ground shadow.
    for(int i=0;i<16;i++){float a=i*2*PI/16,b=(i+1)*2*PI/16;c.tri3({x,p.y+.02f,z},{x+std::sin(a)*.7f,p.y+.02f,z+std::cos(a)*.45f},{x+std::sin(b)*.7f,p.y+.02f,z+std::cos(b)*.45f},{.21f,.20f,.16f,.45f},false);}
    size_t bodyBegin=c.triangles.size();float moving=std::min(1.f,std::hypot(f.value("move_x",0.f),f.value("move_z",0.f))/4.4f);Vec travel=norm({f.value("move_x",0.f),0,f.value("move_z",0.f)});
    for(int leg:{-1,1}){auto step=foot_step(f.value("gait",0.f),moving,leg);Vec hip=p+hipSide*(leg*.16f)+Vec{0,.86f,0},ankle=p+hipSide*(leg*.19f)+travel*step.travel+hipFront*(pose.lunge*(leg==1?1:-.4f))+Vec{0,.12f+step.lift,0};Vec knee=solve_joint(hip,ankle,hipFront,.44f);c.beam(hip,knee,.105f,dark);c.ellipsoid(knee,{.105f,.105f,.105f},dark,hipYaw,4,6);c.beam(knee,ankle,.087f,dark);c.box(ankle+hipFront*.055f-Vec{0,.025f,0},{.23f,.19f,.37f},dark,hipYaw);}
    std::string armourId=f.value("armour",std::string{});Colour torso=armourId.empty()?cloth:armourId=="leather"?Colour{.34f,.25f,.17f}:armourId=="brigandine"?Colour{.29f,.23f,.20f}:armourId=="mail"?Colour{.43f,.46f,.45f}:metal;
    c.ellipsoid(p+Vec{0,1.19f,0},{.35f,.43f,.23f},torso,yaw,8,12);
    c.ellipsoid(p+side*.34f+Vec{0,1.44f,0},{.15f,.13f,.17f},torso,yaw);
    c.ellipsoid(p-side*.34f+Vec{0,1.44f,0},{.15f,.13f,.17f},torso,yaw);
    c.box(p+Vec{0,.87f,0},{.69f,.12f,.40f},{.22f,.17f,.11f},yaw);c.box(p+front*.225f+Vec{0,.87f,0},{.13f,.13f,.05f},GOLD,yaw);
    c.cylinder(p+Vec{0,1.56f,0},.11f,.14f,skin,8);c.ellipsoid(p+Vec{0,1.87f,0},{.18f,.23f,.18f},skin,yaw,8,12);
    c.ellipsoid(p+Vec{0,2.04f,0},{.195f,.12f,.195f},!f.value("helmet",std::string{}).empty()?metal:Colour{.19f,.15f,.11f},yaw,6,12);
    c.ellipsoid(p+front*.178f+Vec{0,1.86f,0},{.04f,.075f,.06f},skin,yaw,4,6);
    c.box(p+front*.18f+side*.075f+Vec{0,1.92f,0},{.055f,.03f,.03f},dark,yaw);c.box(p+front*.18f-side*.075f+Vec{0,1.92f,0},{.055f,.03f,.03f},dark,yaw);
    bool block=f.value("block",false);std::string attack=f.value("attack",std::string{});
    Vec shoulder=p+side*.34f+Vec{0,1.43f,0},hand=p+side*.32f+front*.3f+Vec{0,1.18f,0};
    Vec tip=hand+front*.75f+Vec{0,.9f,0};
    std::string weapon=f.value("weapon",std::string("knife"));float length=weapon_length(weapon);
    Vec leftShoulder=p-side*.34f+Vec{0,1.43f,0};blade_pose(f,time,p,bladeFront,bladeSide,length,hand,tip,&pose,&shoulder,&leftShoulder);
    Vec elbow=solve_joint(shoulder,hand,side-Vec{0,.6f,0},.36f);c.beam(shoulder,elbow,.082f,cloth);c.ellipsoid(elbow,{.083f,.083f,.083f},cloth,yaw,4,6);c.beam(elbow,hand,.068f,cloth);c.box(hand,{.14f,.14f,.14f},skin,yaw);
    held_equipment(c,weapon,hand,tip,bladeSide,bladeFront);
    Vec free=free_hand_offset(block,!f.value("shield",std::string{}).empty(),f.value("gait",0.f),moving);Vec left=p+side*free.x+front*free.z+Vec{0,free.y,0};if(two_handed(f))left=hand-norm(tip-hand)*.11f;else left=limit_reach(leftShoulder,left,.70f);Vec leftElbow=solve_joint(leftShoulder,left,-side-Vec{0,.6f,0},.36f);c.beam(leftShoulder,leftElbow,.08f,cloth);c.beam(leftElbow,left,.067f,cloth);c.box(left,{.14f,.14f,.14f},skin,yaw);
    if(!f.value("shield",std::string{}).empty()){c.box(left+front*.1f,{.55f,.75f,.13f},dark,yaw);c.box(left+front*.18f,{.48f,.66f,.05f},metal,yaw);c.box(left+front*.22f,{.12f,.14f,.07f},GOLD,yaw);}
    float fall=f.value("fall",0.f);if(fall>0){float duration=f.value("fall_duration",1.25f),pose=std::min(1.f,(duration-fall)*7)*std::min(1.f,fall*4),a=pose*PI*.48f;auto rotate=[&](Vec v){Vec d=v-p;float localY=d.y,localZ=dot(d,front);return p+side*dot(d,side)+Vec{0,localY*std::cos(a)-localZ*std::sin(a)+.08f,0}+front*(localY*std::sin(a)+localZ*std::cos(a));};for(size_t i=bodyBegin;i<c.triangles.size();i++){auto& t=c.triangles[i];t.a=rotate(t.a);t.b=rotate(t.b);t.c=rotate(t.c);t.depth=dot((t.a+t.b+t.c)*(1.f/3)-c.camera,c.forward);c.worldTriangles[t.worldIndex]=t;}}
}
