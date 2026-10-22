/* Xervexl integration, Copyright (C) 2026 motlon. GPL-3.0-or-later. */
package motlon.xervexl;

import java.nio.*;
import org.lwjgl.BufferUtils;
import org.lwjgl.opengl.GL;
import org.oreon.core.platform.Window;
import org.oreon.core.scenegraph.*;
import org.oreon.core.gl.scenegraph.GLRenderInfo;
import org.oreon.core.gl.pipeline.*;
import org.oreon.core.gl.memory.VBO;
import org.oreon.core.math.Vec3f;
import static org.lwjgl.glfw.GLFW.*;
import static org.lwjgl.opengl.GL33.*;

/** Oreon scene graph and render components, hosted by the native Xervexl client.
 * The same scene is presented by OpenGL or the native Vulkan swap chain. */
public final class OreonBridge {
    private static EngineWindow window;
    private static Node scene;
    private static StreamVBO world,overlay;
    private static SceneShader shader;
    private static GLRenderInfo worldInfo,uiInfo;
    private static ByteBuffer pixels;
    public static long frames;
    private static class EngineWindow extends Window {
        EngineWindow(){super("Xervexl / Oreon offscreen scene",1280,800);}
        public void create(){
            if(!glfwInit())throw new IllegalStateException("GLFW initialization failed");
            glfwDefaultWindowHints();glfwWindowHint(GLFW_VISIBLE,GLFW_FALSE);
            glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR,3);glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR,3);
            glfwWindowHint(GLFW_OPENGL_PROFILE,GLFW_OPENGL_CORE_PROFILE);
            setId(glfwCreateWindow(getWidth(),getHeight(),getTitle(),0,0));
            if(getId()==0)throw new IllegalStateException("Oreon requires an OpenGL 3.3 driver");
            glfwMakeContextCurrent(getId());GL.createCapabilities();glfwSwapInterval(0);
        }
        public void show(){} public void draw(){glFlush();}
        public void shutdown(){glfwDestroyWindow(getId());glfwTerminate();}
        public boolean isCloseRequested(){return glfwWindowShouldClose(getId());}
        public void resize(int w,int h){if(w!=getWidth()||h!=getHeight()){setWidth(w);setHeight(h);glfwSetWindowSize(getId(),w,h);}}
    }
    private static class State implements RenderParameter {
        boolean depth;State(boolean d){depth=d;}
        public void enable(){if(depth){glEnable(GL_DEPTH_TEST);glDepthMask(true);}else{glDisable(GL_DEPTH_TEST);glDepthMask(false);}glDisable(GL_CULL_FACE);glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);}
        public void disable(){}
    }
    private static class StreamVBO implements VBO {
        int vao=glGenVertexArrays(),vbo=glGenBuffers(),count,stride;
        StreamVBO(int s){stride=s;}
        void upload(ByteBuffer data,int count){this.count=count;glBindVertexArray(vao);glBindBuffer(GL_ARRAY_BUFFER,vbo);
            data.order(ByteOrder.nativeOrder());FloatBuffer values=data.asFloatBuffer();values.limit(count*stride);
            glBufferData(GL_ARRAY_BUFFER,values,GL_STREAM_DRAW);glEnableVertexAttribArray(0);glVertexAttribPointer(0,stride-4,GL_FLOAT,false,stride*4,0L);
            glEnableVertexAttribArray(1);glVertexAttribPointer(1,4,GL_FLOAT,false,stride*4,(stride-4)*4L);}
        public void draw(){glBindVertexArray(vao);glDrawArrays(GL_TRIANGLES,0,count);}
        public void delete(){glDeleteBuffers(vbo);glDeleteVertexArrays(vao);}
    }
    private static class SceneShader extends GLShaderProgram {
        SceneShader(boolean ui){
            addVertexShader("#version 330 core\nlayout(location=0) in "+(ui?"vec2":"vec3")+" p;layout(location=1) in vec4 colour;out vec4 tint;"+
                (ui?"void main(){tint=colour;gl_Position=vec4(p.x*2-1,1-p.y*2,0,1);}":
                "uniform vec3 eye,right,up,forward;uniform float aspect;void main(){vec3 d=p-eye;float z=dot(d,forward);gl_Position=vec4(dot(d,right)*1.09375/aspect,dot(d,up)*1.095,1.00048*z-.24006,z);tint=colour;}"));
            addFragmentShader("#version 330 core\nin vec4 tint;out vec4 result;void main(){result=tint;}");compileShader();
            if(!ui)for(String n:new String[]{"eye","right","up","forward","aspect"})addUniform(n);
        }
    }
    private static Renderable object(GLRenderInfo info){Renderable r=new Renderable();r.addComponent(NodeComponentType.MAIN_RENDERINFO,info);return r;}
    public static void initialize(){
        window=new EngineWindow();window.create();glBindVertexArray(glGenVertexArrays());
        world=new StreamVBO(7);overlay=new StreamVBO(6);shader=new SceneShader(false);
        worldInfo=new GLRenderInfo(shader,new State(true),world);uiInfo=new GLRenderInfo(new SceneShader(true),new State(false),overlay);
        scene=new Node();scene.addChild(object(worldInfo));pixels=BufferUtils.createByteBuffer(4);
    }
    public static ByteBuffer render(ByteBuffer vertices,int count,ByteBuffer ui,int uiCount,int background,float[] camera,int w,int h){
        glfwMakeContextCurrent(window.getId());window.resize(w,h);glViewport(0,0,w,h);glDepthMask(true);glClearColor(.54f,.66f,.72f,1);glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);
        if(background>0){overlay.upload(ui,background);uiInfo.render();}
        shader.bind();for(int i=0;i<4;i++)shader.setUniform(new String[]{"eye","right","up","forward"}[i],new Vec3f(camera[i*3],camera[i*3+1],camera[i*3+2]));shader.setUniformf("aspect",(float)w/h);
        world.upload(vertices,count);scene.render();
        if(uiCount>background){ui.position(background*24);overlay.upload(ui.slice(),uiCount-background);uiInfo.render();ui.position(0);}
        if(pixels.capacity()!=w*h*4)pixels=BufferUtils.createByteBuffer(w*h*4);
        glReadPixels(0,0,w,h,GL_RGBA,GL_UNSIGNED_BYTE,pixels);window.draw();frames++;return pixels;
    }
    public static void shutdown(){if(window!=null){world.delete();overlay.delete();window.shutdown();window=null;}}
}
