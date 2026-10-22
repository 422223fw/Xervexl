# Third-party notices

- `third_party/oreon/`: Oreon Engine, Fynn Fluegge and contributors, GPLv3. The original license and attribution are retained. See `OREON-INTEGRATION.md` for the supplied archive digest, dated modifications and actual runtime integration.
- Runtime/build dependency LWJGL 3.3.3, BSD 3-Clause; licenses remain inside the distributed JARs. https://github.com/LWJGL/lwjgl3/tree/3.3.3 . Native dependencies retain their notices in those JARs.
- Log4j API/Core 2.17.1, Apache 2.0; embedded LICENSE/NOTICE retained. https://logging.apache.org/log4j/2.x/ . Lombok 1.18.2, MIT, retained as an upstream build dependency with its embedded license.
- Portable Eclipse Temurin/OpenJDK 8u504-b01 runtime, GPLv2 with the applicable Classpath/Assembly exceptions. `runtime/java/LICENSE`, `ASSEMBLY_EXCEPTION` and `THIRD_PARTY_README` are retained in binary distributions. Exact corresponding source is included at `runtime/sources/`; see `OREON-INTEGRATION.md`. https://github.com/adoptium/temurin8-binaries/releases/tag/jdk8u504-b01 .
- Apache Maven 3.9.11 is a build-only dependency (Apache 2.0), downloaded locally by `setup-oreon.py`; it is not part of the game runtime.

- `vendor/json.hpp`: nlohmann/json v3.12.0, MIT license. Copyright Niels Lohmann and contributors. Source: https://github.com/nlohmann/json/tree/v3.12.0. License: `vendor/JSON-LICENSE.txt`.
- `vendor/vulkan/` and `vendor/vk_video/`: Khronos Vulkan-Headers v1.3.290. SPDX Apache-2.0 and MIT notices are retained in the headers. Source: https://github.com/KhronosGroup/Vulkan-Headers/tree/v1.3.290. License: `vendor/VULKAN-LICENSE.md`.
- `tools/make_shaders.py` emits the project's own fixed shaders in SPIR-V 1.0, the Khronos standardized shader binary format: https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html.
- Build dependency on this computer: WinLibs GCC 16.2.0 / MinGW-w64 14.0.0 UCRT. https://winlibs.com/. GCC runtime is linked under its Runtime Library Exception. No GCC compiler is included in the game distribution.

The native application calls Windows OpenGL, WinHTTP, GDI, WinMM and the installed Vulkan GPU loader. No modified Windows system libraries are distributed. The shader compiler archives used during development are excluded from the project/distribution.
