#pragma once
#include <unordered_map>
#include <tuple>
// Half-metre blocks. This generator mirrors voxel_world.py, including negative coordinates.
namespace voxel {
inline uint32_t noise(uint32_t seed,int x,int z){uint32_t n=seed^(uint32_t(x)*374761393u)^(uint32_t(z)*668265263u);n=(n^(n>>13))*1274126177u;return (n^(n>>16))&0xffffff;}
inline int divfloor(int a,int b){return int(std::floor(double(a)/b));}
inline int height(uint32_t seed,int x,int z){
    auto layer=[&](int scale){int gx=divfloor(x,scale),gz=divfloor(z,scale);double u=double(x-gx*scale)/scale,v=double(z-gz*scale)/scale;u=u*u*(3-2*u);v=v*v*(3-2*v);
        double a=noise(seed,gx,gz)/16777215.,b=noise(seed,gx+1,gz)/16777215.,c=noise(seed,gx,gz+1)/16777215.,d=noise(seed,gx+1,gz+1)/16777215.;return (a*(1-u)+b*u)*(1-v)+(c*(1-u)+d*u)*v;};
    return std::abs(x)<=8&&std::abs(z)<=8?4:3+int(layer(36)*13+layer(12)*3);
}
inline int material(const std::string& s){const char* names[]={"","grass","dirt","stone","wood","leaves","iron_ore","crystal","glass","iron","bedrock"};for(int i=0;i<11;i++)if(s==names[i])return i;return 0;}
inline Colour colour(int m){const Colour values[]={{0,0,0},{.34f,.46f,.25f},{.39f,.29f,.19f},{.46f,.49f,.48f},{.40f,.29f,.17f},{.22f,.39f,.21f},{.48f,.36f,.26f},{.42f,.66f,.85f},{.60f,.80f,.85f,.34f},{.54f,.59f,.59f},{.20f,.22f,.23f}};return values[std::clamp(m,0,10)];}
struct Block{int material=0,shape=0,rotation=0;};
struct Face{Vec a,b,c,d;Colour colour;};
struct Landscape {
    std::vector<Face> faces;int centreX=INT_MIN,centreZ=0,revision=-1;uint32_t seed=0;std::string id;
    std::map<std::pair<int,int>,int> heights;std::map<std::tuple<int,int,int>,Block> edits;
    int terrain(int x,int z){auto key=std::make_pair(x,z);auto it=heights.find(key);if(it!=heights.end())return it->second;return heights[key]=height(seed,x,z);}
    int generated(int x,int y,int z){int floor=terrain(x,z);if(y<=-32)return 10;
        if(y<=floor){if(y==floor)return 1;if(y>=floor-3)return 2;int ore=noise(seed+97,x+y*11,z-y*7)%100;return y<floor-8&&ore==0?7:ore<5?6:3;}
        for(int gx=divfloor(x,14)-1;gx<=divfloor(x,14)+1;gx++)for(int gz=divfloor(z,14)-1;gz<=divfloor(z,14)+1;gz++){
            int tx=gx*14+3+noise(seed+3,gx,gz)%8,tz=gz*14+3+noise(seed+5,gx,gz)%8;if(std::abs(tx)<=10&&std::abs(tz)<=10)continue;int base=terrain(tx,tz);
            if(x==tx&&z==tz&&y>base&&y<=base+6)return 4;
            if(y>=base+4&&y<=base+8&&(x-tx)*(x-tx)+(z-tz)*(z-tz)+(y-base-6)*(y-base-6)<=10)return 5;
        }return 0;
    }
    Block block(int x,int y,int z){auto it=edits.find({x,y,z});return it==edits.end()?Block{generated(x,y,z),0,0}:it->second;}
    void quad(Vec a,Vec b,Vec c,Vec d,Colour col){faces.push_back({a,b,c,d,col});}
    void shaped(int x,int y,int z,Block b){
        Vec origin{x*.5f,y*.5f,z*.5f};Colour col=colour(b.material);float bottom=b.shape==4?.35f:0.f,top=b.shape==1?.5f:b.shape==4?.65f:1.f;
        auto point=[&](float a,float v,float c){for(int i=0;i<b.rotation;i++){float next=c;c=1-a;a=next;}return origin+Vec{a*.5f,v*.5f,c*.5f};};
        if(b.shape==3){for(int i=0;i<12;i++){float a=i*PI/6,c=(i+1)*PI/6;Vec p=point(.5f+std::cos(a)*.22f,0,.5f+std::sin(a)*.22f),q=point(.5f+std::cos(c)*.22f,0,.5f+std::sin(c)*.22f);quad(p,q,q+Vec{0,.5f,0},p+Vec{0,.5f,0},col);quad(origin+Vec{.25f,.5f,.25f},p+Vec{0,.5f,0},q+Vec{0,.5f,0},origin+Vec{.25f,.5f,.25f},col);}return;}
        Vec v[8];for(int i=0;i<8;i++){float a=i&1?1:0,c=i&4?1:0,h=i&2?(b.shape==2?a:top):bottom;v[i]=point(a,h,c);}
        int sides[][4]={{0,1,3,2},{4,6,7,5},{0,4,5,1},{2,3,7,6},{0,2,6,4},{1,5,7,3}};int offsets[][3]={{0,0,-1},{0,0,1},{0,-1,0},{0,1,0},{-1,0,0},{1,0,0}};
        for(int i=0;i<6;i++){auto& d=offsets[i];auto other=block(x+d[0],y+d[1],z+d[2]);if(b.shape==0&&other.material&&other.material!=8&&other.shape==0)continue;auto& s=sides[i];quad(v[s[0]],v[s[1]],v[s[2]],v[s[3]],col);}
    }
    void rebuild(const json& state,int cx,int cz){
        id=state.value("id",std::string{});seed=state.value("seed",0u);revision=state.value("revision",0);centreX=cx;centreZ=cz;faces.clear();edits.clear();heights.clear();
        int low=0,high=32;
        if(state.contains("edits"))for(auto it=state["edits"].begin();it!=state["edits"].end();++it){int x,y,z;if(sscanf(it.key().c_str(),"%d,%d,%d",&x,&y,&z)!=3)continue;Block b;if(!it.value().is_null()){b.material=material(it.value().value("material",std::string{}));const char* shapes[]={"cube","slab","ramp","pillar","beam"};for(int i=0;i<5;i++)if(it.value().value("shape",std::string("cube"))==shapes[i])b.shape=i;b.rotation=it.value().value("rotation",0);}edits[{x,y,z}]=b;if(std::abs(x-cx)<=48&&std::abs(z-cz)<=48){low=std::min(low,y-1);high=std::max(high,y+1);}}
        low=std::max(-32,low);high=std::min(159,high);
        // Near-field exposed faces include all excavations received from the server.
        for(int x=cx-48;x<=cx+48;x++)for(int z=cz-48;z<=cz+48;z++){
            int floor=terrain(x,z);for(int y=low;y<=std::max(high,floor+8);y++){auto b=block(x,y,z);if(!b.material)continue;shaped(x,y,z,b);}
        }
        // A coarse horizon extends the world without drawing distant underground blocks.
        for(int x=cx-256;x<cx+256;x+=8)for(int z=cz-256;z<cz+256;z+=8){if(std::abs(x-cx)<44&&std::abs(z-cz)<44)continue;quad({x*.5f,(terrain(x,z)+1)*.5f,z*.5f},{(x+8)*.5f,(terrain(x+8,z)+1)*.5f,z*.5f},{(x+8)*.5f,(terrain(x+8,z+8)+1)*.5f,(z+8)*.5f},{x*.5f,(terrain(x,z+8)+1)*.5f,(z+8)*.5f},colour(1));}
    }
    void draw(Canvas& c,const json& state,Vec p,float time){
        int cx=int(std::floor(p.x*2)),cz=int(std::floor(p.z*2));
        if(id!=state.value("id",std::string{})||revision!=state.value("revision",0)||std::abs(cx-centreX)>=8||std::abs(cz-centreZ)>=8)rebuild(state,cx,cz);
        c.ambient=.55f;c.sunlight=.45f;c.fogStart=35;c.fogRange=115;c.fogColour={.68f,.77f,.73f};c.sunDirection=norm({-.4f,1,.3f});
        for(int i=0;i<40;i++)c.rect(0,i*20.f,1280,21,colour_mix({.30f,.48f,.63f},c.fogColour,i/40.f));
        for(auto& f:faces)c.quad(f.a,f.b,f.c,f.d,f.colour);
        auto aim=state.value("aim_block",json{});if(!aim.is_null()&&aim.contains("cell")){
            auto a=aim["cell"];Vec corner{float(a[0])*.5f,float(a[1])*.5f,float(a[2])*.5f};Colour glow{.97f,.77f,.40f,.8f};
            for(int i=0;i<8;i++)for(int bit:{1,2,4})if(!(i&bit)){Vec p=corner+Vec{i&1?.505f:-.005f,i&2?.505f:-.005f,i&4?.505f:-.005f},q=p;int end=i|bit;q=corner+Vec{end&1?.505f:-.005f,end&2?.505f:-.005f,end&4?.505f:-.005f};c.beam(p,q,.006f,glow);}
            float progress=state.value("mine_progress",0.f);if(progress>0){for(int i=0;i<int(progress*10)+1;i++){float a=i*2.4f;Vec s=corner+Vec{.25f+std::sin(a)*.22f,.505f,.25f+std::cos(a)*.22f};c.beam(s,s+Vec{std::sin(a+1)*.15f,0,std::cos(a+1)*.15f},.008f,{.13f,.12f,.10f});}for(int i=0;i<6;i++){float t=std::fmod(time*3+i*.17f,1.f);Vec p=corner+Vec{.25f+std::sin(i*3.f)*t*.55f,.5f+t*.3f-t*t,.25f+std::cos(i*3.f)*t*.55f};c.box(p,{.035f,.035f,.035f},colour(material(aim["block"].value("material",std::string("stone")))));}}
        }
    }
};
}
