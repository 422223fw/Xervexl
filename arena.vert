#version 450
layout(location=0) in vec2 position;
layout(location=1) in vec4 colour;
layout(location=0) out vec4 tint;
layout(set = 0, binding = 0) uniform Transform {
    mat4 projection;
} u_Transform;
void main(){
    gl_Position = u_Transform.projection * vec4(position,0.0,1.0);
    tint = colour;
}
