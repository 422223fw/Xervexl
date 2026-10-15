#pragma once
#include <winhttp.h>
#include <atomic>
#include <thread>
#include <mutex>
#include <deque>
#include <chrono>
#include "json.hpp"
#include "login_store.hpp"
using json=nlohmann::json;
inline std::string decimal_text(const json& obj,const std::string& key,const std::string& fallback="0"){
    auto it=obj.find(key);if(it==obj.end())return fallback;if(it->is_string())return it->get<std::string>();if(it->is_number())return it->dump();return fallback;
}
inline std::string compact_decimal(const std::string& value){return value.size()<=10?value:value.substr(0,1)+"."+value.substr(1,2)+"e"+std::to_string(value.size()-1);}

struct Network {
    struct Task { std::string route;json body;std::string authOverride,baseOverride; };
    std::mutex mutex;std::deque<Task> tasks;
    json world=json::object(),profile=json::object(),input=json::object(),catalog=json::array(),boards=json::object(),worlds=json::array();
    json modes=json::array(),blueprint=json::object();std::string savedMode,blueprintId;
    std::string url="http://127.0.0.1:8765",token,error,message,player;
    std::atomic<bool> running{true};bool connected=false,joined=false,busy=false,restoring=false;
    unsigned generation=0;
    LoginStore loginStore;
    std::thread worker;
    explicit Network(const std::string& sessionFile="data/login-session.bin"):loginStore(sessionFile){url=loginStore.last_server();token=loginStore.token(url);restoring=!token.empty();worker=std::thread([this]{run();});}
    ~Network(){running=false;if(worker.joinable())worker.join();}
    void queue(const std::string& route,const json& body=json::object()){
        std::lock_guard<std::mutex> guard(mutex);tasks.push_back({route,body});busy=true;error.clear();message.clear();
    }
    void server(const std::string& address){
        std::lock_guard<std::mutex> guard(mutex);auto oldBase=url,oldToken=token;bool wasJoined=joined;
        url=LoginStore::address(address);generation++;player.clear();world=json::object();profile=json::object();catalog=json::array();boards=json::object();joined=false;connected=false;tasks.clear();error.clear();message="Server address updated.";
        try{loginStore.select(url);}catch(const std::exception&){message="Server selected. Could not save this setting.";}
        token=loginStore.token(url);restoring=!token.empty();busy=false;
        if(wasJoined&&!oldToken.empty())tasks.push_back({"/arena/leave",json::object(),oldToken,oldBase});
    }
    void logout(){
        std::lock_guard<std::mutex> guard(mutex);auto previous=token;generation++;tasks.clear();token.clear();profile=json::object();world=json::object();boards=json::object();player.clear();joined=false;restoring=false;error.clear();busy=false;message="Logged out. Your progress is saved.";
        if(!previous.empty()){
            try{loginStore.logout(url,previous);}catch(const std::exception&){
                // Remove a stale cache if writing the pending revocation failed.
                if(!DeleteFileW(loginStore.path.c_str())&&GetLastError()!=ERROR_FILE_NOT_FOUND)message="Logged out here. Could not remove the saved sign-in file.";
            }
            tasks.push_back({"/auth/logout",json::object(),previous,url});busy=true;
        }
    }
    static std::wstring wide(const std::string& value){
        int n=MultiByteToWideChar(CP_UTF8,0,value.c_str(),static_cast<int>(value.size()),nullptr,0);
        std::wstring out(n,0);MultiByteToWideChar(CP_UTF8,0,value.c_str(),static_cast<int>(value.size()),out.data(),n);return out;
    }
    json request(const std::string& base,const std::string& route,const json& body,const std::string& auth){
        std::wstring address=wide(base+route);URL_COMPONENTS parts{};parts.dwStructSize=sizeof(parts);parts.dwHostNameLength=DWORD(-1);parts.dwUrlPathLength=DWORD(-1);
        if(!WinHttpCrackUrl(address.c_str(),0,0,&parts))throw std::runtime_error("Invalid server URL. Use http://host:8765 or HTTPS.");
        if(parts.nScheme!=INTERNET_SCHEME_HTTP&&parts.nScheme!=INTERNET_SCHEME_HTTPS)throw std::runtime_error("Server URL must use HTTP or HTTPS.");
        HINTERNET session=WinHttpOpen(L"Xervexl/0.1",WINHTTP_ACCESS_TYPE_NO_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0);
        if(!session)throw std::runtime_error("Network unavailable");
        WinHttpSetTimeouts(session,1800,1800,1800,1800);
        std::wstring host(parts.lpszHostName,parts.dwHostNameLength),path(parts.lpszUrlPath,parts.dwUrlPathLength);
        HINTERNET connection=WinHttpConnect(session,host.c_str(),parts.nPort,0);
        HINTERNET req=connection?WinHttpOpenRequest(connection,L"POST",path.c_str(),nullptr,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,parts.nScheme==INTERNET_SCHEME_HTTPS?WINHTTP_FLAG_SECURE:0):nullptr;
        std::string payload=body.dump();std::wstring headers=L"Content-Type: application/json\r\n";
        if(!auth.empty())headers+=L"Authorization: Bearer "+wide(auth)+L"\r\n";
        std::string response;bool ok=false;
        if(req&&WinHttpSendRequest(req,headers.c_str(),static_cast<DWORD>(headers.size()),payload.data(),static_cast<DWORD>(payload.size()),static_cast<DWORD>(payload.size()),0)&&WinHttpReceiveResponse(req,nullptr)){
            DWORD available=0;ok=true;
            while(WinHttpQueryDataAvailable(req,&available)&&available){
                if(response.size()+available>4*1024*1024){ok=false;break;}
                size_t offset=response.size();response.resize(offset+available);DWORD read=0;
                if(!WinHttpReadData(req,response.data()+offset,available,&read)){ok=false;break;}response.resize(offset+read);
            }
        }
        if(req)WinHttpCloseHandle(req);if(connection)WinHttpCloseHandle(connection);WinHttpCloseHandle(session);
        if(!ok)throw std::runtime_error("Cannot reach arena server. Start the local server or check the address.");
        return json::parse(response);
    }
    void run(){
        auto last=std::chrono::steady_clock::now();
        auto retry=last;auto logoutRetry=last;
        while(running){
            Task task;std::string base,auth;bool work=false;unsigned epoch=0;
            {
                std::lock_guard<std::mutex> guard(mutex);base=url;auth=token;epoch=generation;
                auto now=std::chrono::steady_clock::now();
                if(!tasks.empty()){task=tasks.front();tasks.pop_front();work=true;}
                else if(!loginStore.pending(url).empty()&&now>=logoutRetry){task={"/auth/logout",json::object(),loginStore.pending(url),url};work=true;logoutRetry=now+std::chrono::seconds(3);}
                else if(restoring&&now>=retry){task={"/auth/resume",json::object()};work=true;retry=now+std::chrono::seconds(2);}
                else if(joined&&now-last>std::chrono::milliseconds(45)){task={"/arena/state",input};work=true;last=now;}
                if(!task.authOverride.empty())auth=task.authOverride;if(!task.baseOverride.empty())base=task.baseOverride;
            }
            if(work){
                try{
                    auto result=request(base,task.route,task.body,auth);
                    std::unique_lock<std::mutex> guard(mutex);
                    if(task.route=="/auth/logout"&&!task.authOverride.empty()){
                        if(result.value("logged_out",false)||result.value("code",std::string{})=="auth_required"){
                            try{loginStore.acknowledge(base,auth);}catch(const std::exception&){message="Logged out. Saved logout cleanup will be retried.";}
                        }
                        busy=!tasks.empty();continue;
                    }
                    if(!task.baseOverride.empty()){busy=!tasks.empty();continue;}
                    if(base!=url||epoch!=generation){
                        if(result.contains("token")){auto abandoned=result["token"].get<std::string>();guard.unlock();try{request(base,"/auth/logout",json::object(),abandoned);}catch(const std::exception&) {}}
                        continue;
                    }
                    if(result.contains("error")){
                        error=result["error"].get<std::string>();busy=!tasks.empty();
                        if(result.value("code",std::string{})=="auth_required"&&auth==token){
                            try{loginStore.forget(base,auth);}catch(const std::exception&){}
                            token.clear();profile=json::object();player.clear();world=json::object();boards=json::object();joined=false;restoring=false;
                        }
                    }
                    else{
                        if(task.route!="/arena/state"||!connected)error.clear();connected=true;
                        if(result.contains("token")){
                            auto fresh=result["token"].get<std::string>();
                            try{if(!auth.empty()&&auth!=fresh)loginStore.logout(base,auth);loginStore.remember(base,fresh);}catch(const std::exception&){message="Signed in. Could not save sign-in on this computer.";}
                            token=fresh;restoring=false;joined=false;player.clear();world=json::object();
                        }
                        if(task.route=="/auth/resume")restoring=false;
                        if(result.contains("profile"))profile=result["profile"];
                        if(result.contains("catalog"))catalog=result["catalog"];
                        if(result.contains("worlds"))worlds=result["worlds"];
                        if(result.contains("modes"))modes=result["modes"];
                        if(result.contains("saved_mode"))savedMode=result["saved_mode"].get<std::string>();
                        if(result.contains("blueprint")){blueprint=result["blueprint"];blueprintId=result.value("blueprint_id",std::string{});}
                        if(result.contains("leaderboards"))boards=result["leaderboards"];
                        if(result.contains("player"))player=result["player"].get<std::string>();
                        if(result.contains("fighters"))world=result;
                        if(result.contains("message"))message=result["message"].get<std::string>();
                        if(task.route=="/arena/join")joined=true;
                        if(task.route=="/arena/world")joined=true;
                        if(task.route=="/modes/join")joined=true;
                        if(task.route=="/arena/leave")joined=false;
                        if(task.route=="/arena/state"&&joined&&player.empty()){
                            // An inactive/other-device avatar can disappear while sign-in stays valid.
                            joined=false;
                        }
                        busy=!tasks.empty();
                    }
                }catch(const std::exception& e){
                    std::lock_guard<std::mutex> guard(mutex);if(base==url&&epoch==generation){error=e.what();connected=false;busy=!tasks.empty();}
                    std::this_thread::sleep_for(std::chrono::milliseconds(120));
                }
            }else std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
};
