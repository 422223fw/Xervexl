#include "render.hpp"
#include "json.hpp"
using json=nlohmann::json;
#include "scene.hpp"
#include <cassert>
#include <iostream>

int main(){
    size_t maximum=0;int checked=0;
    for(const std::string biome:{"desert","forest","snow","coast","volcanic","autumn","night","marsh"}){
        json world={{"biome",biome},{"seed",9351},{"props",json::array()}};
        for(int i=0;i<24;i++)world["props"].push_back({{"kind",i%4==0?"tree":i%4==1?"ruin":i%4==2?"pillar":"rock"},{"x",std::sin(i)*22},{"z",std::cos(i)*22},{"radius",1.f},{"height",i%4==0?5.f:2.5f}});
        Canvas c;c.begin(1280,800);c.set_camera({0,3,-8},{0,1,0});environment(c,2,world);
        size_t count=c.triangles.size()+c.mesh.size()/3;
        assert(count<24000);maximum=std::max(maximum,count);
        for(const auto& t:c.triangles)for(Vec v:{t.a,t.b,t.c})assert(std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z));
        assert(c.fogColour.r==world_palette(biome).horizon.r);
        Canvas same;same.begin(1280,800);same.set_camera({0,3,-8},{0,1,0});environment(same,2,world);
        assert(c.triangles.size()==same.triangles.size());
        for(size_t i=0;i<c.triangles.size();i++)assert(dot(c.triangles[i].a-same.triangles[i].a,c.triangles[i].a-same.triangles[i].a)==0);
        c.flush3();for(const auto& vertex:c.mesh)assert(std::isfinite(vertex.x)&&std::isfinite(vertex.y));checked++;
    }
    auto day=world_palette("desert"),night=world_palette("night");assert(night.skyTop.r<day.skyTop.r&&night.ambient<day.ambient);
    std::cout<<checked<<" deterministic biome renders passed; maximum visible world triangles "<<maximum<<".\n";
}
