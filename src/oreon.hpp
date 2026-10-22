#pragma once
#include <jni.h>
#include <filesystem>
// Original motlon bridge. Oreon owns scene graph, shaders, VBOs and depth rendering.
struct Oreon {
    JavaVM* vm{};JNIEnv* env{};HMODULE library{};jclass bridge{};jmethodID renderMethod{};size_t frames=0;
    void checked(){if(env->ExceptionCheck()){env->ExceptionDescribe();env->ExceptionClear();throw std::runtime_error("Oreon rendering failed; see the Java diagnostic log.");}}
    Oreon(){
        auto runtime=std::filesystem::absolute("runtime/java/bin");SetDllDirectoryW(runtime.c_str());
        library=LoadLibraryW((runtime/"server/jvm.dll").c_str());if(!library)throw std::runtime_error("Missing portable Java runtime. Run build-oreon.ps1.");
        using Create=jint(JNICALL*)(JavaVM**,void**,void*);auto proc=GetProcAddress(library,"JNI_CreateJavaVM");Create create{};memcpy(&create,&proc,sizeof(create));
        std::string cp="-Djava.class.path=";for(const auto& jar:std::filesystem::directory_iterator("runtime/oreon"))if(jar.path().extension()==".jar"){if(cp.back()!='=')cp+=';';cp+=std::filesystem::absolute(jar.path()).string();}
        std::string headless="-Djava.awt.headless=true",heap="-Xmx256m";
        JavaVMOption options[3]{{cp.data(),nullptr},{headless.data(),nullptr},{heap.data(),nullptr}};JavaVMInitArgs args{};args.version=JNI_VERSION_1_8;args.nOptions=3;args.options=options;
        if(!create||create(&vm,reinterpret_cast<void**>(&env),&args)!=JNI_OK)throw std::runtime_error("Could not start the portable Oreon runtime");
        bridge=static_cast<jclass>(env->NewGlobalRef(env->FindClass("motlon/xervexl/OreonBridge")));checked();
        env->CallStaticVoidMethod(bridge,env->GetStaticMethodID(bridge,"initialize","()V"));checked();
        renderMethod=env->GetStaticMethodID(bridge,"render","(Ljava/nio/ByteBuffer;ILjava/nio/ByteBuffer;II[FII)Ljava/nio/ByteBuffer;");checked();
    }
    ~Oreon(){if(env&&bridge){env->CallStaticVoidMethod(bridge,env->GetStaticMethodID(bridge,"shutdown","()V"));if(env->ExceptionCheck())env->ExceptionClear();env->DeleteGlobalRef(bridge);}if(vm)vm->DestroyJavaVM();}
    std::vector<unsigned char> pixels;
    const std::vector<unsigned char>& draw(Canvas& c,int w,int h){
        struct Point{float x,y,z,r,g,b,a;};std::vector<Point> vertices;vertices.reserve(c.worldTriangles.size()*3);
        // Opaque surfaces write depth first; transparent surfaces are ordered back to front.
        std::stable_sort(c.worldTriangles.begin(),c.worldTriangles.end(),[](const Triangle& a,const Triangle& b){if((a.colour.a>=.99f)!=(b.colour.a>=.99f))return a.colour.a>=.99f;return a.colour.a>=.99f?false:a.depth>b.depth;});
        for(const auto& t:c.worldTriangles)for(Vec p:{t.a,t.b,t.c})vertices.push_back({p.x,p.y,p.z,t.colour.r,t.colour.g,t.colour.b,t.colour.a});
        Point dummy{};Vertex uiDummy{};auto data=env->NewDirectByteBuffer(vertices.empty()?&dummy:vertices.data(),std::max(size_t(1),vertices.size())*sizeof(Point));
        auto ui=env->NewDirectByteBuffer(c.mesh.empty()?&uiDummy:c.mesh.data(),std::max(size_t(1),c.mesh.size())*sizeof(Vertex));
        float camera[]={c.camera.x,c.camera.y,c.camera.z,c.right.x,c.right.y,c.right.z,c.up.x,c.up.y,c.up.z,c.forward.x,c.forward.y,c.forward.z};auto ca=env->NewFloatArray(12);env->SetFloatArrayRegion(ca,0,12,camera);
        auto result=env->CallStaticObjectMethod(bridge,renderMethod,data,static_cast<jint>(vertices.size()),ui,static_cast<jint>(c.mesh.size()),static_cast<jint>(c.backgroundEnd),ca,w,h);checked();
        auto raw=static_cast<unsigned char*>(env->GetDirectBufferAddress(result));pixels.resize(static_cast<size_t>(w)*h*4);
        for(int y=0;y<h;y++)memcpy(pixels.data()+static_cast<size_t>(y)*w*4,raw+static_cast<size_t>(h-1-y)*w*4,static_cast<size_t>(w)*4);
        env->DeleteLocalRef(result);env->DeleteLocalRef(data);env->DeleteLocalRef(ui);env->DeleteLocalRef(ca);frames++;return pixels;
    }
};
