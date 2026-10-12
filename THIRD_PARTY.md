# Third-party notices

- `vendor/json.hpp`: nlohmann/json v3.12.0, MIT license. Copyright Niels Lohmann and contributors. Source: https://github.com/nlohmann/json/tree/v3.12.0. License: `vendor/JSON-LICENSE.txt`.
- `vendor/vulkan/` and `vendor/vk_video/`: Khronos Vulkan-Headers v1.3.290. SPDX Apache-2.0 and MIT notices are retained in the headers. Source: https://github.com/KhronosGroup/Vulkan-Headers/tree/v1.3.290. License: `vendor/VULKAN-LICENSE.md`.
- `tools/make_shaders.py` emits the project's own fixed shaders in SPIR-V 1.0, the Khronos standardized shader binary format: https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html.
- Build dependency on this computer: WinLibs GCC 16.2.0 / MinGW-w64 14.0.0 UCRT. https://winlibs.com/. GCC runtime is linked under its Runtime Library Exception. No GCC compiler is included in the game distribution.

The native application calls Windows OpenGL, WinHTTP, GDI, WinMM and the installed Vulkan GPU loader. No modified Windows system libraries are distributed. The shader compiler archives used during development are excluded from the project/distribution.
