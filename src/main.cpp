#include "render.hpp"
#include "net.hpp"
#include "scene.hpp"
#include <windowsx.h>
#include <mmsystem.h>
#include <filesystem>
#include <iomanip>

enum class Screen {Home,Auth,Shop,Settings,Help};
struct App {
    HWND window{};int width=1280,height=800;bool running=true,clicked=false,locked=false,vulkan=false;
    float mouseX=0,mouseY=0,yaw=0,pitch=.28f,time=0;int attackMode=0;
    bool arena=false,pendingPlay=false,wasDead=false;Screen screen=Screen::Home;
    int authMode=0,focus=-1;std::string fields[5]={"", "", "", "", "http://127.0.0.1:8765"};
    std::string localMessage;float messageUntil=0,damageUntil=0,lastEventTime=-1;
    Network net;Canvas canvas;std::unique_ptr<Renderer> renderer;
    std::map<std::string,Vec> positions;
    json world,profile;std::string player,status,error,notice;bool connected=false,busy=false;
    float hp=100,stamina=100,death=0,spawnSafe=0;int kills=0,coins=100;
    bool smoke=false,smokeArena=false;std::string screenshot;
    bool captureNext=false,authSubmitted=false;std::string alignedPlayer;

    bool hover(float x,float y,float w,float h){return mouseX>=x&&mouseX<=x+w&&mouseY>=y&&mouseY<=y+h;}
    bool button(float x,float y,float w,float h,const std::string& label,bool primary=false){
        bool hot=hover(x,y,w,h);Colour fill=primary?(hot?Colour{1,.76f,.39f}:GOLD):(hot?Colour{.17f,.22f,.21f,.97f}:Colour{.10f,.14f,.14f,.94f});
        canvas.rect(x,y,w,h,fill);canvas.border(x,y,w,h,primary?GOLD:Colour{.26f,.32f,.30f});
        canvas.text(x+(w-Canvas::text_width(label,2))/2,y+(h-22)/2,label,2,primary?INK:WHITE);
        return hot&&clicked&&!busy;
    }
    void field(float x,float y,float w,const std::string& label,int index,bool secret=false){
        canvas.text(x,y,label,1.6f,MUTED);canvas.rect(x,y+22,w,43,{.065f,.09f,.10f,.98f});canvas.border(x,y+22,w,43,focus==index?GOLD:Colour{.23f,.29f,.28f});
        std::string value=secret?std::string(fields[index].size(),'*'):fields[index];
        while(!value.empty()&&Canvas::text_width(value,1.7f)>w-28)value.erase(value.begin());
        canvas.text(x+14,y+36,value,1.7f,WHITE);
        if(focus==index&&std::fmod(time,1)<.5f)canvas.rect(x+14+Canvas::text_width(value,1.7f),y+34,2,20,GOLD);
        if(hover(x,y+22,w,43)&&clicked)focus=index;
    }
    void toast(std::string value,bool warning=false){localMessage=std::move(value);messageUntil=time+6;if(warning)damageUntil=time+.15f;}
    void play(){
        {std::lock_guard<std::mutex> guard(net.mutex);if(net.joined){arena=true;return;}}
        bool needsGuest;{std::lock_guard<std::mutex> guard(net.mutex);needsGuest=net.token.empty();}
        if(needsGuest)net.queue("/auth/guest");
        pendingPlay=true;
    }
    void engine(bool useVulkan){
        renderer.reset();try{if(useVulkan)renderer=std::make_unique<VulkanRenderer>(window);else renderer=std::make_unique<OpenGLRenderer>(window);vulkan=useVulkan;}
        catch(const std::exception& e){localMessage=std::string("Vulkan unavailable: ")+e.what();messageUntil=time+9;renderer=std::make_unique<OpenGLRenderer>(window);vulkan=false;}
    }
    void snapshot(){
        std::lock_guard<std::mutex> guard(net.mutex);world=net.world;profile=net.profile;player=net.player;connected=net.connected;busy=net.busy;error=net.error;notice=net.message;
    }
    void update(float dt){
        time+=dt;snapshot();
        if(pendingPlay&&!busy){
            bool authed,joined;{std::lock_guard<std::mutex> guard(net.mutex);authed=!net.token.empty();joined=net.joined;}
            if(joined){arena=true;pendingPlay=false;focus=-1;}
            else if(authed&&error.empty())net.queue("/arena/join");
            else if(!error.empty())pendingPlay=false;
        }
        if(screen==Screen::Auth&&authSubmitted&&!profile.empty()&&authMode<2&&!busy&&error.empty()){screen=Screen::Home;focus=-1;fields[1].clear();authSubmitted=false;toast("Signed in. Your equipment is saved on this server.");}
        if(!profile.empty()){coins=profile.value("coins",100);kills=profile.value("kills",0);}
        json self;
        if(world.contains("fighters"))for(auto& f:world["fighters"]){
            std::string id=f.value("id",std::string{});Vec target{f.value("x",0.f),0,f.value("z",0.f)};
            if(!positions.count(id))positions[id]=target;else positions[id]=positions[id]+(target-positions[id])*std::min(1.f,dt*15);
            if(id==player)self=f;
        }
        if(!self.is_null()){
            if(alignedPlayer!=player){yaw=std::atan2(-self.value("x",0.f),-self.value("z",0.f));alignedPlayer=player;}
            float current=self.value("hp",100.f);if(current<hp)damageUntil=time+.22f;hp=current;stamina=self.value("stamina",100.f);death=self.value("dead",0.f);
            spawnSafe=self.value("spawn_safe",0.f);
            if(death>0&&!wasDead)PlaySoundA("assets/fall.wav",nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT);
            wasDead=death>0;
        }
        if(world.contains("events"))for(auto& e:world["events"]){float eventTime=e.value("time",0.f);std::string kind=e.value("kind",std::string{});if(eventTime>lastEventTime&&(kind=="hit"||kind=="parry")&&(e.value("source",std::string{})==player||e.value("target",std::string{})==player))PlaySoundA("assets/steel.wav",nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT);lastEventTime=std::max(lastEventTime,eventTime);}
        bool foreground=GetForegroundWindow()==window;
        bool capture=arena&&screen==Screen::Home&&foreground&&death<=0;
        if(capture&&!locked){POINT centre{width/2,height/2};ClientToScreen(window,&centre);if(!smoke)SetCursorPos(centre.x,centre.y);ShowCursor(FALSE);locked=true;}
        if(!capture&&locked){ClipCursor(nullptr);ShowCursor(TRUE);locked=false;}
        if(capture){
            POINT centre{width/2,height/2};ClientToScreen(window,&centre);POINT p;GetCursorPos(&p);
            if(!smoke){yaw+=(p.x-centre.x)*.0035f;pitch=std::clamp(pitch+(p.y-centre.y)*.002f,-.15f,.72f);SetCursorPos(centre.x,centre.y);}
            RECT clip{};GetClientRect(window,&clip);POINT a{clip.left,clip.top},b{clip.right,clip.bottom};ClientToScreen(window,&a);ClientToScreen(window,&b);clip={a.x,a.y,b.x,b.y};ClipCursor(&clip);
        }
        auto key=[&](int k){return capture&&(GetAsyncKeyState(k)&0x8000);};
        for(int i=0;i<4;i++)if(key('1'+i))attackMode=i;
        float forward=static_cast<float>(key('W'))-static_cast<float>(key('S'));
        float side=static_cast<float>(key('D'))-static_cast<float>(key('A'));
        std::string attacks[]={"left","right","overhead","thrust"};
        json input={{"move",{std::sin(yaw)*forward+std::cos(yaw)*side,std::cos(yaw)*forward-std::sin(yaw)*side}},
                    {"yaw",yaw},{"attack",key(VK_LBUTTON)?attacks[attackMode]:std::string{}},{"block",key(VK_RBUTTON)},
                    {"dodge",key(VK_SHIFT)},{"jump",key(VK_SPACE)}};
        if(smokeArena){input["move"]={0,0};input["attack"]="";}
        {std::lock_guard<std::mutex> guard(net.mutex);net.input=input;}
    }
    void world_view(){
        if(arena&&!player.empty()&&positions.count(player)){
            Vec p=positions[player];canvas.set_camera(p+Vec{-std::sin(yaw)*5.2f,2.7f+pitch*4,-std::cos(yaw)*5.2f},p+Vec{std::sin(yaw)*2,1.25f,std::cos(yaw)*2});
        }else{
            float a=.52f+std::sin(time*.025f)*.2f;canvas.set_camera({std::sin(a)*9+4,3.0f,std::cos(a)*9},{5.5f,1.15f,0});
        }
        environment(canvas,time);
        if(world.contains("fighters")){
            for(auto f:world["fighters"]){std::string id=f.value("id",std::string{});if(positions.count(id)){f["x"]=positions[id].x;f["z"]=positions[id].z;}fighter(canvas,f,time,id==player);}
        }else{
            // Clearly visual menu scene, not a fabricated online population.
            json a={{"id","menu-a"},{"x",2.7},{"z",2.0},{"yaw",-1.2},{"weapon","longsword"},{"armour","mail"},{"shield","buckler"}};
            json b={{"id","menu-b"},{"x",-.2},{"z",1.4},{"yaw",1.4},{"weapon","sabre"},{"armour","leather"},{"attack","left"},{"windup",.1}};
            fighter(canvas,a,time);fighter(canvas,b,time);
        }
        canvas.flush3();
        if(arena&&world.contains("fighters"))for(auto& f:world["fighters"]){
            if(f.value("id",std::string{})==player||f.value("dead",0.f)>0)continue;
            float x,y,d;Vec p{f.value("x",0.f),2.55f,f.value("z",0.f)};
            if(canvas.project(p,x,y,d)&&d<25&&x>40&&x<1240&&y>95&&y<660){
                float s=d<12?1.5f:1.2f;std::string name=f.value("name",std::string("Fighter"));canvas.text(x-name.size()*s*3,y,name,s,WHITE);
                canvas.rect(x-30,y+16,60,4,{.08f,.10f,.10f,.8f});canvas.rect(x-30,y+16,60*f.value("hp",100.f)/100,4,f.value("bot",false)?Colour{.82f,.47f,.24f}:Colour{.38f,.70f,.60f});
                if(f.value("bot",false))canvas.text(x-24,y+25,"AI "+std::to_string(f.value("depth",2)),1,MUTED);
            }
        }
    }
    void emblem(float x,float y,float size){
        canvas.line(x-size*.32f,y-size*.42f,x+size*.32f,y+size*.42f,3,GOLD);canvas.line(x+size*.32f,y-size*.42f,x-size*.32f,y+size*.42f,3,GOLD);
        canvas.line(x-size*.43f,y+size*.17f,x-size*.12f,y+size*.43f,4,GOLD);canvas.line(x+size*.43f,y+size*.17f,x+size*.12f,y+size*.43f,4,GOLD);
    }
    void home(){
        for(int i=0;i<384;i++)canvas.rect(i*2.f,0,2,800,{.035f,.055f,.058f,std::max(0.f,.99f-i*.00245f)});
        canvas.rect(0,0,1280,82,{.025f,.045f,.047f,.88f});emblem(52,39,43);canvas.text(89,27,"MOTLON",2.4f);canvas.text(89,51,"INDEPENDENT ARENA COMBAT",1.1f,MUTED);
        canvas.text(650,35,"THE ARENA",1.6f,GOLD);
        if(button(830,20,140,43,"ARMOURY"))screen=Screen::Shop;
        if(button(983,20,110,43,"SETTINGS"))screen=Screen::Settings;
        if(button(1106,20,140,43,profile.empty()?"SIGN IN":"ACCOUNT")){screen=Screen::Auth;authMode=0;focus=0;}
        canvas.text(57,157,"STEEL. SAND. SURVIVAL.",1.9f,GOLD);
        canvas.text(52,215,"XERVEXL",8.2f,WHITE);
        canvas.rect(57,299,88,3,GOLD);
        canvas.text(57,334,"NO CROWN. NO FINAL ROUND.",2.1f,WHITE);
        canvas.text(57,380,"An open arena of blades and nerve.\nRead your opponent. Choose your strike.\nFall, return, and fight again.",1.75f,MUTED);
        if(button(57,483,343,70,busy?"CONNECTING...":(!player.empty()?"RETURN TO ARENA":"ENTER THE ARENA"),true))play();
        if(button(414,483,142,70,"HOW TO PLAY"))screen=Screen::Help;
        canvas.text(57,585,profile.empty()?"PLAY AS GUEST OR SIGN IN TO SAVE YOUR GEAR":("WELCOME, "+profile.value("username",std::string("FIGHTER"))),1.4f,MUTED);
        canvas.rect(57,631,490,96,{.07f,.10f,.11f,.93f});canvas.border(57,631,490,96,{.19f,.25f,.25f});canvas.rect(57,631,3,96,GOLD);
        canvas.text(77,651,"A BLADE IS ALL YOU NEED",1.7f,GOLD);canvas.text(77,680,"Start with a knife. Earn crowns in battle.\nBuild your own arsenal. No magic. No powers.",1.45f,WHITE);
        canvas.rect(930,600,294,125,{.04f,.065f,.067f,.89f});canvas.text(951,620,"THE SAND NEVER EMPTIES",1.5f,GOLD);
        canvas.text(951,652,"10 FIGHTERS MINIMUM\nAI DEPTH 2 / 3 / 4 / 5\nONLINE SERVER OR LOCAL BOTS",1.25f,WHITE);
        canvas.rect(0,755,1280,45,{.025f,.043f,.045f,.95f});canvas.circle(34,777,4,connected?Colour{.40f,.72f,.48f}:GOLD);
        canvas.text(48,771,connected?"SERVER CONNECTED":"LOCAL / CONNECT TO START",1.35f,MUTED);
        canvas.text(830,771,std::string(renderer->name())+"  /  WINDOWS  /  V0.1",1.35f,MUTED);
    }
    void panel(const std::string& title,const std::string& subtitle){
        canvas.rect(0,0,1280,800,{.02f,.035f,.035f,.72f});canvas.rect(276,102,728,610,{.055f,.079f,.083f,.98f});canvas.border(276,102,728,610,{.27f,.32f,.29f});
        canvas.rect(276,102,728,3,GOLD);canvas.text(314,135,title,3,GOLD);canvas.text(314,171,subtitle,1.35f,MUTED);
        if(button(919,126,48,40,"X")){screen=Screen::Home;focus=-1;}
    }
    void auth(){
        std::string title=authMode==0?"SIGN IN":authMode==1?"CREATE ACCOUNT":authMode==2?"RECOVER ACCOUNT":"RESET PASSWORD";
        panel(title,"YOUR ACCOUNT LIVES ON YOUR SELECTED ARENA SERVER");
        if(authMode<2){
            if(button(315,211,176,41,"SIGN IN",authMode==0)){authMode=0;focus=0;}
            if(button(503,211,216,41,"CREATE ACCOUNT",authMode==1)){authMode=1;focus=0;}
            field(315,282,650,"USERNAME",0);
            field(315,367,650,"PASSWORD (8+ CHARACTERS)",1,true);
            if(authMode==1)field(315,452,650,"EMAIL",2);
            if(button(315,authMode==1?546:465,650,56,busy?"PLEASE WAIT...":authMode==0?"SIGN IN":"CREATE ACCOUNT",true)){
                net.queue(authMode==0?"/auth/login":"/auth/register",{{"username",fields[0]},{"password",fields[1]},{"email",fields[2]}});
                authSubmitted=true;
            }
            if(authMode==0&&button(315,538,310,40,"FORGOT PASSWORD?")){authMode=2;focus=0;}
            canvas.text(315,637,"GUEST PROGRESS IS TEMPORARY. REGISTER TO SAVE EQUIPMENT.",1.25f,MUTED);
        }else if(authMode==2){
            field(315,232,650,"USERNAME",0);field(315,325,650,"MATCHING EMAIL",2);
            if(button(315,433,650,55,"EMAIL RESET CODE",true))net.queue("/auth/forgot",{{"username",fields[0]},{"email",fields[2]}});
            if(button(315,514,650,45,"I ALREADY HAVE A RESET CODE")){authMode=3;focus=3;}
            canvas.text(315,599,"Email delivery requires SMTP on the server.\nLocal mode does not pretend to send email.",1.5f,MUTED);
        }else{
            field(315,232,650,"RESET CODE FROM EMAIL",3);field(315,325,650,"NEW PASSWORD",1,true);
            if(button(315,433,650,55,"UPDATE PASSWORD",true))net.queue("/auth/reset",{{"code",fields[3]},{"password",fields[1]}});
            if(button(315,514,650,45,"BACK TO SIGN IN")){authMode=0;focus=0;}
        }
    }
    void weapon_icon(float x,float y,const std::string& id,float scale=1){
        bool shield=id=="buckler"||id=="kite",armour=id=="leather"||id=="mail"||id=="plate";
        if(shield){canvas.circle(x,y,23*scale,{.34f,.38f,.37f});canvas.circle(x,y,17*scale,{.18f,.24f,.22f});canvas.circle(x,y,7*scale,GOLD);}
        else if(armour){canvas.rect(x-18*scale,y-24*scale,36*scale,48*scale,{.46f,.50f,.47f});canvas.triangle(x-18*scale,y-24*scale,x,y-35*scale,x+18*scale,y-24*scale,{.59f,.62f,.57f});canvas.rect(x-20*scale,y+14*scale,40*scale,5*scale,GOLD);}
        else{float len=id=="knife"?27:48;canvas.line(x,y+18*scale,x,y-len*scale,5*scale,{.75f,.78f,.75f});canvas.line(x-14*scale,y+16*scale,x+14*scale,y+16*scale,4*scale,GOLD);canvas.line(x,y+18*scale,x,y+35*scale,6*scale,{.30f,.22f,.15f});canvas.triangle(x-2*scale,y-len*scale,x+2*scale,y-len*scale,x,y-(len+8)*scale,WHITE);}
    }
    void shop(){
        canvas.rect(0,0,1280,800,{.025f,.041f,.044f,.96f});canvas.text(46,36,"THE ARMOURY",3.6f,GOLD);canvas.text(47,81,"EARN 45 CROWNS PER DEFEATED FIGHTER. PURCHASED ITEMS ARE EQUIPPED.",1.4f,MUTED);
        canvas.text(931,48,std::to_string(coins)+" CROWNS",2,GOLD);if(button(1127,30,106,46,"BACK"))screen=Screen::Home;
        if(profile.empty()){canvas.text(49,126,"ENTER THE ARENA AS A GUEST OR SIGN IN BEFORE BUYING.",1.6f,WHITE);}
        std::vector<json> items={
            {{"id","knife"},{"name","WORN KNIFE"},{"price",0},{"detail","FAST / SHORT REACH"}},
            {{"id","arming"},{"name","ARMING SWORD"},{"price",180},{"detail","BALANCED / 23 DAMAGE"}},
            {{"id","sabre"},{"name","CAVALRY SABRE"},{"price",420},{"detail","QUICK / 25 DAMAGE"}},
            {{"id","longsword"},{"name","STEEL LONGSWORD"},{"price",720},{"detail","LONG REACH / 31 DAMAGE"}},
            {{"id","greatsword"},{"name","GREATSWORD"},{"price",1100},{"detail","HEAVY / 39 DAMAGE"}},
            {{"id","buckler"},{"name","IRON BUCKLER"},{"price",260},{"detail","BLOCKS 58% OF DAMAGE"}},
            {{"id","kite"},{"name","KITE SHIELD"},{"price",580},{"detail","BLOCKS 78% OF DAMAGE"}},
            {{"id","leather"},{"name","LEATHER ARMOUR"},{"price",320},{"detail","12% DAMAGE REDUCTION"}},
            {{"id","mail"},{"name","CHAINMAIL"},{"price",680},{"detail","24% DAMAGE REDUCTION"}},
            {{"id","plate"},{"name","STEEL CUIRASS"},{"price",1200},{"detail","34% DEFENCE / SLOWER"}}
        };
        for(int i=0;i<10;i++){
            float x=47+(i%5)*241,y=166+(i/5)*272;auto& item=items[i];std::string id=item["id"];
            bool owned=false;if(profile.contains("inventory"))for(auto& v:profile["inventory"])if(v==id)owned=true;
            bool equipped=profile.value("weapon",std::string{})==id||profile.value("shield",std::string{})==id||profile.value("armour",std::string{})==id;
            canvas.rect(x,y,225,251,{.085f,.12f,.125f});canvas.border(x,y,225,251,equipped?GOLD:Colour{.20f,.27f,.26f});
            canvas.text(x+15,y+16,equipped?"EQUIPPED":owned?"OWNED":"AVAILABLE",1.15f,equipped?GOLD:MUTED);
            weapon_icon(x+112,y+91,id,.9f);canvas.text(x+13,y+147,item["name"],1.6f,WHITE);canvas.text(x+13,y+174,item["detail"],1.05f,MUTED);
            std::string label=equipped?"EQUIPPED":owned?"EQUIP":std::to_string(item["price"].get<int>())+" CROWNS";
            if(button(x+13,y+203,199,35,label,owned&&!equipped)&&!equipped){
                if(profile.empty())toast("Enter the arena or sign in first.");
                else net.queue(owned?"/shop/equip":"/shop/buy",{{"item",id}});
            }
        }
        canvas.text(48,746,"WEAPONS TRADE REACH AND DAMAGE AGAINST SPEED. ARMOUR DOES NOT MAKE YOU INVINCIBLE.",1.3f,MUTED);
    }
    void settings(){
        panel("ARENA SETTINGS","A LOCAL SERVER WORKS NOW. REMOTE SERVERS CAN BE ADDED LATER.");
        field(315,233,650,"SERVER ADDRESS",4);
        if(button(315,321,650,51,"CONNECT TO THIS SERVER",true)){
            arena=false;pendingPlay=false;net.queue("/arena/leave");net.server(fields[4]);net.queue("/health");positions.clear();
        }
        canvas.text(315,419,"GRAPHICS API",1.7f,GOLD);
        if(button(315,455,315,52,"OPENGL",!vulkan))engine(false);
        if(button(649,455,316,52,"VULKAN",vulkan))engine(true);
        canvas.text(315,548,"Use HTTPS for an internet server.\nYour account belongs to the selected server.\nOpenGL is the fallback when Vulkan is unavailable.\nNo administrator rights are required.",1.45f,MUTED);
    }
    void help(){
        panel("READ THE BLADE","DIRECTIONAL SWORD COMBAT. SMALL JUMPS. NO SUPERNATURAL POWERS.");
        std::vector<std::pair<std::string,std::string>> rows={{"W A S D","MOVE"},{"MOUSE","TURN / LOOK"},{"LEFT CLICK","ATTACK"},{"RIGHT CLICK","HOLD BLOCK / PARRY"},{"1 / 2 / 3 / 4","LEFT / RIGHT / OVERHEAD / THRUST"},{"SHIFT","DODGE - COSTS STAMINA"},{"SPACE","SMALL JUMP"},{"E","ARMOURY"},{"ESC","MENU / RESUME"}};
        float y=227;for(auto& row:rows){canvas.text(315,y,row.first,1.6f,GOLD);canvas.text(550,y,row.second,1.4f,WHITE);canvas.rect(315,y+23,650,1,{.17f,.23f,.22f});y+=39;}
        canvas.text(315,610,"Watch the attack windup. Face attacks to block.\nDodge to avoid a hit, then punish the recovery.\nThere is no winner: after falling, respawn in 3.5 seconds.",1.4f,MUTED);
    }
    void hud(){
        canvas.rect(22,20,440,67,{.035f,.055f,.058f,.89f});emblem(53,52,33);canvas.text(80,34,"XERVEXL",2.2f,GOLD);
        canvas.text(80,62,"FREE ARENA / NO FINAL ROUND",1.1f,MUTED);
        canvas.rect(997,20,261,67,{.035f,.055f,.058f,.89f});
        canvas.text(1013,35,std::to_string(world.value("humans",0))+" PLAYERS / "+std::to_string(world.value("bots",0))+" BOTS",1.4f,WHITE);canvas.text(1013,61,renderer->name(),1.15f,GOLD);
        canvas.line(634,400,646,400,1.3f,{1,1,1,.6f});canvas.line(640,394,640,406,1.3f,{1,1,1,.6f});
        if(spawnSafe>0){canvas.rect(443,145,394,44,{.035f,.055f,.058f,.89f});canvas.text(463,158,"SAFE ENTRY / DAMAGE STARTS SHORTLY",1.55f,GOLD);}
        canvas.rect(28,657,370,112,{.035f,.055f,.058f,.94f});canvas.text(47,673,profile.value("username",std::string("FIGHTER")),1.6f,WHITE);
        canvas.text(47,701,"HEALTH",1.1f,MUTED);canvas.rect(132,700,239,12,{.16f,.20f,.18f});canvas.rect(132,700,239*hp/100,12,{.62f,.26f,.19f});
        canvas.text(47,728,"STAMINA",1.1f,MUTED);canvas.rect(132,727,239,9,{.16f,.20f,.18f});canvas.rect(132,727,239*stamina/100,9,GOLD);
        canvas.text(47,752,std::to_string(kills)+" ELIMINATIONS / "+std::to_string(coins)+" CROWNS",1.15f,MUTED);
        std::string moves[]={"LEFT CUT","RIGHT CUT","OVERHEAD","THRUST"};
        for(int i=0;i<4;i++){float x=450+i*149;canvas.rect(x,714,141,54,i==attackMode?Colour{.38f,.28f,.16f,.94f}:Colour{.04f,.07f,.075f,.90f});canvas.border(x,714,141,54,i==attackMode?GOLD:Colour{.20f,.27f,.25f});canvas.text(x+13,727,std::to_string(i+1),1.5f,GOLD);canvas.text(x+12,750,moves[i],1.05f,WHITE);}
        canvas.text(470,681,"RMB BLOCK   SHIFT DODGE   SPACE JUMP",1.25f,MUTED);canvas.text(1100,728,"E ARMOURY\nESC MENU",1.35f,MUTED);
        if(world.contains("events")){float y=106;for(auto& e:world["events"])if(e.value("kind",std::string{})=="kill"&&world.value("time",0.f)-e.value("time",0.f)<8){std::string label=e.value("source",std::string{})+"  /  "+e.value("target",std::string{});canvas.rect(961,y-7,296,26,{.04f,.06f,.06f,.72f});canvas.text(974,y,label,1.2f,MUTED);y+=32;}}
        if(death>0){canvas.rect(0,0,1280,800,{.05f,.025f,.02f,.6f});canvas.text(415,315,"YOU FELL",5,GOLD);canvas.text(427,385,"BACK IN "+std::to_string(static_cast<int>(std::ceil(death)))+" SECONDS",2.1f,WHITE);canvas.text(418,430,"THE ARENA HAS NO FINAL ROUND.",1.6f,MUTED);}
        if(time<damageUntil){canvas.rect(0,0,1280,24,{.65f,.10f,.045f,.5f});canvas.rect(0,776,1280,24,{.65f,.10f,.045f,.5f});canvas.rect(0,0,24,800,{.65f,.10f,.045f,.5f});canvas.rect(1256,0,24,800,{.65f,.10f,.045f,.5f});}
    }
    void frame(){
        canvas.begin(width,height);world_view();
        if(arena&&screen==Screen::Home)hud();else{
            if(screen==Screen::Home)home();else if(screen==Screen::Auth)auth();else if(screen==Screen::Shop)shop();else if(screen==Screen::Settings)settings();else help();
        }
        std::string value=!error.empty()?error:!notice.empty()?notice:time<messageUntil?localMessage:std::string{};
        if(!value.empty()){
            if(value.size()>100)value=value.substr(0,100);
            canvas.rect(30,arena?114.f:92.f,1220,35,{.08f,.105f,.105f,.98f});canvas.text(44,arena?126.f:104.f,value,1.5f,!error.empty()?Colour{1,.55f,.32f}:GOLD);
        }
        renderer->captureRequested=captureNext;renderer->draw(canvas.mesh,width,height);clicked=false;
        if(captureNext&&!screenshot.empty())capture(screenshot);captureNext=false;
    }
    void capture(const std::string& path){
        if(renderer->pixels.size()!=static_cast<size_t>(width)*height*4)return;
        BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=width;info.bmiHeader.biHeight=-height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
        std::vector<unsigned char> bytes=renderer->pixels;for(size_t i=0;i<bytes.size();i+=4)std::swap(bytes[i],bytes[i+2]);
        BITMAPFILEHEADER header{};header.bfType=0x4d42;header.bfOffBits=sizeof(header)+sizeof(info.bmiHeader);header.bfSize=header.bfOffBits+static_cast<DWORD>(bytes.size());
        std::ofstream file(path,std::ios::binary);file.write(reinterpret_cast<char*>(&header),sizeof(header));file.write(reinterpret_cast<char*>(&info.bmiHeader),sizeof(info.bmiHeader));file.write(reinterpret_cast<char*>(bytes.data()),bytes.size());
    }
};

App* app=nullptr;
LRESULT CALLBACK window_proc(HWND w,UINT msg,WPARAM wp,LPARAM lp){
    if(!app)return DefWindowProc(w,msg,wp,lp);
    switch(msg){
        case WM_CLOSE:app->running=false;return 0;
        case WM_SIZE:app->width=std::max(1,static_cast<int>(LOWORD(lp)));app->height=std::max(1,static_cast<int>(HIWORD(lp)));return 0;
        case WM_MOUSEMOVE:app->mouseX=GET_X_LPARAM(lp)*1280.f/app->width;app->mouseY=GET_Y_LPARAM(lp)*800.f/app->height;return 0;
        case WM_LBUTTONDOWN:app->clicked=true;return 0;
        case WM_KEYDOWN:
            if(wp==VK_ESCAPE){if(app->screen!=Screen::Home){app->screen=Screen::Home;app->focus=-1;}else app->arena=!app->arena&& !app->player.empty();}
            if(wp=='E'&&app->arena)app->screen=app->screen==Screen::Shop?Screen::Home:Screen::Shop;
            if(wp==VK_TAB&&app->screen==Screen::Auth){app->focus=(app->focus+1)%(app->authMode==1?3:2);}
            if(wp==VK_F12){std::filesystem::create_directories("screenshots");app->captureNext=true;app->screenshot="screenshots/capture.bmp";app->toast("Screenshot saved in screenshots/capture.bmp");}
            return 0;
        case WM_CHAR:
            if(app->focus>=0){std::string& text=app->fields[app->focus];if(wp==8&&!text.empty())text.pop_back();else if(wp>=32&&wp<127&&text.size()<254)text+=static_cast<char>(wp);}
            return 0;
        default:return DefWindowProc(w,msg,wp,lp);
    }
}

int WINAPI WinMain(HINSTANCE instance,HINSTANCE,LPSTR command,int){
    try{
        wchar_t executable[MAX_PATH];GetModuleFileNameW(nullptr,executable,MAX_PATH);
        std::filesystem::path root=std::filesystem::path(executable).parent_path().parent_path();SetCurrentDirectoryW(root.c_str());
        App state;app=&state;std::string args=command;state.vulkan=args.find("--vulkan")!=std::string::npos;state.smoke=args.find("--smoke")!=std::string::npos;state.smokeArena=args.find("--arena")!=std::string::npos;
        if(args.find("--shop")!=std::string::npos)state.screen=Screen::Shop;
        WNDCLASSW wc{};wc.style=CS_OWNDC;wc.lpfnWndProc=window_proc;wc.hInstance=instance;wc.lpszClassName=L"XervexlArenaWindow";wc.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&wc);
        RECT size{0,0,1280,800};AdjustWindowRect(&size,WS_OVERLAPPEDWINDOW,FALSE);
        state.window=CreateWindowW(wc.lpszClassName,L"Xervexl | motlon",WS_OVERLAPPEDWINDOW|WS_VISIBLE,CW_USEDEFAULT,CW_USEDEFAULT,size.right-size.left,size.bottom-size.top,nullptr,nullptr,instance,nullptr);
        if(!state.window)throw std::runtime_error("Cannot create game window");
        state.engine(state.vulkan);state.net.queue("/health");
        if(state.smokeArena)state.play();
        auto previous=std::chrono::steady_clock::now();int frameCount=0;double fpsTotal=0;
        while(state.running){
            MSG message;while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessage(&message);}
            if(IsIconic(state.window)){Sleep(40);continue;}
            auto now=std::chrono::steady_clock::now();float dt=std::chrono::duration<float>(now-previous).count();previous=now;
            state.update(std::min(dt,.1f));if(state.smoke&&fpsTotal+dt>4)state.captureNext=true;state.frame();frameCount++;fpsTotal+=dt;
            if(state.smoke&&fpsTotal>4){
                std::filesystem::create_directories("screenshots");std::string tag=state.vulkan?"vulkan":"opengl";if(state.smokeArena)tag+="-arena";else if(state.screen==Screen::Shop)tag+="-shop";else tag+="-home";
                state.capture("screenshots/"+tag+".bmp");
                json report={{"renderer",state.renderer->name()},{"frames",frameCount},{"seconds",fpsTotal},{"vertices",state.canvas.mesh.size()},{"connected",state.connected},{"player",state.player},{"fighters",state.world.value("fighters",json::array()).size()},{"humans",state.world.value("humans",0)},{"bots",state.world.value("bots",0)},{"error",state.error}};
                std::ofstream("screenshots/"+tag+".json")<<report.dump(2);break;
            }
            auto used=std::chrono::steady_clock::now()-now;if(used<std::chrono::milliseconds(16))std::this_thread::sleep_for(std::chrono::milliseconds(16)-used);
        }
        if(state.locked){ClipCursor(nullptr);ShowCursor(TRUE);}
        bool joined;{std::lock_guard<std::mutex> guard(state.net.mutex);joined=state.net.joined;}
        if(joined){state.net.queue("/arena/leave");Sleep(70);}
        state.renderer.reset();DestroyWindow(state.window);app=nullptr;return 0;
    }catch(const std::exception& error){
        std::ofstream("client-error.log")<<error.what();MessageBoxA(nullptr,error.what(),"Xervexl could not start",MB_OK|MB_ICONERROR);return 1;
    }
}
