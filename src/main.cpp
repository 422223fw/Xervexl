#include "render.hpp"
#include "net.hpp"
#include "scene.hpp"
#include "controls.hpp"
#include "audio.hpp"
#include <windowsx.h>
#include <mmsystem.h>
#include <filesystem>
#include <iomanip>
#include <sstream>

enum class Screen {Home,Auth,Shop,Settings,Help,Leaders,Inventory,Worlds,Modes,Workshop};
struct App {
    HWND window{};int width=1280,height=800;bool running=true,clicked=false,locked=false,vulkan=false;
    float mouseX=0,mouseY=0,yaw=0,pitch=.28f,time=0;int attackMode=0;
    float cameraDistance=5.2f,cameraTarget=5.2f,mouseDX=0,mouseDY=0;std::string guardDir="centre";int inventoryPage=0,inventorySlot=0,worldPage=0;
    bool arena=false,pendingPlay=false,wasDead=false;Screen screen=Screen::Home;
    int authMode=0,focus=-1;std::string fields[7]={"", "", "", "", "http://127.0.0.1:8765","My Arena","on start weapon arming\non kill if head heal 20\non revive score 25\non win score 100"};
    std::string localMessage;float messageUntil=0,damageUntil=0,lastEventTime=-1;
    Network net;Canvas canvas;std::unique_ptr<Renderer> renderer;
    std::map<std::string,Vec> positions;
    std::map<std::string,PoseTransition> poseTracks;VisualCombatClock animationClock;
    json world,profile,catalog,boards,worlds;std::string player,status,error,notice;bool connected=false,busy=false,savedLogin=false,restoringLogin=false;
    float hp=100,maxHp=100,stamina=100,death=0,spawnSafe=0,spellCd=0,healthRegen=0;int kills=0,coins=100,level=1,skill=0;std::string xp="0";
    int shopCategory=0,shopPage=0,leaderTab=0,seenEvent=0;float lastBoards=-10,lastWorlds=-10;std::string aimZone="body",heldWeapon="knife",heldSpell;
    bool automatic=true,switchSmoke=false;int switchStep=0;std::vector<std::string> seenApis;
    bool smoke=false,smokeArena=false;std::string screenshot;
    bool captureNext=false,authSubmitted=false,showHitboxes=false,blocking=false;std::string alignedPlayer,shownGuard="centre";
    CombatControls controls;
    MusicPlayer music;json modes=json::array(),editorProps=json::array();std::string pendingMode,editorId,loadedBlueprint;int modePage=0,editorBiome=0,editorPlayers=20,editorTeam=4,editorKind=0;float editorRadius=1,editorHeight=3,lastModes=-10;bool editorSurvival=true,rightClicked=false,editorSelectAll=false;
    explicit App(const std::string& sessionFile="data/login-session.bin"):net(sessionFile){fields[4]=net.url;try{std::ifstream a("data/audio.json");if(a){json v;a>>v;music.enabled=v.value("enabled",true);music.volume=std::clamp(v.value("volume",.32f),0.f,1.f);}}catch(const std::exception&){}try{std::ifstream file("data/controls.json");if(file){json saved;file>>saved;controls.easy=saved.value("easy",true);}}catch(const std::exception&) {}}
    void control_mode(bool easy){controls.easy=easy;controls.leftWasDown=false;try{std::filesystem::create_directories("data");std::ofstream file("data/controls.json");file<<json{{"easy",easy}}.dump();if(!file)throw std::runtime_error("write");}catch(const std::exception&){toast("Controls changed. Could not save this setting.");}}
    bool authPlayRequested=false;int requestedWorld=-2;
    std::string previewMove;float previewPhase=.18f;
    bool signed_in(){return !profile.empty()&&!profile.value("guest",true);}
    void save_audio(){try{std::filesystem::create_directories("data");std::ofstream out("data/audio.json");out<<json{{"enabled",music.enabled},{"volume",music.volume}};}catch(const std::exception&) {toast("Music changed; could not save this setting.");}}
    void enter_mode(std::string id){pendingMode=id;if(require_sign_in(true,-3))return;pendingMode.clear();net.queue("/modes/join",{{"mode",id},{"biome",editorBiome}});pendingPlay=true;screen=Screen::Home;focus=-1;}
    void switch_slot(int slot){if(!profile.empty())net.queue("/inventory/switch",{{"slot",slot}});}
    bool require_sign_in(bool enter=false,int worldId=-2){
        if(signed_in())return false;
        authPlayRequested=enter;requestedWorld=worldId;pendingPlay=false;
        {std::lock_guard<std::mutex> guard(net.mutex);if(net.restoring||!net.profile.empty()){toast("Restoring your signed-in account...");return true;}}
        screen=Screen::Auth;authMode=1;focus=0;toast("Sign up or sign in to enter the arena.");return true;
    }
    void choose_room(int id=-1){if(require_sign_in(true,id))return;net.queue("/arena/world",id<0?json::object():json{{"world_id",id}});pendingPlay=true;screen=Screen::Home;}

    bool hover(float x,float y,float w,float h){return mouseX>=x&&mouseX<=x+w&&mouseY>=y&&mouseY<=y+h;}
    bool button(float x,float y,float w,float h,const std::string& label,bool primary=false,bool allowBusy=false){
        bool hot=hover(x,y,w,h);Colour fill=primary?(hot?Colour{1,.76f,.39f}:GOLD):(hot?Colour{.17f,.22f,.21f,.97f}:Colour{.10f,.14f,.14f,.94f});
        canvas.rect(x,y,w,h,fill);canvas.border(x,y,w,h,primary?GOLD:Colour{.26f,.32f,.30f});
        canvas.text(x+(w-Canvas::text_width(label,2))/2,y+(h-22)/2,label,2,primary?INK:WHITE);
        return hot&&clicked&&(allowBusy||!busy);
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
        if(require_sign_in(true))return;
        {std::lock_guard<std::mutex> guard(net.mutex);if(net.joined){arena=true;return;}}
        pendingPlay=true;
    }
    void engine(bool useVulkan,bool useAuto=false){
        automatic=useAuto;
        renderer.reset();try{if(useVulkan)renderer=std::make_unique<VulkanRenderer>(window);else renderer=std::make_unique<OpenGLRenderer>(window);vulkan=useVulkan;}
        catch(const std::exception& e){localMessage=std::string("Vulkan unavailable: ")+e.what();messageUntil=time+9;renderer=std::make_unique<OpenGLRenderer>(window);vulkan=false;}
        seenApis.push_back(renderer->name());
    }
    void leaders(){if(require_sign_in())return;net.queue("/leaderboards");lastBoards=time;screen=Screen::Leaders;}
    void snapshot(){
        std::lock_guard<std::mutex> guard(net.mutex);world=net.world;profile=net.profile;catalog=net.catalog;boards=net.boards;worlds=net.worlds;player=net.player;connected=net.connected;busy=net.busy;savedLogin=!net.token.empty();restoringLogin=net.restoring;error=net.error;notice=net.message;net.message.clear();modes=net.modes;if(!net.savedMode.empty()){editorId=net.savedMode;net.savedMode.clear();}if(!net.blueprintId.empty()){editorId=net.blueprintId;auto b=net.blueprint;fields[5]=b["mode"].value("name",std::string{});fields[6]=b.value("code",std::string{});editorProps=b.value("props",json::array());editorBiome=b.value("biome",0);editorPlayers=b["mode"].value("players",20);editorTeam=b["mode"].value("team_size",4);editorSurvival=b["mode"].value("survival",true);net.blueprintId.clear();}
    }
    void update(float dt){
        time+=dt;snapshot();
        if(!notice.empty())toast(notice);
        if(pendingPlay&&!busy){
            bool authed,joined;{std::lock_guard<std::mutex> guard(net.mutex);authed=!net.token.empty();joined=net.joined;}
            if(joined){arena=true;pendingPlay=false;focus=-1;}
            else if(authed&&error.empty())net.queue("/arena/join");
            else if(!error.empty())pendingPlay=false;
        }
        if(screen==Screen::Auth&&authSubmitted&&signed_in()&&authMode<2&&!busy&&error.empty()){screen=Screen::Home;focus=-1;fields[1].clear();authSubmitted=false;toast("Hello, "+profile.value("username",std::string("FIGHTER"))+"! Your equipment and progress are ready.");}
        if(authPlayRequested&&signed_in()&&!busy&&!restoringLogin){authPlayRequested=false;screen=Screen::Home;focus=-1;if(requestedWorld==-3)enter_mode(pendingMode);else if(requestedWorld==-2)play();else choose_room(requestedWorld);}
        if(arena&&player.empty()&&!pendingPlay)arena=false;
        cameraDistance+=(cameraTarget-cameraDistance)*std::min(1.f,dt*12);
        if(!profile.empty()){coins=profile.value("coins",100);kills=profile.value("kills",0);level=profile.value("level",1);skill=profile.value("skill",0);xp=decimal_text(profile,"xp");maxHp=profile.value("max_hp",100.f);}
        if(screen==Screen::Leaders&&time-lastBoards>2&&!busy){net.queue("/leaderboards");lastBoards=time;}
        if(screen==Screen::Worlds&&time-lastWorlds>2&&!busy){net.queue("/servers");lastWorlds=time;}
        if(screen==Screen::Modes&&time-lastModes>2&&!busy){net.queue("/modes");lastModes=time;}
        music.update(arena&&screen==Screen::Home);
        if(switchSmoke&&time>1.1f*(switchStep+1)&&switchStep<3){engine(!vulkan);switchStep++;}
        json self;
        if(world.contains("fighters"))for(auto& f:world["fighters"]){
            std::string id=f.value("id",std::string{});Vec target{f.value("x",0.f),0,f.value("z",0.f)};
            if(!positions.count(id))positions[id]=target;else positions[id]=positions[id]+(target-positions[id])*std::min(1.f,dt*15);
            if(id==player)self=f;
        }
        if(!self.is_null()){
            if(alignedPlayer!=player){yaw=std::atan2(-self.value("x",0.f),-self.value("z",0.f));alignedPlayer=player;seenEvent=0;}
            float current=self.value("hp",100.f);if(current<hp)damageUntil=time+.22f;hp=current;stamina=self.value("stamina",100.f);death=self.value("dead",0.f);
            spawnSafe=self.value("spawn_safe",0.f);healthRegen=self.value("regen_rate",0.f);blocking=self.value("block",false);shownGuard=self.value("guard_dir",std::string("centre"));
            maxHp=self.value("max_hp",100.f);heldWeapon=self.value("weapon",std::string("knife"));heldSpell=self.value("spell",std::string{});spellCd=self.value("spell_cd",0.f);
            if(controls.easy)guardDir=self.value("guard_dir",std::string("centre"));
            if(death>0&&!wasDead)PlaySoundA("assets/fall.wav",nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT);
            wasDead=death>0;
        }
        if(world.contains("events"))for(auto& e:world["events"]){
            int id=e.value("id",0);if(id<=seenEvent)continue;seenEvent=id;std::string kind=e.value("kind",std::string{});
            if((kind=="hit"||kind=="projectile_hit"||kind=="parry"||kind=="deflect"||kind=="disarm")&&(e.value("source",std::string{})==player||e.value("target",std::string{})==player))PlaySoundA("assets/steel.wav",nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT);
            if(kind=="kill"&&e.value("source_id",std::string{})==player)toast("ELIMINATION  +"+std::to_string(e.value("xp",0))+" XP  +"+std::to_string(e.value("skill",0))+" SKILL  +"+std::to_string(e.value("coins",0))+" CROWNS");
            if(kind=="kill"&&e.value("target_id",std::string{})==player)toast("DEFEATED  -"+std::to_string(e.value("lost_skill",0))+" SKILL POINTS");
            if((kind=="parry"&&e.value("target",std::string{})==player)||(kind=="deflect"&&e.value("source",std::string{})==player))toast("PERFECT DEFENCE / XP + SKILL / ZERO STAMINA COST");
            if(kind=="disarm"&&e.value("source",std::string{})==player)toast("DISARM / XP + SKILL EARNED");
            if(kind=="disarm"&&e.value("target",std::string{})==player)toast("WEAPON LOST / SKILL LOST / F TO RECOVER YOUR BLADE");
            if(kind=="grip_hold"&&e.value("target",std::string{})==player)toast("GRIP HELD / WEAPON RETAINED");
            if(kind=="grip_hold"&&e.value("source",std::string{})==player)toast("OPPONENT HELD THEIR GRIP");
            if(kind=="pickup"&&e.value("source",std::string{})==player)toast("PICKED UP: "+item_info(e.value("weapon",std::string("knife"))).value("name",std::string("WEAPON")));
            if(kind=="level"&&e.value("target",std::string{})==player)toast("LEVEL UP! RANK "+std::to_string(e.value("level",1)));
            if(kind=="fall"&&e.value("target",std::string{})==player)toast("KNOCKED DOWN / RECOVERING FOOTING");
        }
        bool foreground=GetForegroundWindow()==window;
        bool capture=arena&&screen==Screen::Home&&foreground&&death<=0;
        if(capture&&!locked){POINT centre{width/2,height/2};ClientToScreen(window,&centre);if(!smoke)SetCursorPos(centre.x,centre.y);ShowCursor(FALSE);locked=true;}
        if(!capture&&locked){ClipCursor(nullptr);ShowCursor(TRUE);locked=false;}
        if(capture){
            POINT centre{width/2,height/2};ClientToScreen(window,&centre);POINT p;GetCursorPos(&p);
            if(!smoke){mouseDX=static_cast<float>(p.x-centre.x);mouseDY=static_cast<float>(p.y-centre.y);yaw+=mouseDX*.0035f;pitch=std::clamp(pitch+mouseDY*.002f,-.85f,1.0f);SetCursorPos(centre.x,centre.y);}
            RECT clip{};GetClientRect(window,&clip);POINT a{clip.left,clip.top},b{clip.right,clip.bottom};ClientToScreen(window,&a);ClientToScreen(window,&b);clip={a.x,a.y,b.x,b.y};ClipCursor(&clip);
        }
        auto key=[&](int k){return capture&&(GetAsyncKeyState(k)&0x8000);};
        if(key('Z'))aimZone="legs";if(key('X'))aimZone="body";if(key('C'))aimZone="head";
        float forward=static_cast<float>(key('W'))-static_cast<float>(key('S'));
        float side=static_cast<float>(key('D'))-static_cast<float>(key('A'));
        CombatKeys keys{forward,side,mouseDX,mouseDY,static_cast<bool>(key(VK_LBUTTON)),static_cast<bool>(key(VK_RBUTTON)),static_cast<bool>(key(VK_MBUTTON)),static_cast<bool>(key('V')),static_cast<bool>(key('Q')),static_cast<bool>(key('R')),static_cast<bool>(key('N')),static_cast<bool>(key('K')),static_cast<bool>(key('U')),static_cast<bool>(key('L'))};
        std::string attack=controls.attack(keys);attackMode=controls.cut;
        guardDir=controls.guard;
        json input={{"move",{std::sin(yaw)*forward+std::cos(yaw)*side,std::cos(yaw)*forward-std::sin(yaw)*side}},
                    {"yaw",yaw},{"attack",attack},{"block",key(VK_RBUTTON)},{"easy_controls",controls.easy},{"auto_cut",controls.primaryAttack},{"debug_hitboxes",showHitboxes},
                    {"dodge",key(VK_SHIFT)},{"jump",key(VK_SPACE)},{"drop",key('G')},{"pickup",key('F')},{"cast",key('B')},
                    {"aim_zone",aimZone},{"aim_pitch",pitch-.28f},{"guard_dir",guardDir},{"revive",key('H')}};
        if(smokeArena){input["move"]={0,0};input["attack"]="";}
        {std::lock_guard<std::mutex> guard(net.mutex);net.input=input;}
    }
    void world_view(){
        canvas.following=arena&&cameraDistance>=.45f;
        if(!previewMove.empty()){
            canvas.set_camera({3,2.45f,4},{0,1.18f,0});environment(canvas,time);
            bool guarding=previewMove.rfind("guard_",0)==0;std::string move=guarding?"":previewMove;
            auto timing=move_timing(move);float windup=timing.windup,duration=timing.duration;
            json f={{"id","pose-preview"},{"x",0},{"z",0},{"body_yaw",0},{"weapon","longsword"},{"attack",move},{"attack_started",0},{"attack_windup",windup},{"attack_duration",duration},{"block",guarding},{"guard_dir",guarding?previewMove.substr(6):"centre"}};
            fighter(canvas,f,previewPhase,true);canvas.flush3();return;
        }
        if(arena&&!player.empty()&&positions.count(player)){
            Vec p=positions[player];
            if(world.contains("fighters"))for(const auto& f:world["fighters"])if(f.value("id",std::string{})==player){float jump=f.value("jump",0.f);if(jump>0)p.y+=std::sin((.55f-jump)/.55f*PI)*.65f;float fall=f.value("fall",0.f);if(fall>0)p.y-=std::min(1.f,fall*4)*.95f;break;}
            if(cameraDistance<.45f){Vec eye=p+Vec{0,1.84f,0};canvas.set_camera(eye,eye+Vec{std::sin(yaw)*std::cos(pitch)*6,-std::sin(pitch)*6,std::cos(yaw)*std::cos(pitch)*6});}
            else {float blend=std::clamp((cameraDistance-.45f)/2.f,0.f,1.f),d=std::max(0.f,cameraDistance-.45f);Vec eye=p+Vec{-std::sin(yaw)*d,1.84f+d*.63f+pitch*2*blend,-std::cos(yaw)*d};float radius=std::hypot(eye.x,eye.z);if(radius>38.5f){eye.x*=38.5f/radius;eye.z*=38.5f/radius;}Vec nearLook=eye+Vec{std::sin(yaw)*std::cos(pitch)*6,-std::sin(pitch)*6,std::cos(yaw)*std::cos(pitch)*6},farLook=p+Vec{std::sin(yaw)*1.2f,1.25f,std::cos(yaw)*1.2f};canvas.set_camera(eye,nearLook*(1-blend)+farLook*blend);}
        }else{
            float a=.52f+std::sin(time*.025f)*.2f;canvas.set_camera({std::sin(a)*9+4,3.0f,std::cos(a)*9},{5.5f,1.15f,0});
        }
        environment(canvas,time,world.value("world",json::object()));
        battlefield_objects(canvas,world,time);
        if(showHitboxes)debug_hitboxes(canvas,world,arena&&cameraDistance<.45f?player:std::string{});
        auto round=world.value("match",json::object());
        if(!round.empty()&&round.value("phase",std::string{})=="playing"){float radius=round.value("zone_radius",38.f);for(int i=0;i<64;i++){float a=i*2*PI/64,b=(i+1)*2*PI/64;canvas.beam({std::sin(a)*radius,.07f,std::cos(a)*radius},{std::sin(b)*radius,.07f,std::cos(b)*radius},.035f,{.32f,.65f,.78f,.80f});}}
        if(world.contains("fighters")){
            float combatTime=animationClock.sample(world.value("time",0.f),time);
            for(auto f:world["fighters"]){std::string id=f.value("id",std::string{});if(positions.count(id)){f["x"]=positions[id].x;f["z"]=positions[id].z;}
                CombatPose visual=poseTracks[id].sample(pose_input(f,combatTime,id==player&&arena&&cameraDistance<.45f),f.value("attack_id",0),time);
                if(f.value("downed",0.f)>0){f["fall"]=.8;f["fall_duration"]=1.25;}
                if(id==player&&arena&&cameraDistance<.45f)first_person_arms(canvas,f,yaw,pitch,combatTime,&visual);else fighter(canvas,f,combatTime,id==player,&visual);}
            std::erase_if(poseTracks,[&](const auto& entry){return time-entry.second.lastSeen>.5f;});
        }else{
            // Clearly visual menu scene, not a fabricated online population.
            json a={{"id","menu-a"},{"x",2.7},{"z",2.0},{"yaw",-1.2},{"weapon","longsword"},{"armour","mail"},{"shield","buckler"}};
            json b={{"id","menu-b"},{"x",-.2},{"z",1.4},{"yaw",1.4},{"weapon","sabre"},{"armour","leather"},{"attack",std::fmod(time,2.4f)<1.2f?"left":"right"},{"attack_started",std::floor(time/1.2f)*1.2f},{"attack_windup",.18f},{"attack_duration",.46f},{"windup",0}};
            fighter(canvas,a,time);fighter(canvas,b,time);
        }
        canvas.flush3();
        if(arena&&!round.empty()&&world.contains("fighters")){
            int team=-1;for(auto& f:world["fighters"])if(f.value("id",std::string{})==player){team=f.value("team",-1);break;}
            for(auto& f:world["fighters"])if(f.value("team",-2)==team&&f.value("id",std::string{})!=player&&f.value("dead",0.f)<=0){float x,y,d;Vec p{f.value("x",0.f),f.value("downed",0.f)>0?1.0f:2.3f,f.value("z",0.f)};if(canvas.project(p,x,y,d)&&x>30&&x<1150&&y>150&&y<640)canvas.text(x,y,(f.value("downed",0.f)>0?"[H] DOWN / ":"ALLY / ")+f.value("name",std::string{}),1.15f,f.value("downed",0.f)>0?GOLD:Colour{.55f,.88f,.72f});}
        }
        auto pickup=world.value("pickup",json::object());
        if(arena&&!pickup.empty()&&world.contains("drops"))for(const auto& d:world["drops"]){
            if(d.value("id",std::string{})!=pickup.value("id",std::string{}))continue;
            float x,y,depth;Vec p{d.value("x",0.f),d.value("y",.06f)+.3f,d.value("z",0.f)};
            if(canvas.project(p,x,y,depth)&&depth<10&&x>90&&x<1190&&y>100&&y<555){
                std::string label=pickup.value("own",false)?"[F] YOUR WEAPON":"[F] PICK UP";float w=Canvas::text_width(label,1.5f)+24;
                canvas.rect(x-w/2,y-9,w,29,{.035f,.055f,.058f,.94f});canvas.text(x-w/2+12,y,label,1.5f,GOLD);
            }
        }
        if(arena&&world.contains("fighters"))for(auto& f:world["fighters"]){
            if(f.value("id",std::string{})==player||f.value("dead",0.f)>0)continue;
            float x,y,d;Vec p{f.value("x",0.f),2.55f,f.value("z",0.f)};
            if(canvas.project(p,x,y,d)&&d<25&&x>40&&x<1240&&y>95&&y<660){
                if(!round.empty()&&(d>10||std::abs(x-640)>180))continue;
                if(!round.empty()){bool ally=false;for(auto& me:world["fighters"])if(me.value("id",std::string{})==player){ally=me.value("team",-1)==f.value("team",-2);break;}if(ally)continue;}
                float s=d<12?1.5f:1.2f;std::string name=f.value("name",std::string("Fighter"));canvas.text(x-name.size()*s*3,y,name,s,WHITE);
                canvas.rect(x-30,y+16,60,4,{.08f,.10f,.10f,.8f});canvas.rect(x-30,y+16,60*f.value("hp",100.f)/f.value("max_hp",100.f),4,f.value("bot",false)?Colour{.82f,.47f,.24f}:Colour{.38f,.70f,.60f});
                canvas.text(x-34,y+25,"LV "+std::to_string(f.value("level",1))+(f.value("bot",false)?" / AI "+std::to_string(f.value("depth",2)):""),1.1f,MUTED);
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
        if(button(640,20,176,43,"LEADERBOARDS"))leaders();
        if(button(830,20,140,43,"ARMOURY"))screen=Screen::Shop;
        if(button(983,20,110,43,"SETTINGS",false,true))screen=Screen::Settings;
        if(button(1106,20,140,43,signed_in()||savedLogin?"LOGOUT":"SIGN IN",false,true)){authPlayRequested=false;if(signed_in()||savedLogin){pendingPlay=false;arena=false;net.logout();profile=json::object();savedLogin=restoringLogin=false;fields[1].clear();}else{screen=Screen::Auth;authMode=0;focus=0;}}
        canvas.text(57,157,"STEEL. SAND. SURVIVAL.",1.9f,GOLD);
        canvas.text(52,215,"XERVEXL",8.2f,WHITE);
        canvas.rect(57,299,88,3,GOLD);
        canvas.text(57,334,"NO CROWN. NO FINAL ROUND.",2.1f,WHITE);
        canvas.text(57,380,"An open arena of blades and nerve.\nRead your opponent. Choose your strike.\nFall, return, and fight again.",1.75f,MUTED);
        if(button(57,483,343,70,restoringLogin?"RESTORING ACCOUNT...":busy?"CONNECTING...":!signed_in()?"SIGN UP TO PLAY":(!player.empty()?"RETURN TO ARENA":"ENTER THE ARENA"),true))play();
        if(button(414,483,142,70,"HOW TO PLAY"))screen=Screen::Help;
        if(button(57,563,240,45,"GAME MODES"))screen=Screen::Modes;if(button(310,563,246,45,"WORLD WORKSHOP"))screen=Screen::Workshop;
        canvas.text(57,616,signed_in()?("HELLO, "+profile.value("username",std::string("FIGHTER"))):restoringLogin?"RECONNECTING TO YOUR SAVED ACCOUNT...":"CREATE YOUR ACCOUNT / ALREADY REGISTERED? SIGN IN",1.35f,signed_in()?GOLD:MUTED);
        canvas.rect(57,631,490,96,{.07f,.10f,.11f,.93f});canvas.border(57,631,490,96,{.19f,.25f,.25f});canvas.rect(57,631,3,96,GOLD);
        canvas.text(77,651,"A BLADE IS ALL YOU NEED",1.7f,GOLD);canvas.text(77,680,"Earn XP, skill and crowns. Build your arsenal.\nBlades, bows, armour and rare arcane weapons.",1.45f,WHITE);
        canvas.rect(930,600,294,125,{.04f,.065f,.067f,.89f});canvas.text(951,619,"100 PLAYERS PER SERVER",1.5f,GOLD);
        canvas.text(951,650,world.value("world",json::object()).value("name",std::string("CHOOSE YOUR NEXT ARENA")),1.45f,WHITE);
        if(button(951,680,251,32,"EXPLORE WORLDS"))screen=Screen::Worlds;
        canvas.rect(0,755,1280,45,{.025f,.043f,.045f,.95f});canvas.circle(34,777,4,connected?Colour{.40f,.72f,.48f}:GOLD);
        canvas.text(48,771,connected?"SERVER CONNECTED":"LOCAL / CONNECT TO START",1.35f,MUTED);
        canvas.text(830,771,std::string(renderer->name())+"  /  ONE GAME  /  V0.9.0",1.35f,MUTED);
    }
    void panel(const std::string& title,const std::string& subtitle){
        canvas.rect(0,0,1280,800,{.02f,.035f,.035f,.72f});canvas.rect(276,102,728,610,{.055f,.079f,.083f,.98f});canvas.border(276,102,728,610,{.27f,.32f,.29f});
        canvas.rect(276,102,728,3,GOLD);canvas.text(314,135,title,3,GOLD);canvas.text(314,171,subtitle,1.35f,MUTED);
        if(button(919,126,48,40,"X")){screen=Screen::Home;focus=-1;authPlayRequested=false;}
    }
    void auth(){
        std::string title=authMode==0?"SIGN IN":authMode==1?"SIGN UP":authMode==2?"RECOVER ACCOUNT":"RESET PASSWORD";
        panel(title,"YOUR ACCOUNT LIVES ON YOUR SELECTED ARENA SERVER");
        if(authMode<2){
            if(button(315,211,176,41,"SIGN IN",authMode==0)){authMode=0;focus=0;}
            if(button(503,211,216,41,"SIGN UP",authMode==1)){authMode=1;focus=0;}
            field(315,282,650,"USERNAME",0);
            field(315,367,650,"PASSWORD (8+ CHARACTERS)",1,true);
            if(authMode==1)field(315,452,650,"EMAIL",2);
            if(button(315,authMode==1?546:465,650,56,busy?"PLEASE WAIT...":authMode==0?"SIGN IN":"SIGN UP",true)){
                net.queue(authMode==0?"/auth/login":"/auth/register",{{"username",fields[0]},{"password",fields[1]},{"email",fields[2]}});
                authSubmitted=true;
            }
            if(authMode==0&&button(315,538,310,40,"FORGOT PASSWORD?")){authMode=2;focus=0;}
            canvas.text(315,637,"A REGISTERED ACCOUNT IS REQUIRED TO PLAY. YOUR PROGRESS IS SAVED.",1.25f,MUTED);
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
#include "menus.inc"
#include "workshop.inc"
    void settings(){
        panel("ARENA SETTINGS","A LOCAL SERVER WORKS NOW. REMOTE SERVERS CAN BE ADDED LATER.");
        field(315,233,650,"SERVER ADDRESS",4);
        if(button(315,321,650,51,"CONNECT TO THIS SERVER",true,true)){
            arena=false;pendingPlay=false;net.queue("/arena/leave");net.server(fields[4]);net.queue("/health");positions.clear();
        }
        canvas.text(315,419,"ONE GAME / BOTH GRAPHICS ENGINES",1.7f,GOLD);
        if(button(315,455,208,52,"AUTO",automatic))engine(true,true);
        if(button(535,455,208,52,"OPENGL",!automatic&&!vulkan))engine(false);
        if(button(755,455,210,52,"VULKAN",!automatic&&vulkan))engine(true);
        canvas.text(315,529,"COMBAT CONTROLS",1.6f,GOLD);
        if(button(315,561,310,45,"EASY",controls.easy))control_mode(true);
        if(button(639,561,326,45,"DIRECTIONAL",!controls.easy))control_mode(false);
        canvas.text(315,628,controls.easy?"Hold left click for cuts. Right click selects a visible guard.\nYou still face the attack and time the block yourself.":"Walking selects cuts; WASD / mouse chooses guard direction.\nClick for each attack. V overhead / middle click thrust.",1.35f,MUTED);
        canvas.text(315,676,"MUSIC",1.4f,MUTED);
        if(button(402,665,133,32,music.enabled?"ON":"OFF")){music.enabled=!music.enabled;save_audio();}
        if(button(550,665,75,32,"-")){music.volume=std::max(0.f,music.volume-.1f);music.set_volume();save_audio();}
        canvas.text(640,674,std::to_string(static_cast<int>(music.volume*100))+"%",1.5f,GOLD);
        if(button(710,665,75,32,"+")){music.volume=std::min(1.f,music.volume+.1f);music.set_volume();save_audio();}
        if(music.failed)canvas.text(803,676,"NO AUDIO DEVICE",1.1f,MUTED);
    }
    void help(){
        panel("READ THE BLADE","AIM, PARRY, DISARM. EARN XP AND BUILD YOUR ARSENAL.");
        std::vector<std::pair<std::string,std::string>> rows={{"W A S D / MOUSE","MOVE / LOOK"},{"LEFT CLICK / RMB",controls.easy?"HOLD TO CUT / BLOCK AND CANCEL":"DIRECTIONAL CUT / MANUAL GUARD"},{"MIDDLE CLICK / V","THRUST / OVERHEAD CUT"},{"Q / R","DISARM / CONTROLLED SPIN"},{"1 - 5 / I","CHANGE WEAPON / OWNED INVENTORY"},{"MOUSE WHEEL","OVERHEAD VIEW THROUGH FIRST PERSON"},{"Z X C / B","AIM LEGS BODY HEAD / CAST SPELL"},{"G F / SHIFT SPACE","DROP PICKUP / DODGE JUMP"},{"E / T / ESC","ARMOURY / SCORES / MENU"},{"SETTINGS",controls.easy?"EASY CONTROLS / CHANGE TO DIRECTIONAL":"DIRECTIONAL CONTROLS / CHANGE TO EASY"}};
        float y=218;for(auto& row:rows){canvas.text(315,y,row.first,1.5f,GOLD);canvas.text(540,y,row.second,1.3f,WHITE);canvas.rect(315,y+23,650,1,{.17f,.23f,.22f});y+=39;}
        canvas.text(315,621,"Face the incoming blade; press block just before impact.\nHolding block does not repeatedly give a perfect parry.\nFace an arrow and block at impact to return it.",1.4f,MUTED);
    }
    void hud(){
        auto match=world.value("match",json::object());json self;int ownTeam=-1;
        if(world.contains("fighters"))for(const auto& f:world["fighters"])if(f.value("id",std::string{})==player){self=f;ownTeam=f.value("team",-1);break;}
        if(!match.empty()){
            canvas.rect(360,90,560,65,{.03f,.06f,.07f,.94f});canvas.text(377,100,match.value("name",std::string{})+" / TEAM "+std::to_string(ownTeam+1),1.7f,GOLD);
            std::string phase=match.value("phase",std::string{});canvas.text(377,128,phase=="playing"?std::to_string(match.value("teams_left",0))+" TEAMS LEFT / "+std::to_string(match.value("alive",0))+" FIGHTERS":phase+" / "+std::to_string(static_cast<int>(match.value("remaining",0.f)))+"S",1.4f,WHITE);
            int row=0;if(world.contains("fighters"))for(const auto& f:world["fighters"])if(f.value("team",-1)==ownTeam&&row<10){float y=180+row*30;canvas.rect(22,y,270,26,{.03f,.05f,.06f,.9f});canvas.text(33,y+4,f.value("name",std::string{})+(f.value("downed",0.f)>0?" / DOWN":f.value("eliminated",false)?" / OUT":""),1.2f,f.value("downed",0.f)>0?GOLD:WHITE);row++;}
            auto revive=world.value("revive",json::object());if(!revive.empty()){canvas.rect(410,563,460,64,{.035f,.07f,.07f,.96f});canvas.text(430,576,"HOLD H TO REVIVE "+revive.value("name",std::string{}),1.6f,GOLD);canvas.rect(430,611,420*revive.value("progress",0.f),4,GOLD);}
            if(!self.is_null()&&self.value("downed",0.f)>0){canvas.rect(380,360,520,100,{.12f,.06f,.035f,.94f});canvas.text(404,380,"DOWNED / WAIT FOR YOUR SQUAD",2,GOLD);canvas.text(404,423,"BLEEDING OUT IN "+std::to_string(static_cast<int>(self.value("downed",0.f)))+"S",1.6f,WHITE);}
            if(!match.value("ranked",true)&&!self.is_null())canvas.text(370,165,"MOD SCORE "+std::to_string(self.value("match_score",0))+" / XP "+std::to_string(self.value("match_xp",0))+" / CROWNS "+std::to_string(self.value("match_coins",0)),1.3f,GOLD);
            if(phase=="finished"){canvas.rect(380,330,520,150,{.04f,.08f,.07f,.96f});bool won=match.value("winner",-2)==ownTeam;canvas.text(408,351,won?"YOUR SQUAD WINS":"ROUND COMPLETE",3,GOLD);canvas.text(408,408,won&&match.value("ranked",false)?"+650 XP / +350 CROWNS / +25 SKILL":"NEXT ROUND STARTS SHORTLY",1.6f,WHITE);}
        }
        canvas.rect(22,20,440,67,{.035f,.055f,.058f,.89f});emblem(53,52,33);canvas.text(80,34,"XERVEXL",2.2f,GOLD);
        canvas.text(80,61,"RANK "+std::to_string(level)+" / "+std::to_string(skill)+" SKILL / "+compact_decimal(decimal_text(profile,"level_progress_xp"))+" / "+compact_decimal(decimal_text(profile,"level_cost_xp","79"))+" XP",1.15f,MUTED);
        canvas.rect(997,20,261,67,{.035f,.055f,.058f,.89f});
        auto room=world.value("world",json::object());canvas.text(1013,35,"SERVER "+std::to_string(room.value("server_number",1))+" / "+std::to_string(world.value("humans",0))+" / 100",1.4f,WHITE);canvas.text(1013,61,std::string(renderer->name())+" / "+std::to_string(world.value("bots",0))+" BOTS",1.15f,GOLD);
        canvas.line(634,400,646,400,1.3f,{1,1,1,.6f});canvas.line(640,394,640,406,1.3f,{1,1,1,.6f});
        if(showHitboxes)canvas.text(28,101,"F3 / SERVER HITBOXES / CYAN: GUARD BLADE",1.2f,GOLD);
        if(spawnSafe>0){canvas.rect(443,145,394,44,{.035f,.055f,.058f,.89f});canvas.text(463,158,"SAFE ENTRY / DAMAGE STARTS SHORTLY",1.55f,GOLD);}
        auto pickup=world.value("pickup",json::object());
        if(!pickup.empty()&&death<=0){
            std::string name=item_info(pickup.value("weapon",std::string("knife"))).value("name",std::string("WEAPON"));
            canvas.rect(424,565,432,53,{.035f,.055f,.058f,.96f});canvas.border(424,565,432,53,GOLD);
            canvas.text(440,576,std::string(pickup.value("ready",false)?"HOLD F: ":"RECOVERING / HOLD F: ")+(pickup.value("own",false)?"YOUR ":"")+name,1.3f,GOLD);
            canvas.text(440,598,heldWeapon=="fists"?"PICK UP AND EQUIP YOUR BLADE":"PICK UP / CURRENT WEAPON DROPS",1.05f,MUTED);
        }
        canvas.rect(28,657,370,112,{.035f,.055f,.058f,.94f});canvas.text(47,673,profile.value("username",std::string("FIGHTER")),1.6f,WHITE);
        canvas.text(47,701,healthRegen>0?"REGEN +2":"HEALTH",1.1f,healthRegen>0?Colour{.44f,.80f,.49f}:MUTED);canvas.rect(132,700,239,12,{.16f,.20f,.18f});canvas.rect(132,700,239*hp/maxHp,12,healthRegen>0?Colour{.31f,.64f,.38f}:Colour{.62f,.26f,.19f});canvas.text(263,672,std::to_string(static_cast<int>(hp))+" / "+std::to_string(static_cast<int>(maxHp)),1.2f,MUTED);
        canvas.text(47,728,"STAMINA",1.1f,MUTED);canvas.rect(132,727,239,9,{.16f,.20f,.18f});canvas.rect(132,727,239*stamina/100,9,GOLD);
        canvas.text(47,752,std::to_string(kills)+" ELIMINATIONS / "+std::to_string(coins)+" CROWNS",1.15f,MUTED);
        json slots=profile.value("weapon_slots",json::array({"knife","","","",""}));
        for(int i=0;i<5;i++){float x=450+i*119;std::string id=i<static_cast<int>(slots.size())?slots[i].get<std::string>():"";bool active=id==heldWeapon&&!id.empty();canvas.rect(x,714,112,54,active?Colour{.38f,.28f,.16f,.94f}:Colour{.04f,.07f,.075f,.90f});canvas.border(x,714,112,54,active?GOLD:Colour{.20f,.27f,.25f});canvas.text(x+10,723,std::to_string(i+1),1.4f,GOLD);canvas.text(x+10,748,id.empty()?"EMPTY":id.substr(0,13),1.05f,WHITE);}
        auto info=item_info(heldWeapon);std::string weaponLabel=heldWeapon=="fists"?"BARE HANDS / F: RECOVER":info.value("name",heldWeapon);canvas.text(450,648,weaponLabel+" / AIM: "+aimZone+" [Z X C]",1.3f,GOLD);
        const char* moveNames[]={"LEFT CUT","RIGHT CUT","OVERHEAD","THRUST"};canvas.text(450,677,blocking?"GUARD: "+shownGuard+" / MOUSE OR A D W S":controls.easy?std::string("MOVE: ")+moveNames[attackMode]+" / HOLD LMB / RMB: BLOCK":std::string("MOVE: ")+moveNames[attackMode]+" / GUARD: "+guardDir,1.2f,blocking?Colour{.4f,.85f,.95f}:MUTED);canvas.text(450,695,"N RISING / K REVERSE SPIN / U POMMEL / L FEINT",1.05f,MUTED);canvas.text(1100,709,"E ARMOURY\nT SCORES\nESC MENU",1.2f,MUTED);
        if(!heldSpell.empty())canvas.text(450,622,"B: "+heldSpell+(spellCd>0?" / "+std::to_string(static_cast<int>(std::ceil(spellCd)))+"S":" / READY"),1.3f,{.46f,.74f,.92f});
        float progress=profile.value("xp_progress",0.f);canvas.rect(450,781,589,5,{.16f,.20f,.18f});canvas.rect(450,781,589*std::clamp(progress,0.f,1.f),5,GOLD);
        if(world.contains("events")){float y=106;for(auto& e:world["events"])if(e.value("kind",std::string{})=="kill"&&world.value("time",0.f)-e.value("time",0.f)<8){std::string label=e.value("source",std::string{})+"  /  "+e.value("target",std::string{});canvas.rect(961,y-7,296,26,{.04f,.06f,.06f,.72f});canvas.text(974,y,label,1.2f,MUTED);y+=32;}}
        if(death>0&&match.empty()){canvas.rect(0,0,1280,800,{.05f,.025f,.02f,.6f});canvas.text(415,315,"YOU FELL",5,GOLD);canvas.text(427,385,"BACK IN "+std::to_string(static_cast<int>(std::ceil(death)))+" SECONDS",2.1f,WHITE);canvas.text(418,430,"THE ARENA HAS NO FINAL ROUND.",1.6f,MUTED);}
        if(death>0&&!match.empty()&&match.value("phase",std::string{})!="finished")canvas.text(425,390,"ELIMINATED / YOUR SQUAD CAN STILL WIN",1.8f,GOLD);
        if(time<damageUntil){canvas.rect(0,0,1280,24,{.65f,.10f,.045f,.5f});canvas.rect(0,776,1280,24,{.65f,.10f,.045f,.5f});canvas.rect(0,0,24,800,{.65f,.10f,.045f,.5f});canvas.rect(1256,0,24,800,{.65f,.10f,.045f,.5f});}
    }
    void frame(){
        canvas.begin(width,height);world_view();
        if(!previewMove.empty()){canvas.rect(30,25,620,69,{.035f,.055f,.06f,.92f});canvas.text(46,38,"MOVEMENT PREVIEW / "+previewMove,2,GOLD);canvas.text(46,69,"VISUAL MANNEQUIN / NO ARENA SESSION",1.25f,MUTED);}else if(arena&&screen==Screen::Home)hud();else{
            if(screen==Screen::Home)home();else if(screen==Screen::Auth)auth();else if(screen==Screen::Shop)shop();else if(screen==Screen::Settings)settings();else if(screen==Screen::Leaders)leaderboard_view();else if(screen==Screen::Inventory)inventory_view();else if(screen==Screen::Worlds)worlds_view();else if(screen==Screen::Modes)modes_view();else if(screen==Screen::Workshop)workshop_view();else help();
        }
        std::string value=!error.empty()?error:time<messageUntil?localMessage:std::string{};
        if(!value.empty()){
            if(value.size()>100)value=value.substr(0,100);
            float noticeY=arena?(world.value("match",json::object()).empty()?114.f:495.f):92.f;
            canvas.rect(30,noticeY,1220,35,{.08f,.105f,.105f,.98f});canvas.text(44,noticeY+12,value,1.5f,!error.empty()?Colour{1,.55f,.32f}:GOLD);
        }
        renderer->captureRequested=captureNext;renderer->draw(canvas.mesh,width,height);clicked=false;rightClicked=false;
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
    if(!app)return DefWindowProcW(w,msg,wp,lp);
    switch(msg){
        case WM_CLOSE:app->running=false;return 0;
        case WM_SIZE:app->width=std::max(1,static_cast<int>(LOWORD(lp)));app->height=std::max(1,static_cast<int>(HIWORD(lp)));return 0;
        case WM_MOUSEMOVE:app->mouseX=GET_X_LPARAM(lp)*1280.f/app->width;app->mouseY=GET_Y_LPARAM(lp)*800.f/app->height;return 0;
        case WM_LBUTTONDOWN:app->clicked=true;return 0;
        case WM_RBUTTONDOWN:app->rightClicked=true;return 0;
        case WM_MOUSEWHEEL:if(app->arena&&app->screen==Screen::Home)app->cameraTarget=std::clamp(app->cameraTarget-GET_WHEEL_DELTA_WPARAM(wp)/120.f*.9f,0.f,14.f);return 0;
        case WM_KEYDOWN:
            if(app->focus==6&&(GetKeyState(VK_CONTROL)&0x8000)){
                if(wp=='A'){app->editorSelectAll=true;return 0;}
                if(wp=='V'&&OpenClipboard(w)){
                    HANDLE handle=GetClipboardData(CF_UNICODETEXT);if(handle){auto data=static_cast<const wchar_t*>(GlobalLock(handle));if(data){if(app->editorSelectAll)app->fields[6].clear();app->editorSelectAll=false;for(size_t i=0;data[i]&&i<4096&&app->fields[6].size()<4096;i++)if(data[i]=='\n'||(data[i]>=32&&data[i]<127))app->fields[6]+=static_cast<char>(data[i]);GlobalUnlock(handle);}}CloseClipboard();return 0;
                }
            }
            if(wp==VK_ESCAPE&&!(lp&(1<<30))){if(app->screen!=Screen::Home){app->screen=Screen::Home;app->focus=-1;app->authPlayRequested=false;}else app->arena=!app->arena&& !app->player.empty();}
            if(wp=='E'&&app->arena&&app->focus<0&&!(lp&(1<<30)))app->screen=app->screen==Screen::Shop?Screen::Home:Screen::Shop;
            if(wp=='T'&&app->focus<0&&app->screen!=Screen::Auth&&app->screen!=Screen::Settings&&!(lp&(1<<30)))app->leaders();
            if(wp=='I'&&app->focus<0&&app->screen!=Screen::Auth&&app->screen!=Screen::Settings&&!(lp&(1<<30)))app->screen=app->screen==Screen::Inventory?Screen::Home:Screen::Inventory;
            if(wp>='1'&&wp<='5'&&app->arena&&app->screen==Screen::Home&&!(lp&(1<<30)))app->switch_slot(static_cast<int>(wp-'1'));
            if(wp==VK_TAB&&app->screen==Screen::Auth){app->focus=(app->focus+1)%(app->authMode==1?3:2);}
            if(wp==VK_F3&&!(lp&(1<<30))){app->showHitboxes=!app->showHitboxes;app->toast(app->showHitboxes?"HITBOXES ON / HEAD BODY LIMBS AND BLADE":"HITBOXES OFF");}
            if(wp==VK_F12){std::filesystem::create_directories("screenshots");app->captureNext=true;app->screenshot="screenshots/capture.bmp";app->toast("Screenshot saved in screenshots/capture.bmp");}
            return 0;
        case WM_CHAR:
            if(app->focus>=0){std::string& text=app->fields[app->focus];if(app->focus==6&&app->editorSelectAll&&(wp==8||wp==13||(wp>=32&&wp<127))){text.clear();app->editorSelectAll=false;}if(wp==8&&!text.empty())text.pop_back();else if(wp==13&&app->focus==6&&text.size()<4096)text+='\n';else if(wp>=32&&wp<127&&text.size()<(app->focus==6?4096:254))text+=static_cast<char>(wp);}
            return 0;
        default:return DefWindowProcW(w,msg,wp,lp);
    }
}

int WINAPI WinMain(HINSTANCE instance,HINSTANCE,LPSTR command,int){
    try{
        wchar_t executable[MAX_PATH];GetModuleFileNameW(nullptr,executable,MAX_PATH);
        std::filesystem::path root=std::filesystem::path(executable).parent_path().parent_path();SetCurrentDirectoryW(root.c_str());
        std::string args=command,sessionFile="data/login-session.bin";
        if(auto pos=args.find("--session-file=");pos!=std::string::npos){size_t start=pos+15,end=args.find(' ',start);sessionFile=args.substr(start,end==std::string::npos?end:end-start);}
        App state(sessionFile);app=&state;state.vulkan=args.find("--opengl")==std::string::npos;state.smoke=args.find("--smoke")!=std::string::npos;state.smokeArena=args.find("--arena")!=std::string::npos;state.switchSmoke=args.find("--switch")!=std::string::npos;
        if(args.find("--shop")!=std::string::npos)state.screen=Screen::Shop;
        if(args.find("--ranged")!=std::string::npos)state.shopCategory=1;
        if(args.find("--defence")!=std::string::npos)state.shopCategory=2;
        if(args.find("--arcane")!=std::string::npos)state.shopCategory=3;
        if(args.find("--health")!=std::string::npos)state.shopCategory=4;
        if(args.find("--inventory")!=std::string::npos)state.screen=Screen::Inventory;
        if(args.find("--worlds")!=std::string::npos)state.screen=Screen::Worlds;
        if(args.find("--modes")!=std::string::npos)state.screen=Screen::Modes;
        if(args.find("--workshop")!=std::string::npos)state.screen=Screen::Workshop;
        if(args.find("--first-person")!=std::string::npos)state.cameraDistance=state.cameraTarget=0;
        if(args.find("--overhead")!=std::string::npos)state.cameraDistance=state.cameraTarget=14;
        if(auto pos=args.find("--preview-move=");pos!=std::string::npos){size_t start=pos+15,end=args.find(' ',start);state.previewMove=args.substr(start,end==std::string::npos?end:end-start);}
        if(auto pos=args.find("--preview-phase=");pos!=std::string::npos)state.previewPhase=std::stof(args.substr(pos+16));
        if(auto pos=args.find("--server=");pos!=std::string::npos){size_t start=pos+9,end=args.find(' ',start);state.fields[4]=args.substr(start,end==std::string::npos?end:end-start);state.net.server(state.fields[4]);}
        WNDCLASSW wc{};wc.style=CS_OWNDC;wc.lpfnWndProc=window_proc;wc.hInstance=instance;wc.lpszClassName=L"XervexlArenaWindow";wc.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&wc);
        RECT size{0,0,1280,800};AdjustWindowRect(&size,WS_OVERLAPPEDWINDOW,FALSE);
        state.window=CreateWindowW(wc.lpszClassName,L"Xervexl | motlon",WS_OVERLAPPEDWINDOW|WS_VISIBLE,CW_USEDEFAULT,CW_USEDEFAULT,size.right-size.left,size.bottom-size.top,nullptr,nullptr,instance,nullptr);
        if(!state.window)throw std::runtime_error("Cannot create game window");
        SetWindowTextW(state.window,L"Xervexl | motlon");ShowWindow(state.window,SW_SHOWNORMAL);UpdateWindow(state.window);
        state.engine(state.vulkan,args.find("--opengl")==std::string::npos&&args.find("--vulkan")==std::string::npos);state.net.queue("/health");
        if(args.find("--leaders")!=std::string::npos)state.leaders();
        if(auto pos=args.find("--world=");pos!=std::string::npos)state.choose_room(std::stoi(args.substr(pos+8)));else if(state.smokeArena)state.play();
        auto previous=std::chrono::steady_clock::now();int frameCount=0;double fpsTotal=0;
        while(state.running){
            MSG message;while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessage(&message);}
            if(IsIconic(state.window)){Sleep(40);continue;}
            auto now=std::chrono::steady_clock::now();float dt=std::chrono::duration<float>(now-previous).count();previous=now;
            state.update(std::min(dt,.1f));if(state.smoke&&fpsTotal+dt>4)state.captureNext=true;state.frame();frameCount++;fpsTotal+=dt;
            if(state.smoke&&fpsTotal>4){
                std::filesystem::create_directories("screenshots");std::string tag=state.switchSmoke?"combined":state.vulkan?"vulkan":"opengl";if(!state.previewMove.empty())tag+="-pose-"+state.previewMove;else if(state.screen==Screen::Auth)tag+="-auth";else if(state.smokeArena)tag+=state.cameraTarget<.45f?"-first-person":state.cameraTarget>12?"-overhead":"-arena";else if(state.screen==Screen::Shop)tag+="-shop";else if(state.screen==Screen::Leaders)tag+="-leaders";else if(state.screen==Screen::Inventory)tag+="-inventory";else if(state.screen==Screen::Worlds)tag+="-worlds";else tag+="-home";
                state.capture("screenshots/"+tag+".bmp");
                json report={{"renderer",state.renderer->name()},{"frames",frameCount},{"seconds",fpsTotal},{"vertices",state.canvas.mesh.size()},{"connected",state.connected},{"player",state.player},{"fighters",state.world.value("fighters",json::array()).size()},{"humans",state.world.value("humans",0)},{"bots",state.world.value("bots",0)},{"error",state.error}};
                report["graphics_engines_used"]=state.seenApis;report["catalog_items"]=state.catalog.size();report["rank"]=state.level;report["skill"]=state.skill;report["xp"]=state.xp;
                report["camera_distance"]=state.cameraDistance;report["world"]=state.world.value("world",json::object()).value("name",std::string{});report["signed_in"]=state.signed_in();report["weapon_slots"]=state.profile.value("weapon_slots",json::array());
                report["signup_screen"]=state.screen==Screen::Auth&&state.authMode==1;report["xp_to_next"]=decimal_text(state.profile,"xp_to_next","79");
                std::ofstream("screenshots/"+tag+".json")<<report.dump(2);Sleep(500);break;
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
