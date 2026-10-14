#pragma once
#include <winhttp.h>
#include <atomic>
#include <thread>
#include <mutex>
#include <deque>
#include <chrono>
#include "json.hpp"
using json=nlohmann::json;
inline std::string decimal_text(const json& obj,const std::string& key,const std::string& fallback="0"){
    auto it=obj.find(key);if(it==obj.end())return fallback;if(it->is_string())return it->get<std::string>();if(it->is_number())return it->dump();return fallback;
}
inline std::string compact_decimal(const std::string& value){return value.size()<=10?value:value.substr(0,1)+"."+value.substr(1,2)+"e"+std::to_string(value.size()-1);}

struct Network {
    struct Task { std::string route;json body; };
    std::mutex mutex;std::deque<Task> tasks;
    json world=json::object(),profile=json::object(),input=json::object(),catalog=json::array(),boards=json::object(),worlds=json::array();
    std::string url="http://127.0.0.1:8765",token,error,message,player;
    std::atomic<bool> running{true};bool connected=false,joined=false,busy=false;
    std::thread worker;
    Network(){worker=std::thread([this]{run();});}
    ~Network(){running=false;if(worker.joinable())worker.join();}
    void queue(const std::string& route,const json& body=json::object()){
        std::lock_guard<std::mutex> guard(mutex);tasks.push_back({route,body});busy=true;error.clear();message.clear();
    }
    void server(const std::string& address){
        std::lock_guard<std::mutex> guard(mutex);url=address;token.clear();player.clear();world=json::object();profile=json::object();catalog=json::array();boards=json::object();joined=false;connected=false;tasks.clear();error.clear();message="Server address updated.";
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
        while(running){
            Task task;std::string base,auth;bool work=false;
            {
                std::lock_guard<std::mutex> guard(mutex);base=url;auth=token;
                if(!tasks.empty()){task=tasks.front();tasks.pop_front();work=true;}
                else if(joined&&std::chrono::steady_clock::now()-last>std::chrono::milliseconds(45)){task={"/arena/state",input};work=true;last=std::chrono::steady_clock::now();}
            }
            if(work){
                try{
                    auto result=request(base,task.route,task.body,auth);
                    if(result.contains("token")&&!auth.empty()){
                        try{request(base,"/arena/leave",json::object(),auth);}catch(const std::exception&){}
                    }
                    std::lock_guard<std::mutex> guard(mutex);
                    if(base!=url)continue;
                    if(result.contains("error")){error=result["error"].get<std::string>();busy=!tasks.empty();}
                    else{
                        if(task.route!="/arena/state"||!connected)error.clear();connected=true;
                        if(result.contains("token")){token=result["token"].get<std::string>();joined=false;player.clear();world=json::object();}
                        if(result.contains("profile"))profile=result["profile"];
                        if(result.contains("catalog"))catalog=result["catalog"];
                        if(result.contains("worlds"))worlds=result["worlds"];
                        if(result.contains("leaderboards"))boards=result["leaderboards"];
                        if(result.contains("player"))player=result["player"].get<std::string>();
                        if(result.contains("fighters"))world=result;
                        if(result.contains("message"))message=result["message"].get<std::string>();
                        if(task.route=="/arena/join")joined=true;
                        if(task.route=="/arena/world")joined=true;
                        if(task.route=="/arena/leave")joined=false;
                        if(result.value("logged_out",false)){token.clear();player.clear();profile=json::object();world=json::object();boards=json::object();joined=false;}
                        busy=!tasks.empty();
                    }
                }catch(const std::exception& e){
                    std::lock_guard<std::mutex> guard(mutex);if(base==url){error=e.what();connected=false;busy=!tasks.empty();}
                    std::this_thread::sleep_for(std::chrono::milliseconds(120));
                }
            }else std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
};
