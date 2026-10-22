#pragma once
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <vector>
#include <string>
#include <stdexcept>
#include <fstream>
#include <memory>
#include <GL/gl.h>
#define VK_USE_PLATFORM_WIN32_KHR
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>

struct Vertex { float x,y,r,g,b,a; };
struct Renderer {
    bool captureRequested=false;
    std::vector<unsigned char> pixels;
    virtual ~Renderer() = default;
    virtual void draw(const std::vector<Vertex>& vertices, int width, int height) = 0;
    virtual void draw_pixels(const std::vector<unsigned char>&,int,int)=0;
    virtual const char* name() const = 0;
};

struct OpenGLRenderer : Renderer {
    HWND window; HDC dc; HGLRC context;
    OpenGLRenderer(HWND w):window(w),dc(GetDC(w)),context(nullptr) {
        if (!GetPixelFormat(dc)) {
            PIXELFORMATDESCRIPTOR p{}; p.nSize=sizeof(p);p.nVersion=1;
            p.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;
            p.iPixelType=PFD_TYPE_RGBA;p.cColorBits=32;p.cAlphaBits=8;
            int f=ChoosePixelFormat(dc,&p);
            if (!f || !SetPixelFormat(dc,f,&p)) throw std::runtime_error("OpenGL pixel format unavailable");
        }
        context=wglCreateContext(dc);
        if (!context || !wglMakeCurrent(dc,context)) throw std::runtime_error("OpenGL context unavailable");
    }
    ~OpenGLRenderer() {wglMakeCurrent(nullptr,nullptr);if(context)wglDeleteContext(context);ReleaseDC(window,dc);}
    const char* name() const override {return "OPENGL";}
    void draw_pixels(const std::vector<unsigned char>& rgba,int w,int h) override {
        wglMakeCurrent(dc,context);glViewport(0,0,w,h);glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);
        glMatrixMode(GL_PROJECTION);glLoadIdentity();glOrtho(0,w,h,0,-1,1);glMatrixMode(GL_MODELVIEW);glLoadIdentity();
        glRasterPos2i(0,0);glPixelZoom(1,-1);glDrawPixels(w,h,GL_RGBA,GL_UNSIGNED_BYTE,rgba.data());glPixelZoom(1,1);
        if(captureRequested)pixels=rgba;captureRequested=false;SwapBuffers(dc);
    }
    void draw(const std::vector<Vertex>& v,int w,int h) override {
        glViewport(0,0,w,h);glClearColor(.06f,.07f,.07f,1);glClear(GL_COLOR_BUFFER_BIT);
        glMatrixMode(GL_PROJECTION);glLoadIdentity();glOrtho(0,1,1,0,-1,1);
        glMatrixMode(GL_MODELVIEW);glLoadIdentity();glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);
        glEnableClientState(GL_VERTEX_ARRAY);glEnableClientState(GL_COLOR_ARRAY);
        glVertexPointer(2,GL_FLOAT,sizeof(Vertex),v.data());
        glColorPointer(4,GL_FLOAT,sizeof(Vertex),reinterpret_cast<const char*>(v.data())+sizeof(float)*2);
        glDrawArrays(GL_TRIANGLES,0,static_cast<GLsizei>(v.size()));
        if(captureRequested){
            std::vector<unsigned char> raw(static_cast<size_t>(w)*h*4);pixels.resize(raw.size());glReadPixels(0,0,w,h,GL_RGBA,GL_UNSIGNED_BYTE,raw.data());
            for(int y=0;y<h;y++)memcpy(pixels.data()+static_cast<size_t>(y)*w*4,raw.data()+static_cast<size_t>(h-1-y)*w*4,static_cast<size_t>(w)*4);
            captureRequested=false;
        }
        SwapBuffers(dc);
    }
};

#define VK_FUNCTIONS(X) \
X(vkCreateInstance) X(vkDestroyInstance) X(vkCreateWin32SurfaceKHR) X(vkDestroySurfaceKHR) \
X(vkEnumeratePhysicalDevices) X(vkGetPhysicalDeviceQueueFamilyProperties) X(vkGetPhysicalDeviceSurfaceSupportKHR) \
X(vkGetPhysicalDeviceSurfaceCapabilitiesKHR) X(vkGetPhysicalDeviceSurfaceFormatsKHR) X(vkGetPhysicalDeviceMemoryProperties) \
X(vkCreateDevice) X(vkDestroyDevice) X(vkGetDeviceQueue) X(vkDeviceWaitIdle) X(vkQueueWaitIdle) \
X(vkCreateSwapchainKHR) X(vkDestroySwapchainKHR) X(vkGetSwapchainImagesKHR) X(vkAcquireNextImageKHR) X(vkQueuePresentKHR) \
X(vkCreateImageView) X(vkDestroyImageView) X(vkCreateRenderPass) X(vkDestroyRenderPass) X(vkCreateFramebuffer) X(vkDestroyFramebuffer) \
X(vkCreateShaderModule) X(vkDestroyShaderModule) X(vkCreatePipelineLayout) X(vkDestroyPipelineLayout) \
X(vkCreateGraphicsPipelines) X(vkDestroyPipeline) X(vkCreateBuffer) X(vkDestroyBuffer) \
X(vkGetBufferMemoryRequirements) X(vkAllocateMemory) X(vkFreeMemory) X(vkBindBufferMemory) X(vkMapMemory) X(vkUnmapMemory) \
X(vkCreateCommandPool) X(vkDestroyCommandPool) X(vkAllocateCommandBuffers) X(vkResetCommandBuffer) \
X(vkBeginCommandBuffer) X(vkEndCommandBuffer) X(vkCmdBeginRenderPass) X(vkCmdEndRenderPass) \
X(vkCmdBindPipeline) X(vkCmdBindVertexBuffers) X(vkCmdSetViewport) X(vkCmdSetScissor) X(vkCmdDraw) X(vkCmdPipelineBarrier) X(vkCmdCopyImageToBuffer) X(vkCmdCopyBufferToImage) \
X(vkCreateSemaphore) X(vkDestroySemaphore) X(vkQueueSubmit)

struct VulkanRenderer : Renderer {
    HMODULE library{};PFN_vkGetInstanceProcAddr getProc{};
#define DECLARE_VK(fn) PFN_##fn fn{};
    VK_FUNCTIONS(DECLARE_VK)
#undef DECLARE_VK
    VkInstance instance{};VkSurfaceKHR surface{};VkPhysicalDevice physical{};VkDevice device{};VkQueue queue{};
    uint32_t family{};VkSwapchainKHR swapchain{};VkExtent2D extent{};VkFormat format{};
    std::vector<VkImageView> views;std::vector<VkFramebuffer> frames;
    std::vector<VkImage> images;
    VkBuffer readBuffer{};VkDeviceMemory readMemory{};void* readMapped{};
    VkBuffer uploadBuffer{};VkDeviceMemory uploadMemory{};void* uploadMapped{};
    VkRenderPass pass{};VkPipelineLayout layout{};VkPipeline pipeline{};
    VkBuffer buffer{};VkDeviceMemory memory{};void* mapped{};size_t capacity=sizeof(Vertex)*2000000;
    VkCommandPool pool{};VkCommandBuffer command{};VkSemaphore acquired{},complete{};

    static void check(VkResult result,const char* action){if(result!=VK_SUCCESS)throw std::runtime_error(std::string(action)+" ("+std::to_string(result)+")");}
    template<typename T> void load(T& fn,const char* name){fn=reinterpret_cast<T>(getProc(instance,name));if(!fn)throw std::runtime_error(std::string("Missing Vulkan function: ")+name);}
    explicit VulkanRenderer(HWND window) {
        try { initialize(window); } catch(...) { cleanup();throw; }
    }
    void initialize(HWND window){
        library=LoadLibraryW(L"vulkan-1.dll");if(!library)throw std::runtime_error("Vulkan driver not installed");
        auto proc=GetProcAddress(library,"vkGetInstanceProcAddr");static_assert(sizeof(proc)==sizeof(getProc));memcpy(&getProc,&proc,sizeof(proc));
        if(!getProc)throw std::runtime_error("Vulkan loader unavailable");
        load(vkCreateInstance,"vkCreateInstance");
        const char* extensions[]={VK_KHR_SURFACE_EXTENSION_NAME,VK_KHR_WIN32_SURFACE_EXTENSION_NAME};
        VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};app.pApplicationName="Xervexl";app.applicationVersion=1;app.pEngineName="motlon arena";app.apiVersion=VK_API_VERSION_1_0;
        VkInstanceCreateInfo ci{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};ci.pApplicationInfo=&app;ci.enabledExtensionCount=2;ci.ppEnabledExtensionNames=extensions;
        check(vkCreateInstance(&ci,nullptr,&instance),"Vulkan instance");
#define LOAD_VK(fn) load(fn,#fn);
        VK_FUNCTIONS(LOAD_VK)
#undef LOAD_VK
        VkWin32SurfaceCreateInfoKHR sc{VK_STRUCTURE_TYPE_WIN32_SURFACE_CREATE_INFO_KHR};sc.hinstance=GetModuleHandle(nullptr);sc.hwnd=window;
        check(vkCreateWin32SurfaceKHR(instance,&sc,nullptr,&surface),"Vulkan window surface");
        uint32_t count=0;check(vkEnumeratePhysicalDevices(instance,&count,nullptr),"GPU discovery");
        std::vector<VkPhysicalDevice> gpus(count);check(vkEnumeratePhysicalDevices(instance,&count,gpus.data()),"GPU list");
        for(auto gpu:gpus){
            uint32_t n=0;vkGetPhysicalDeviceQueueFamilyProperties(gpu,&n,nullptr);std::vector<VkQueueFamilyProperties> qs(n);vkGetPhysicalDeviceQueueFamilyProperties(gpu,&n,qs.data());
            for(uint32_t j=0;j<n;j++){VkBool32 supported=VK_FALSE;vkGetPhysicalDeviceSurfaceSupportKHR(gpu,j,surface,&supported);if((qs[j].queueFlags&VK_QUEUE_GRAPHICS_BIT)&&supported){physical=gpu;family=j;break;}}
            if(physical)break;
        }
        if(!physical)throw std::runtime_error("No GPU supports Vulkan presentation");
        float priority=1;VkDeviceQueueCreateInfo qc{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};qc.queueFamilyIndex=family;qc.queueCount=1;qc.pQueuePriorities=&priority;
        const char* ext=VK_KHR_SWAPCHAIN_EXTENSION_NAME;
        VkDeviceCreateInfo dc{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};dc.queueCreateInfoCount=1;dc.pQueueCreateInfos=&qc;dc.enabledExtensionCount=1;dc.ppEnabledExtensionNames=&ext;
        check(vkCreateDevice(physical,&dc,nullptr,&device),"Vulkan logical device");vkGetDeviceQueue(device,family,0,&queue);
        VkBufferCreateInfo bc{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};bc.size=capacity;bc.usage=VK_BUFFER_USAGE_VERTEX_BUFFER_BIT;bc.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
        check(vkCreateBuffer(device,&bc,nullptr,&buffer),"Vertex buffer");VkMemoryRequirements req{};vkGetBufferMemoryRequirements(device,buffer,&req);
        VkPhysicalDeviceMemoryProperties props{};vkGetPhysicalDeviceMemoryProperties(physical,&props);uint32_t memoryType=UINT32_MAX;
        for(uint32_t j=0;j<props.memoryTypeCount;j++)if((req.memoryTypeBits&(1<<j))&&((props.memoryTypes[j].propertyFlags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))==(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))){memoryType=j;break;}
        if(memoryType==UINT32_MAX)throw std::runtime_error("No coherent vertex memory");
        VkMemoryAllocateInfo ma{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ma.allocationSize=req.size;ma.memoryTypeIndex=memoryType;
        check(vkAllocateMemory(device,&ma,nullptr,&memory),"Vertex allocation");check(vkBindBufferMemory(device,buffer,memory,0),"Bind vertex memory");check(vkMapMemory(device,memory,0,capacity,0,&mapped),"Map vertices");
        VkCommandPoolCreateInfo pc{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};pc.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;pc.queueFamilyIndex=family;
        check(vkCreateCommandPool(device,&pc,nullptr,&pool),"Command pool");
        VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ca.commandPool=pool;ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ca.commandBufferCount=1;
        check(vkAllocateCommandBuffers(device,&ca,&command),"Command buffer");
        VkSemaphoreCreateInfo sem{VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};check(vkCreateSemaphore(device,&sem,nullptr,&acquired),"Acquire semaphore");check(vkCreateSemaphore(device,&sem,nullptr,&complete),"Present semaphore");
    }
    VkShaderModule shader(const char* path){
        std::ifstream f(path,std::ios::binary|std::ios::ate);if(!f)throw std::runtime_error(std::string("Missing shader: ")+path);
        size_t size=static_cast<size_t>(f.tellg());if(size%4)throw std::runtime_error("Invalid SPIR-V");std::vector<uint32_t> code(size/4);f.seekg(0);f.read(reinterpret_cast<char*>(code.data()),size);
        VkShaderModuleCreateInfo ci{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};ci.codeSize=size;ci.pCode=code.data();VkShaderModule m{};check(vkCreateShaderModule(device,&ci,nullptr,&m),"Shader module");return m;
    }
    void clear_swapchain(){
        if(!device)return;vkDeviceWaitIdle(device);
        if(uploadMapped)vkUnmapMemory(device,uploadMemory);uploadMapped=nullptr;
        if(uploadBuffer)vkDestroyBuffer(device,uploadBuffer,nullptr);uploadBuffer={};
        if(uploadMemory)vkFreeMemory(device,uploadMemory,nullptr);uploadMemory={};
        if(readMapped)vkUnmapMemory(device,readMemory);readMapped=nullptr;
        if(readBuffer)vkDestroyBuffer(device,readBuffer,nullptr);readBuffer={};
        if(readMemory)vkFreeMemory(device,readMemory,nullptr);readMemory={};images.clear();
        for(auto f:frames)vkDestroyFramebuffer(device,f,nullptr);frames.clear();
        if(pipeline)vkDestroyPipeline(device,pipeline,nullptr);pipeline={};
        if(layout)vkDestroyPipelineLayout(device,layout,nullptr);layout={};
        if(pass)vkDestroyRenderPass(device,pass,nullptr);pass={};
        for(auto view:views)vkDestroyImageView(device,view,nullptr);views.clear();
        if(swapchain)vkDestroySwapchainKHR(device,swapchain,nullptr);swapchain={};
    }
    void resize(int width,int height){
        clear_swapchain();VkSurfaceCapabilitiesKHR caps{};check(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&caps),"Surface capabilities");
        uint32_t n=0;check(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&n,nullptr),"Surface formats");std::vector<VkSurfaceFormatKHR> formats(n);check(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&n,formats.data()),"Surface formats");
        if(formats.empty())throw std::runtime_error("No Vulkan surface format");auto chosen=formats[0];
        for(auto f:formats)if(f.format==VK_FORMAT_B8G8R8A8_UNORM){chosen=f;break;}
        format=chosen.format;extent=caps.currentExtent;
        if(extent.width==UINT32_MAX){extent.width=std::max(caps.minImageExtent.width,std::min(caps.maxImageExtent.width,static_cast<uint32_t>(width)));extent.height=std::max(caps.minImageExtent.height,std::min(caps.maxImageExtent.height,static_cast<uint32_t>(height)));}
        uint32_t images=caps.minImageCount+1;if(caps.maxImageCount&&images>caps.maxImageCount)images=caps.maxImageCount;
        VkSwapchainCreateInfoKHR sc{VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR};sc.surface=surface;sc.minImageCount=images;sc.imageFormat=format;sc.imageColorSpace=chosen.colorSpace;sc.imageExtent=extent;sc.imageArrayLayers=1;sc.imageUsage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
        if(caps.supportedUsageFlags&VK_IMAGE_USAGE_TRANSFER_SRC_BIT)sc.imageUsage|=VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
        if(!(caps.supportedUsageFlags&VK_IMAGE_USAGE_TRANSFER_DST_BIT))throw std::runtime_error("Vulkan surface cannot receive Oreon frames");
        sc.imageUsage|=VK_IMAGE_USAGE_TRANSFER_DST_BIT;
        sc.imageSharingMode=VK_SHARING_MODE_EXCLUSIVE;sc.preTransform=caps.currentTransform;sc.compositeAlpha=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;sc.presentMode=VK_PRESENT_MODE_FIFO_KHR;sc.clipped=VK_TRUE;
        check(vkCreateSwapchainKHR(device,&sc,nullptr,&swapchain),"Swapchain");
        uint32_t imageCount=0;vkGetSwapchainImagesKHR(device,swapchain,&imageCount,nullptr);std::vector<VkImage> swapImages(imageCount);check(vkGetSwapchainImagesKHR(device,swapchain,&imageCount,swapImages.data()),"Swapchain images");
        this->images=swapImages;
        {
            VkBufferCreateInfo bc{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};bc.size=static_cast<VkDeviceSize>(extent.width)*extent.height*4;bc.usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT;bc.sharingMode=VK_SHARING_MODE_EXCLUSIVE;check(vkCreateBuffer(device,&bc,nullptr,&uploadBuffer),"Oreon upload buffer");
            VkMemoryRequirements req{};vkGetBufferMemoryRequirements(device,uploadBuffer,&req);VkPhysicalDeviceMemoryProperties props{};vkGetPhysicalDeviceMemoryProperties(physical,&props);uint32_t type=UINT32_MAX;
            for(uint32_t i=0;i<props.memoryTypeCount;i++)if((req.memoryTypeBits&(1<<i))&&((props.memoryTypes[i].propertyFlags&6)==6)){type=i;break;}
            if(type==UINT32_MAX)throw std::runtime_error("No coherent Oreon upload memory");VkMemoryAllocateInfo ma{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ma.allocationSize=req.size;ma.memoryTypeIndex=type;check(vkAllocateMemory(device,&ma,nullptr,&uploadMemory),"Oreon upload memory");check(vkBindBufferMemory(device,uploadBuffer,uploadMemory,0),"Bind Oreon upload");check(vkMapMemory(device,uploadMemory,0,bc.size,0,&uploadMapped),"Map Oreon upload");
        }
        if(sc.imageUsage&VK_IMAGE_USAGE_TRANSFER_SRC_BIT){
            VkBufferCreateInfo bc{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};bc.size=static_cast<VkDeviceSize>(extent.width)*extent.height*4;bc.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT;bc.sharingMode=VK_SHARING_MODE_EXCLUSIVE;check(vkCreateBuffer(device,&bc,nullptr,&readBuffer),"Readback buffer");
            VkMemoryRequirements req{};vkGetBufferMemoryRequirements(device,readBuffer,&req);VkPhysicalDeviceMemoryProperties props{};vkGetPhysicalDeviceMemoryProperties(physical,&props);uint32_t type=UINT32_MAX;
            for(uint32_t i=0;i<props.memoryTypeCount;i++)if((req.memoryTypeBits&(1<<i))&&((props.memoryTypes[i].propertyFlags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))==(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))){type=i;break;}
            if(type==UINT32_MAX)throw std::runtime_error("No readback memory");VkMemoryAllocateInfo ma{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ma.allocationSize=req.size;ma.memoryTypeIndex=type;check(vkAllocateMemory(device,&ma,nullptr,&readMemory),"Readback memory");check(vkBindBufferMemory(device,readBuffer,readMemory,0),"Bind readback");check(vkMapMemory(device,readMemory,0,bc.size,0,&readMapped),"Map readback");
        }
        for(auto image:swapImages){VkImageViewCreateInfo iv{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};iv.image=image;iv.viewType=VK_IMAGE_VIEW_TYPE_2D;iv.format=format;iv.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;iv.subresourceRange.levelCount=1;iv.subresourceRange.layerCount=1;VkImageView view{};check(vkCreateImageView(device,&iv,nullptr,&view),"Image view");views.push_back(view);}
        VkAttachmentDescription at{};at.format=format;at.samples=VK_SAMPLE_COUNT_1_BIT;at.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR;at.storeOp=VK_ATTACHMENT_STORE_OP_STORE;at.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE;at.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE;at.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;at.finalLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        VkAttachmentReference ref{0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};VkSubpassDescription sub{};sub.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS;sub.colorAttachmentCount=1;sub.pColorAttachments=&ref;
        VkSubpassDependency dep{};dep.srcSubpass=VK_SUBPASS_EXTERNAL;dep.dstSubpass=0;dep.srcStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;dep.dstStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;dep.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        VkRenderPassCreateInfo rp{VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO};rp.attachmentCount=1;rp.pAttachments=&at;rp.subpassCount=1;rp.pSubpasses=&sub;rp.dependencyCount=1;rp.pDependencies=&dep;
        check(vkCreateRenderPass(device,&rp,nullptr,&pass),"Render pass");
        for(auto view:views){VkFramebufferCreateInfo fb{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};fb.renderPass=pass;fb.attachmentCount=1;fb.pAttachments=&view;fb.width=extent.width;fb.height=extent.height;fb.layers=1;VkFramebuffer frame{};check(vkCreateFramebuffer(device,&fb,nullptr,&frame),"Framebuffer");frames.push_back(frame);}
        VkShaderModule vert=shader("shaders/arena.vert.spv"),frag=shader("shaders/arena.frag.spv");
        VkPipelineShaderStageCreateInfo stages[2]{};stages[0].sType=stages[1].sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;stages[0].stage=VK_SHADER_STAGE_VERTEX_BIT;stages[0].module=vert;stages[0].pName="main";stages[1].stage=VK_SHADER_STAGE_FRAGMENT_BIT;stages[1].module=frag;stages[1].pName="main";
        VkVertexInputBindingDescription binding{0,sizeof(Vertex),VK_VERTEX_INPUT_RATE_VERTEX};VkVertexInputAttributeDescription attrs[]={{0,0,VK_FORMAT_R32G32_SFLOAT,0},{1,0,VK_FORMAT_R32G32B32A32_SFLOAT,sizeof(float)*2}};
        VkPipelineVertexInputStateCreateInfo vi{VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};vi.vertexBindingDescriptionCount=1;vi.pVertexBindingDescriptions=&binding;vi.vertexAttributeDescriptionCount=2;vi.pVertexAttributeDescriptions=attrs;
        VkPipelineInputAssemblyStateCreateInfo ia{VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};ia.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
        VkPipelineViewportStateCreateInfo vp{VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};vp.viewportCount=1;vp.scissorCount=1;
        VkPipelineRasterizationStateCreateInfo rs{VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};rs.polygonMode=VK_POLYGON_MODE_FILL;rs.cullMode=VK_CULL_MODE_NONE;rs.frontFace=VK_FRONT_FACE_CLOCKWISE;rs.lineWidth=1;
        VkPipelineMultisampleStateCreateInfo ms{VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};ms.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT;
        VkPipelineColorBlendAttachmentState blend{};blend.blendEnable=VK_TRUE;blend.srcColorBlendFactor=VK_BLEND_FACTOR_SRC_ALPHA;blend.dstColorBlendFactor=VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA;blend.colorBlendOp=VK_BLEND_OP_ADD;blend.srcAlphaBlendFactor=VK_BLEND_FACTOR_ONE;blend.dstAlphaBlendFactor=VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA;blend.alphaBlendOp=VK_BLEND_OP_ADD;blend.colorWriteMask=15;
        VkPipelineColorBlendStateCreateInfo cb{VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO};cb.attachmentCount=1;cb.pAttachments=&blend;
        VkDynamicState ds[]={VK_DYNAMIC_STATE_VIEWPORT,VK_DYNAMIC_STATE_SCISSOR};VkPipelineDynamicStateCreateInfo dynamic{VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO};dynamic.dynamicStateCount=2;dynamic.pDynamicStates=ds;
        VkPipelineLayoutCreateInfo lc{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};check(vkCreatePipelineLayout(device,&lc,nullptr,&layout),"Pipeline layout");
        VkGraphicsPipelineCreateInfo pi{VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};pi.stageCount=2;pi.pStages=stages;pi.pVertexInputState=&vi;pi.pInputAssemblyState=&ia;pi.pViewportState=&vp;pi.pRasterizationState=&rs;pi.pMultisampleState=&ms;pi.pColorBlendState=&cb;pi.pDynamicState=&dynamic;pi.layout=layout;pi.renderPass=pass;
        VkResult result=vkCreateGraphicsPipelines(device,VK_NULL_HANDLE,1,&pi,nullptr,&pipeline);vkDestroyShaderModule(device,vert,nullptr);vkDestroyShaderModule(device,frag,nullptr);check(result,"Graphics pipeline");
    }
    void draw(const std::vector<Vertex>& v,int width,int height) override {
        if(!swapchain||extent.width!=static_cast<uint32_t>(width)||extent.height!=static_cast<uint32_t>(height))resize(width,height);
        uint32_t index=0;VkResult r=vkAcquireNextImageKHR(device,swapchain,UINT64_MAX,acquired,VK_NULL_HANDLE,&index);
        if(r==VK_ERROR_OUT_OF_DATE_KHR){resize(width,height);return;}if(r!=VK_SUBOPTIMAL_KHR)check(r,"Acquire frame");
        if(v.size()*sizeof(Vertex)>capacity)throw std::runtime_error("Scene vertex capacity exceeded");
        memcpy(mapped,v.data(),v.size()*sizeof(Vertex));check(vkResetCommandBuffer(command,0),"Reset command buffer");
        VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;check(vkBeginCommandBuffer(command,&begin),"Begin frame");
        VkClearValue clear{};clear.color={{.06f,.07f,.07f,1}};VkRenderPassBeginInfo rp{VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO};rp.renderPass=pass;rp.framebuffer=frames[index];rp.renderArea.extent=extent;rp.clearValueCount=1;rp.pClearValues=&clear;
        vkCmdBeginRenderPass(command,&rp,VK_SUBPASS_CONTENTS_INLINE);vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_GRAPHICS,pipeline);
        VkViewport viewport{0,0,static_cast<float>(extent.width),static_cast<float>(extent.height),0,1};VkRect2D scissor{{0,0},extent};vkCmdSetViewport(command,0,1,&viewport);vkCmdSetScissor(command,0,1,&scissor);
        VkDeviceSize offset=0;vkCmdBindVertexBuffers(command,0,1,&buffer,&offset);vkCmdDraw(command,static_cast<uint32_t>(v.size()),1,0,0);vkCmdEndRenderPass(command);
        bool capture=captureRequested&&readMapped;
        if(capture){
            VkImageMemoryBarrier barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};barrier.srcAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;barrier.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;barrier.oldLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;barrier.newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;barrier.srcQueueFamilyIndex=barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;barrier.image=images[index];barrier.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;barrier.subresourceRange.levelCount=1;barrier.subresourceRange.layerCount=1;
            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&barrier);
            VkBufferImageCopy copy{};copy.imageSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;copy.imageSubresource.layerCount=1;copy.imageExtent={extent.width,extent.height,1};vkCmdCopyImageToBuffer(command,images[index],VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,readBuffer,1,&copy);
            barrier.srcAccessMask=VK_ACCESS_TRANSFER_READ_BIT;barrier.dstAccessMask=0;barrier.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;barrier.newLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,0,0,nullptr,0,nullptr,1,&barrier);
        }
        check(vkEndCommandBuffer(command),"End frame");
        VkPipelineStageFlags wait=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.waitSemaphoreCount=1;submit.pWaitSemaphores=&acquired;submit.pWaitDstStageMask=&wait;submit.commandBufferCount=1;submit.pCommandBuffers=&command;submit.signalSemaphoreCount=1;submit.pSignalSemaphores=&complete;
        check(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE),"Submit frame");
        VkPresentInfoKHR present{VK_STRUCTURE_TYPE_PRESENT_INFO_KHR};present.waitSemaphoreCount=1;present.pWaitSemaphores=&complete;present.swapchainCount=1;present.pSwapchains=&swapchain;present.pImageIndices=&index;
        r=vkQueuePresentKHR(queue,&present);vkQueueWaitIdle(queue);if(r!=VK_ERROR_OUT_OF_DATE_KHR&&r!=VK_SUBOPTIMAL_KHR)check(r,"Present frame");
        if(capture){pixels.resize(static_cast<size_t>(extent.width)*extent.height*4);memcpy(pixels.data(),readMapped,pixels.size());if(format==VK_FORMAT_B8G8R8A8_UNORM||format==VK_FORMAT_B8G8R8A8_SRGB)for(size_t i=0;i<pixels.size();i+=4)std::swap(pixels[i],pixels[i+2]);}
        captureRequested=false;
    }
    void draw_pixels(const std::vector<unsigned char>& rgba,int w,int h) override {
        if(!swapchain||extent.width!=static_cast<uint32_t>(w)||extent.height!=static_cast<uint32_t>(h))resize(w,h);
        if(extent.width!=static_cast<uint32_t>(w)||extent.height!=static_cast<uint32_t>(h))return;
        uint32_t index=0;auto r=vkAcquireNextImageKHR(device,swapchain,UINT64_MAX,acquired,VK_NULL_HANDLE,&index);
        if(r==VK_ERROR_OUT_OF_DATE_KHR){resize(w,h);return;}if(r!=VK_SUBOPTIMAL_KHR)check(r,"Acquire Oreon frame");
        memcpy(uploadMapped,rgba.data(),rgba.size());
        if(format==VK_FORMAT_B8G8R8A8_UNORM||format==VK_FORMAT_B8G8R8A8_SRGB){auto p=static_cast<unsigned char*>(uploadMapped);for(size_t i=0;i<rgba.size();i+=4)std::swap(p[i],p[i+2]);}
        else if(format!=VK_FORMAT_R8G8B8A8_UNORM&&format!=VK_FORMAT_R8G8B8A8_SRGB)throw std::runtime_error("Unsupported Oreon presentation format");
        check(vkResetCommandBuffer(command,0),"Reset Oreon frame");VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;check(vkBeginCommandBuffer(command,&begin),"Begin Oreon frame");
        VkImageMemoryBarrier b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};b.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;b.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED;b.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;b.srcQueueFamilyIndex=b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;b.image=images[index];b.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;b.subresourceRange.levelCount=1;b.subresourceRange.layerCount=1;
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&b);
        VkBufferImageCopy copy{};copy.imageSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;copy.imageSubresource.layerCount=1;copy.imageExtent={extent.width,extent.height,1};vkCmdCopyBufferToImage(command,uploadBuffer,images[index],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
        b.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;b.dstAccessMask=0;b.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;b.newLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,0,0,nullptr,0,nullptr,1,&b);
        check(vkEndCommandBuffer(command),"End Oreon frame");VkPipelineStageFlags stage=VK_PIPELINE_STAGE_TRANSFER_BIT;VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.waitSemaphoreCount=1;submit.pWaitSemaphores=&acquired;submit.pWaitDstStageMask=&stage;submit.commandBufferCount=1;submit.pCommandBuffers=&command;submit.signalSemaphoreCount=1;submit.pSignalSemaphores=&complete;check(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE),"Submit Oreon frame");
        VkPresentInfoKHR present{VK_STRUCTURE_TYPE_PRESENT_INFO_KHR};present.waitSemaphoreCount=1;present.pWaitSemaphores=&complete;present.swapchainCount=1;present.pSwapchains=&swapchain;present.pImageIndices=&index;r=vkQueuePresentKHR(queue,&present);vkQueueWaitIdle(queue);if(r!=VK_ERROR_OUT_OF_DATE_KHR&&r!=VK_SUBOPTIMAL_KHR)check(r,"Present Oreon frame");
        if(captureRequested)pixels=rgba;captureRequested=false;
    }
    const char* name() const override{return "VULKAN";}
    void cleanup(){
        if(device){clear_swapchain();if(mapped)vkUnmapMemory(device,memory);if(buffer)vkDestroyBuffer(device,buffer,nullptr);if(memory)vkFreeMemory(device,memory,nullptr);if(pool)vkDestroyCommandPool(device,pool,nullptr);if(acquired)vkDestroySemaphore(device,acquired,nullptr);if(complete)vkDestroySemaphore(device,complete,nullptr);vkDestroyDevice(device,nullptr);}
        if(surface&&vkDestroySurfaceKHR)vkDestroySurfaceKHR(instance,surface,nullptr);if(instance&&vkDestroyInstance)vkDestroyInstance(instance,nullptr);if(library)FreeLibrary(library);
    }
    ~VulkanRenderer(){cleanup();}
};
