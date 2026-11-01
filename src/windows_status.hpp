#pragma once
#include <windows.h>
#include <shellapi.h>
#include <string>

// A per-window Windows notification icon; no background service or installation.
class WindowsStatus {
    NOTIFYICONDATAW icon{};
    bool present=false;
    std::wstring tooltip=L"Xervexl | motlon\nConnecting to server";
public:
    static constexpr UINT callback=WM_APP+41;
    const UINT taskbarCreated=RegisterWindowMessageW(L"TaskbarCreated");
    void attach(HWND window){
        icon.cbSize=sizeof(icon);icon.hWnd=window;icon.uID=1;
        icon.uFlags=NIF_MESSAGE|NIF_ICON|NIF_TIP;
        icon.uCallbackMessage=callback;icon.hIcon=LoadIconW(nullptr,MAKEINTRESOURCEW(32512));
        refresh(true);
    }
    void refresh(bool add=false){
        if(!icon.hWnd)return;
        wcsncpy(icon.szTip,tooltip.c_str(),127);icon.szTip[127]=0;
        present=Shell_NotifyIconW(add?NIM_ADD:NIM_MODIFY,&icon)!=FALSE;
    }
    void set(const std::string& value){
        int length=MultiByteToWideChar(CP_UTF8,0,value.data(),static_cast<int>(value.size()),nullptr,0);
        std::wstring next(length,L' ');
        if(length)MultiByteToWideChar(CP_UTF8,0,value.data(),static_cast<int>(value.size()),next.data(),length);
        if(next==tooltip&&present)return;
        tooltip=next;refresh(!present);
    }
    bool available()const{return present;}
    void remove(){if(present)Shell_NotifyIconW(NIM_DELETE,&icon);present=false;icon.hWnd=nullptr;}
    ~WindowsStatus(){remove();}
};
