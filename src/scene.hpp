#pragma once
#include <cmath>
#include <array>
#include <map>
#include <algorithm>
#include <cctype>

constexpr float PI=3.14159265f;
struct Vec {float x,y,z;Vec operator+(Vec v)const{return{x+v.x,y+v.y,z+v.z};}Vec operator-(Vec v)const{return{x-v.x,y-v.y,z-v.z};}Vec operator*(float f)const{return{x*f,y*f,z*f};}};
inline float dot(Vec a,Vec b){return a.x*b.x+a.y*b.y+a.z*b.z;}
inline Vec cross(Vec a,Vec b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
inline Vec norm(Vec a){float d=std::sqrt(dot(a,a));return a*(1/std::max(.0001f,d));}
struct Colour{float r,g,b,a=1;Colour operator*(float f)const{return{r*f,g*f,b*f,a};}};
const Colour GOLD{.91f,.64f,.29f},INK{.045f,.065f,.068f},WHITE{.93f,.92f,.85f},MUTED{.55f,.62f,.60f};
struct Triangle{Vec a,b,c;Colour colour;float depth;};

struct Canvas{
    std::vector<Vertex> mesh;std::vector<Triangle> triangles;
    Vec camera{},forward{},right{},up{};float aspect=1.6f;
    void begin(int w,int h){mesh.clear();triangles.clear();aspect=static_cast<float>(w)/h;}
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
    void set_camera(Vec eye,Vec target){camera=eye;forward=norm(target-eye);right=norm(cross({0,1,0},forward));up=cross(forward,right);}
    bool project(Vec p,float& x,float& y,float& depth)const{Vec d=p-camera;depth=dot(d,forward);if(depth<.12f)return false;x=640+dot(d,right)/depth*700/aspect;y=400-dot(d,up)/depth*438;return true;}
    void tri3(Vec a,Vec b,Vec c,Colour colour,bool shade=true){
        float depth=dot((a+b+c)*(1.f/3)-camera,forward);if(std::max({dot(a-camera,forward),dot(b-camera,forward),dot(c-camera,forward)})<.12f)return;
        if(shade){Vec n=norm(cross(b-a,c-a));float light=.47f+.53f*std::abs(dot(n,norm({-.5f,1,.3f})));colour=colour*light;}
        float fog=std::clamp((depth-32)/150,0.f,.65f);colour.r=colour.r*(1-fog)+.61f*fog;colour.g=colour.g*(1-fog)+.67f*fog;colour.b=colour.b*(1-fog)+.65f*fog;
        triangles.push_back({a,b,c,colour,depth});
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
        std::sort(triangles.begin(),triangles.end(),[](const Triangle& a,const Triangle& b){return a.depth>b.depth;});
        for(auto& t:triangles){
            std::vector<Vec> poly;Vec v[]={t.a,t.b,t.c};
            for(int i=0;i<3;i++){Vec a=v[i],b=v[(i+1)%3];float da=dot(a-camera,forward),db=dot(b-camera,forward);if(da>=.13f)poly.push_back(a);if((da>=.13f)!=(db>=.13f))poly.push_back(a+(b-a)*((.13f-da)/(db-da)));}
            for(size_t i=1;i+1<poly.size();i++){float x[3],y[3],d;bool valid=project(poly[0],x[0],y[0],d)&&project(poly[i],x[1],y[1],d)&&project(poly[i+1],x[2],y[2],d);if(valid)triangle(x[0],y[0],x[1],y[1],x[2],y[2],t.colour);}
        }
    }
};

inline void environment(Canvas& c,float time){
    // Every visible object is generated locally; both APIs draw the same geometry.
    c.rect(0,0,1280,800,{.58f,.68f,.72f});
    for(int i=0;i<20;i++)c.rect(0,i*25.f,1280,25,{.35f+i*.012f,.51f+i*.007f,.60f+i*.005f});
    c.circle(1030,126,57,{1,.89f,.62f,.13f});c.circle(1030,126,35,{1,.91f,.69f});
    for(int i=0;i<24;i++){float a=i*2*PI/24,r=85+(i%4)*9;c.cylinder({std::sin(a)*r,-3,std::cos(a)*r},14+(i%3)*4,13+(i%5)*4,{.31f,.40f,.37f},7,0);}
    // Sand tiles ensure the ground remains projected near the moving camera.
    for(int x=-45;x<45;x+=5)for(int z=-45;z<45;z+=5){float colour=((x*13+z*7)%9)*.003f;c.quad({float(x),-.05f,float(z)},{float(x+5),-.05f,float(z)},{float(x+5),-.05f,float(z+5)},{float(x),-.05f,float(z+5)},{.61f+colour,.52f+colour,.37f+colour});}
    for(int i=0;i<64;i++){
        float a=i*2*PI/64,r=40;Vec p{std::sin(a)*r,1.25f,std::cos(a)*r};
        c.box(p,{3.9f,2.5f,1.6f},{.54f,.49f,.39f},a);c.box(p+Vec{0,1.35f,0},{3.9f,.2f,1.85f},{.67f,.60f,.47f},a);
        if(i%4==0){c.cylinder({p.x,0,p.z},1.1f,5.2f,{.51f,.48f,.40f},8);c.cylinder({p.x,5.2f,p.z},1.4f,.35f,{.66f,.59f,.46f},8);}
        if(i%8==0){Vec flag{p.x,4.4f,p.z};c.beam(flag+Vec{0,-.4f,0},flag+Vec{0,3.2f,0},.055f,{.25f,.24f,.20f});float wind=std::sin(time*2+i)*.3f;c.quad(flag+Vec{0,3,0},flag+Vec{1.7f,2.7f,wind},flag+Vec{1.7f,1.1f,wind},flag+Vec{0,1.4f,0},{.37f,.12f,.10f});}
    }
    for(int i=0;i<24;i++){float a=i*2*PI/24+.1f,r=49+(i%3)*3;Vec p{std::sin(a)*r,0,std::cos(a)*r};c.cylinder(p,.28f,3.5f,{.26f,.22f,.15f},7);c.cylinder(p+Vec{0,2.5f,0},2.7f,5,{.20f,.31f,.24f},8,0);}
    for(int i=0;i<12;i++){float a=i*2*PI/12;Vec p{std::sin(a)*35,0,std::cos(a)*35};c.box(p+Vec{0,.45f,0},{1.5f,.9f,1.2f},{.37f,.28f,.17f},a);c.box(p+Vec{0,.95f,0},{1.6f,.1f,1.3f},{.49f,.37f,.21f},a);}
    // Decorative inset central circle and radial scoring lines.
    for(int i=0;i<72;i++){float a=i*2*PI/72,b=(i+1)*2*PI/72;c.quad({std::sin(a)*10,.005f,std::cos(a)*10},{std::sin(b)*10,.005f,std::cos(b)*10},{std::sin(b)*10.18f,.005f,std::cos(b)*10.18f},{std::sin(a)*10.18f,.005f,std::cos(a)*10.18f},{.78f,.67f,.46f},false);}
}

inline std::string weapon_family(const std::string& id){
    if(id=="fists")return "unarmed";if(id=="bow"||id=="longbow"||id=="moonbow")return "bow";
    if(id=="crossbow"||id=="slingshot")return id;if(id=="emberstaff")return "staff";
    if(id=="axe"||id=="halberd")return "axe";if(id=="mace"||id=="spear")return id;return "blade";
}
inline void held_equipment(Canvas& c,const std::string& id,Vec hand,Vec tip,Vec side,Vec front){
    std::string family=weapon_family(id);if(family=="unarmed")return;Colour metal{.56f,.59f,.57f},wood{.34f,.23f,.12f};
    bool magic=id=="stormblade"||id=="frostsabre"||id=="sunblade"||id=="moonbow"||id=="emberstaff";
    if(magic)metal=id=="sunblade"?Colour{.98f,.66f,.26f}:Colour{.39f,.75f,.95f};
    Vec direction=norm(tip-hand),up{0,1,0};
    if(family=="bow"){
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
        c.beam(hand,hand+direction*.22f,.06f,wood);c.beam(hand+direction*.23f-side*.18f,hand+direction*.23f+side*.18f,.035f,GOLD);
        c.beam(hand+direction*.24f,tip,.035f,metal);c.beam(hand+direction*.26f+side*.035f,tip,.009f,{.88f,.89f,.84f});
    }
}
inline void battlefield_objects(Canvas& c,const json& world,float){
    if(world.contains("drops"))for(const auto& d:world["drops"]){float y=d.value("y",.06f),a=d.value("age",0.f)*2;Vec p{d.value("x",0.f),y,d.value("z",0.f)},front{std::sin(a),0,std::cos(a)},side{std::cos(a),0,-std::sin(a)};held_equipment(c,d.value("weapon",std::string("knife")),p,p+front*1.1f,side,front);}
    if(world.contains("projectiles"))for(const auto& p:world["projectiles"]){Vec v{p.value("x",0.f),p.value("y",1.f),p.value("z",0.f)},direction=norm({p.value("vx",0.f),p.value("vy",0.f),p.value("vz",1.f)});std::string kind=p.value("kind",std::string{});
        if(kind=="slingshot")c.ellipsoid(v,{.055f,.055f,.055f},{.53f,.55f,.51f},0,4,6);
        else if(kind=="firebolt"||kind=="frostbolt"||kind=="staff"){Colour col=kind=="frostbolt"?Colour{.35f,.77f,.95f}:Colour{1,.51f,.18f};c.ellipsoid(v,{.12f,.12f,.12f},col,0,4,8);c.beam(v-direction*.65f,v,.027f,col);}
        else{c.beam(v-direction*.68f,v,.012f,{.41f,.27f,.14f});c.beam(v-direction*.08f,v,.04f,{.78f,.80f,.73f});c.beam(v-direction*.58f,v-direction*.69f,.042f,{.83f,.78f,.63f});}
    }
}
inline void fighter(Canvas& c,const json& f,float time,bool self=false){
    if(f.value("dead",0.f)>0)return;
    float x=f.value("x",0.f),z=f.value("z",0.f),yaw=f.value("yaw",0.f);
    float jump=f.value("jump",0.f);float lift=jump>0?std::sin((.55f-jump)/.55f*PI)*.65f:0;
    Vec p{x,lift,z};Vec front{std::sin(yaw),0,std::cos(yaw)},side{std::cos(yaw),0,-std::sin(yaw)};
    std::string id=f.value("id",std::string{});unsigned hash=0;for(unsigned char a:id)hash=hash*31+a;
    Colour cloth=self?Colour{.21f,.34f,.32f}:Colour{.28f+float(hash%4)*.07f,.18f+float(hash%3)*.05f,.13f+float(hash%5)*.04f};
    Colour skin{.69f,.49f,.34f},metal{.56f,.59f,.57f},dark{.18f,.18f,.16f};
    // Flattened ground shadow.
    for(int i=0;i<16;i++){float a=i*2*PI/16,b=(i+1)*2*PI/16;c.tri3({x,.02f,z},{x+std::sin(a)*.7f,.02f,z+std::cos(a)*.45f},{x+std::sin(b)*.7f,.02f,z+std::cos(b)*.45f},{.21f,.20f,.16f,.45f},false);}
    float step=std::sin(time*7+hash)*.1f;
    c.ellipsoid(p+side*.18f+Vec{0,.43f,step},{.13f,.40f,.14f},dark,yaw);c.ellipsoid(p-side*.18f+Vec{0,.43f,-step},{.13f,.40f,.14f},dark,yaw);
    c.box(p+side*.18f+Vec{0,.1f,.05f},{.26f,.2f,.4f},dark,yaw);c.box(p-side*.18f+Vec{0,.1f,.05f},{.26f,.2f,.4f},dark,yaw);
    bool armour=!f.value("armour",std::string{}).empty();
    c.ellipsoid(p+Vec{0,1.19f,0},{.35f,.43f,.23f},armour?metal:cloth,yaw,8,12);
    c.ellipsoid(p+side*.35f+Vec{0,1.44f,0},{.19f,.16f,.22f},armour?metal:cloth,yaw);
    c.ellipsoid(p-side*.35f+Vec{0,1.44f,0},{.19f,.16f,.22f},armour?metal:cloth,yaw);
    c.box(p+Vec{0,.87f,0},{.69f,.12f,.40f},{.22f,.17f,.11f},yaw);c.box(p+front*.225f+Vec{0,.87f,0},{.13f,.13f,.05f},GOLD,yaw);
    c.cylinder(p+Vec{0,1.56f,0},.11f,.14f,skin,8);c.ellipsoid(p+Vec{0,1.87f,0},{.18f,.23f,.18f},skin,yaw,8,12);
    c.ellipsoid(p+Vec{0,2.04f,0},{.195f,.12f,.195f},armour||!f.value("helmet",std::string{}).empty()?metal:Colour{.19f,.15f,.11f},yaw,6,12);
    c.ellipsoid(p+front*.178f+Vec{0,1.86f,0},{.04f,.075f,.06f},skin,yaw,4,6);
    c.box(p+front*.18f+side*.075f+Vec{0,1.92f,0},{.055f,.03f,.03f},dark,yaw);c.box(p+front*.18f-side*.075f+Vec{0,1.92f,0},{.055f,.03f,.03f},dark,yaw);
    bool block=f.value("block",false);std::string attack=f.value("attack",std::string{});
    float phase=f.value("windup",0.f)>0?1-f.value("windup",0.f)/.22f:std::fmod(time*5,1.f);
    Vec shoulder=p+side*.42f+Vec{0,1.42f,0},hand=p+side*.53f+front*.34f+Vec{0,1.12f,0};
    Vec tip=hand+front*.75f+Vec{0,.9f,0};
    std::string weapon=f.value("weapon",std::string("knife"));float length=weapon=="knife"||weapon=="dagger"?.55f:weapon=="greatsword"?1.85f:weapon=="spear"||weapon=="halberd"?2.3f:weapon=="longsword"?1.5f:1.15f;
    if(block){hand=p+front*.55f+Vec{0,1.52f,0};tip=hand+side*.8f+Vec{0,.4f,0};}
    else if(!attack.empty()){
        if(attack=="overhead"){hand=p+front*.6f+Vec{0,1.65f,0};tip=hand+front*(phase*1.25f)+Vec{0,1.1f-phase*1.8f,0};}
        else if(attack=="thrust"){hand=p+side*.25f+front*(.65f+phase*.25f)+Vec{0,1.3f,0};tip=hand+front*length;}
        else{float swing=(phase*2-1)*1.9f*(attack=="left"?1:-1);hand=p+side*.15f+front*.45f+Vec{0,1.3f,0};tip=hand+Vec{std::sin(yaw+swing)*length,.15f,std::cos(yaw+swing)*length};}
    }else tip=hand+norm(tip-hand)*length;
    c.beam(shoulder,hand,.13f,cloth);c.box(hand,{.17f,.17f,.17f},skin,yaw);
    held_equipment(c,weapon,hand,tip,side,front);
    Vec left=p-side*.48f+front*(block?.5f:.12f)+Vec{0,1.15f,0};c.beam(p-side*.4f+Vec{0,1.42f,0},left,.12f,cloth);c.box(left,{.17f,.17f,.17f},skin,yaw);
    if(!f.value("shield",std::string{}).empty()){c.box(left+front*.1f,{.55f,.75f,.13f},dark,yaw);c.box(left+front*.18f,{.48f,.66f,.05f},metal,yaw);c.box(left+front*.22f,{.12f,.14f,.07f},GOLD,yaw);}
}
