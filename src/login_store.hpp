#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <wincrypt.h>
#include <filesystem>
#include <fstream>
#include <chrono>
#include <thread>
#include <string>
#include <vector>
#include "json.hpp"

// DPAPI uses the current Windows user's protection; no password is saved here.
struct LoginStore {
    using Json=nlohmann::json;
    std::filesystem::path path;
    Json data;
    bool unreadable=false;
    explicit LoginStore(const std::string& file):path(file){load();}
    static std::string address(std::string value){while(!value.empty()&&value.back()=='/')value.pop_back();return value;}
    void load(){
        data={{"version",1},{"last_server","http://127.0.0.1:8765"},{"tokens",Json::object()},{"pending_logout",Json::object()}};
        unreadable=false;
        if(!std::filesystem::exists(path))return;
        try{
            auto size=std::filesystem::file_size(path);if(size==0||size>4*1024*1024)throw std::runtime_error("Invalid saved sign-in size");
            std::ifstream file(path,std::ios::binary);std::vector<unsigned char> encrypted(size);file.read(reinterpret_cast<char*>(encrypted.data()),size);
            if(!file)throw std::runtime_error("Cannot read saved sign-in");
            DATA_BLOB input{static_cast<DWORD>(encrypted.size()),encrypted.data()},output{};
            if(!CryptUnprotectData(&input,nullptr,nullptr,nullptr,nullptr,CRYPTPROTECT_UI_FORBIDDEN,&output))throw std::runtime_error("Cannot decrypt saved sign-in");
            std::string plain(reinterpret_cast<char*>(output.pbData),output.cbData);SecureZeroMemory(output.pbData,output.cbData);LocalFree(output.pbData);
            auto saved=Json::parse(plain);
            if(saved.value("version",0)!=1||!saved.at("last_server").is_string()||!saved.at("tokens").is_object()||!saved.at("pending_logout").is_object())throw std::runtime_error("Invalid saved sign-in");
            for(auto& [base,token]:saved["tokens"].items())if(!token.is_string()||token.get<std::string>().size()>128)throw std::runtime_error("Invalid saved token");
            for(auto& [base,tokens]:saved["pending_logout"].items()){
                if(!tokens.is_array())throw std::runtime_error("Invalid pending logout");
                for(const auto& token:tokens)if(!token.is_string()||token.get<std::string>().size()>128)throw std::runtime_error("Invalid pending token");
            }
            data=std::move(saved);
        }catch(const std::exception&){unreadable=true;}
    }
    void save(){
        auto parent=path.parent_path();if(!parent.empty())std::filesystem::create_directories(parent);
        if(unreadable&&std::filesystem::exists(path)){
            auto backup=path;backup+=".unreadable-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+".bak";
            if(!CopyFileW(path.c_str(),backup.c_str(),TRUE))throw std::runtime_error("Could not back up unreadable saved sign-in");
            unreadable=false;
        }
        std::string plain=data.dump();DATA_BLOB input{static_cast<DWORD>(plain.size()),reinterpret_cast<BYTE*>(plain.data())},output{};
        if(!CryptProtectData(&input,L"Xervexl remembered sign-in",nullptr,nullptr,nullptr,CRYPTPROTECT_UI_FORBIDDEN,&output))throw std::runtime_error("Windows could not protect saved sign-in");
        auto temporary=path;temporary+=".tmp";
        std::ofstream file(temporary,std::ios::binary);file.write(reinterpret_cast<char*>(output.pbData),output.cbData);file.close();LocalFree(output.pbData);
        if(!file)throw std::runtime_error("Could not write saved sign-in");
        for(int attempt=0;attempt<6;attempt++){
            if(MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))return;
            std::this_thread::sleep_for(std::chrono::milliseconds(20*(attempt+1)));
        }
        throw std::runtime_error("Could not replace saved sign-in");
    }
    std::string token(const std::string& base)const{return data["tokens"].value(address(base),std::string{});}
    std::string last_server()const{return data.value("last_server",std::string("http://127.0.0.1:8765"));}
    void select(const std::string& base){load();data["last_server"]=address(base);save();}
    void remember(const std::string& base,const std::string& token){load();data["last_server"]=address(base);data["tokens"][address(base)]=token;save();}
    void forget(const std::string& base,const std::string& expected){load();if(token(base)==expected){data["tokens"].erase(address(base));save();}}
    void logout(const std::string& base,const std::string& token){
        load();auto key=address(base);if(this->token(base)==token)data["tokens"].erase(key);
        if(!data["pending_logout"].contains(key))data["pending_logout"][key]=Json::array();
        auto& pending=data["pending_logout"][key];bool found=false;for(auto& t:pending)if(t==token)found=true;
        if(!token.empty()&&!found)pending.push_back(token);
        save();
    }
    std::string pending(const std::string& base)const{
        auto it=data["pending_logout"].find(address(base));return it!=data["pending_logout"].end()&&!it->empty()?(*it)[0].get<std::string>():std::string{};
    }
    void acknowledge(const std::string& base,const std::string& token){
        load();auto key=address(base);auto it=data["pending_logout"].find(key);if(it==data["pending_logout"].end())return;
        auto remaining=Json::array();for(auto& t:*it)if(t!=token)remaining.push_back(t);
        if(remaining.empty())data["pending_logout"].erase(key);else *it=std::move(remaining);save();
    }
};
