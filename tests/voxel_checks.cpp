#include "render.hpp"
#include "json.hpp"
using json=nlohmann::json;
#include "scene.hpp"
#include "voxel.hpp"
#include <iostream>
int main(){
    json result=json::array();voxel::Landscape landscape;
    for(uint32_t seed:{0u,7u,16777215u})for(int x:{-1000000,-99,-15,-8,-1,0,8,9,20,99,1000000})for(int z:{-77,-1,0,8,45}){
        landscape.seed=seed;landscape.heights.clear();int h=voxel::height(seed,x,z);
        json blocks=json::array();for(int y:{h-12,h-2,h,h+1,h+5,h+8})blocks.push_back({y,landscape.generated(x,y,z)});
        result.push_back({{"seed",seed},{"x",x},{"z",z},{"height",h},{"blocks",blocks}});
    }
    std::cout<<result.dump();
}
