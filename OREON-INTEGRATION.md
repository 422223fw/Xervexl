# Xervexl 0.12 — Oreon integration

Copyright (C) 2026 motlon for the original Xervexl gameplay and integration code.
The combined Xervexl release is distributed under GPL version 3; see `LICENSE`.
Existing third-party notices and license exceptions remain applicable to their
respective components. Selling the game does not remove source/license obligations.

## Upstream and modifications

Oreon Engine is by Fynn Fluegge and its contributors:
https://github.com/fynnfluegge/oreon-engine . The supplied
`oreon-engine-main.zip` was imported into `third_party/oreon`, retaining its GPLv3
license, README, source, resources and attribution. Input archive SHA-256:
`4261112281d3453bff8c8e191f1f8343b80bf584410c0d35d1d5cba3241cc181`.

Changes dated 21 October 2026:

- Maven parent references are concrete `3.0.0`, allowing installed module
  descriptors to resolve outside the reactor. LWJGL uses released `3.3.3` instead
  of the unavailable `3.1.7-SNAPSHOT` dependency.
- `GLShaderProgram` throws an exception on shader setup failure instead of
  terminating its native host with `System.exit`.
- `oreon-bridge/` is an original motlon extension: a portable window subclass,
  streamed world/UI VBOs, shaders, Oreon scene graph and render components, camera
  projection, actual depth-buffer rendering, and frame readback. It uses Oreon's
  `Window`, `Node`, `Renderable`, `GLRenderInfo`, `GLShaderProgram`, `VBO` and
  `RenderParameter` in every displayed frame, in both arena and survival worlds.
- `src/oreon.hpp` embeds portable Java through JNI. `src/render.hpp` presents the
  resulting frame through OpenGL or the native Vulkan swap chain in one client.
  Vulkan uses a coherent upload buffer and image transfer. This is **Oreon core/GL
  rendering with native Vulkan presentation**, not Oreon's deferred Vulkan module.
- Survival generation, shaped building, mining, crafting, creatures, account-only
  friends and private-world permissions are original Xervexl systems. No Roblox
  code, branded maps, character art or animations are imported.

## Build and corresponding source

Windows x64, Python 3.10+, a C++20 MinGW compiler and a compatible OpenGL 3.3 driver
are required. All downloads/builds can run in a writable folder as a normal user.

```powershell
python setup-oreon.py
powershell -NoProfile -ExecutionPolicy Bypass -File build-oreon.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1 -Compiler C:\path\to\g++.exe
python -m unittest discover -s tests -v
python package-release.py
```

`setup-oreon.py` pins Temurin 8u504-b01 and Maven 3.9.11 and verifies official
SHA-256/SHA-512 files over HTTPS. Maven dependencies are resolved with TLS enabled.
`build-oreon.ps1` also accepts explicit `-JavaHome` (JDK 8) and `-Maven` paths.
The JDK and Maven are build tools; they are not installed system-wide. No .NET SDK
is required. The game includes only a portable Java runtime, engine/dependency jars
and its native executable; Python is required separately for its local server.

Binary ZIPs include the corresponding Xervexl/Oreon source and build scripts in
their usual repository paths. The exact Temurin/OpenJDK source archive is included
at `runtime/sources/OpenJDK8U-jdk-sources_8u504b01.tar.gz`, with its verified digest
and upstream URL in `runtime/sources/manifest.json`. Java retains its GPLv2,
Classpath/Assembly exceptions and `THIRD_PARTY_README` in `runtime/java/`.
Dependency JARs retain their embedded licenses and notices. `THIRD_PARTY.md`
identifies the dependencies. Private `data/`, accounts, session tokens, learned
bot data, compiler/JDK/Maven caches and development logs are excluded from ZIPs
and Git. The Java source tarball is distributed in binary ZIPs, not checked into
Git as a generated 94 MB artifact; the setup script fetches the identical archive.

## Current scope

Worlds persist in `<accounts stem>.realms.json` and a neighbouring `.realms/`
directory. They generate deterministic half-metre terrain, trees and underground
resources with sparse saved edits and bounded nearby mesh detail. Building has
cubes, slabs, ramps, round pillars and beams. All editing, physics, materials,
crafting and combat decisions are server-authoritative. Individual crafted gear
and world XP/skill/crowns are separate from arena progression. Private world access
requires ownership or an accepted friendship; owners can turn friend building,
PvP, wild creatures and sparring bots on/off. Removing a friend revokes access.
Natural creatures currently use the shared humanoid combat rig with different
equipment, health and appearance; they are not a full ecosystem or animal AI.

Friends must connect to the **same running backend**. The server's `--host`
setting can bind a LAN address; no public hosting, automatic port forwarding or
firewall changes are configured. The default listener remains `127.0.0.1:8765`.
For LAN hosting, stop that local server first, then run
`python server.py --host 0.0.0.0`, and have friends enter the host's LAN address
in Settings. Do not run two servers against the same data directory.

OpenGL is the default. The current GL-to-CPU-to-Vulkan presentation bridge is
substantially slower on this computer than OpenGL presentation and still needs
optimization. Terrain detail has a bounded drawing distance, caves need further
visual polish, and network interpolation and camera clipping remain prototype
limitations. This is a playable survival foundation, not feature parity with
Minecraft or the complete original Oreon demonstration renderer.
