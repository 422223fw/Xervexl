#include "login_store.hpp"
#include <cassert>
#include <iostream>

int main(int argc,char** argv){
    assert(argc==2);std::filesystem::path path=argv[1];
    const std::string a="http://127.0.0.1:18761",b="http://127.0.0.1:18762",secret="synthetic-remembered-token-no-real-credentials";
    LoginStore saved(path.string());saved.remember(a,secret);
    std::ifstream file(path,std::ios::binary);std::string bytes((std::istreambuf_iterator<char>(file)),{});file.close();
    assert(bytes.find(secret)==std::string::npos);assert(bytes.find(a)==std::string::npos);
    LoginStore reopened(path.string());assert(reopened.token(a)==secret);assert(reopened.token(b).empty());assert(reopened.last_server()==a);
    reopened.remember(b,"other-synthetic-token");reopened.logout(a,secret);
    LoginStore offline(path.string());assert(offline.token(a).empty());assert(offline.pending(a)==secret);assert(offline.token(b)=="other-synthetic-token");
    offline.acknowledge(a,secret);LoginStore acknowledged(path.string());assert(acknowledged.pending(a).empty());
    acknowledged.forget(b,"different-token");assert(acknowledged.token(b)=="other-synthetic-token");
    acknowledged.forget(b,"other-synthetic-token");assert(LoginStore(path.string()).token(b).empty());
    std::ofstream(path,std::ios::binary)<<"corrupt-encrypted-cache";
    LoginStore damaged(path.string());assert(damaged.unreadable);assert(damaged.token(a).empty());
    damaged.remember(a,secret);assert(LoginStore(path.string()).token(a)==secret);
    bool backup=false;for(auto& p:std::filesystem::directory_iterator(path.parent_path()))if(p.path().filename().string().find(path.filename().string()+".unreadable-")==0)backup=true;
    assert(backup);
    std::cout<<"Windows-protected sign-in: encrypted disk data, restart restore, server isolation, offline logout, revocation acknowledgement and corruption backup passed.\n";
}
