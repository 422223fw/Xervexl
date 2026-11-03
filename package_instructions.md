# Xervexl Package – Build & Distribution Guide

## 1. Prerequisites

| Requirement | Tool / Version | Notes |
|-------------|---------------|-------|
| **Python** | 3.10+ | Used for the build script and packaging steps. |
| **MinGW‑WSL** (or any GCC‑compatible compiler) | 8+ | Build script `build.ps1` invokes `g++` to compile the C++ client. | 
| **PowerShell** | v5+ | Execution policy set to **Bypass** during builds and releases. |

## 2. Build the Native Client

```powershell
# From the project root: C:\Users\Anabel\Documents\Downloads\Xervexl
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

> **Success** – After a few seconds the executable is created at `build\Xervexl.exe`. It can be launched directly:
> ```powershell
> build\Xervexl.exe
> ```

## 3. Verify the Build

1. **Smoke tests** – run the compiled binary with each supported API.

```powershell
build\Xervexl.exe --smoke --opengl
build\Xervexl.exe --smoke --vulkan
build\Xervexl.exe --smoke --arena
```
All should exit with code 0.

2. **Runtime files** – `runtime/` contains the portable C++ runtime that the client needs at launch.

3. **Assets & configuration** –
   * `data/` – player accounts, game settings, etc. (do not include in the public package; copy this folder per user).
   * `screenshots/` – location for any generated screenshots.
   * `OREON‑INTEGRATION.md` – shows how the client links to the Oreon rendering library.

## 4. Package the Release

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File package.ps1
```
The `package.ps1` script calls `python package‑release.py` which will:

* Bundle the `build/` folder (containing `Xervexl.exe`).
* Stash the `runtime/` folder.
* Include `start.ps1` so the game can be started with a single script.
* Copy the `data/`, `screenshots/`, and `OREON‑INTEGRATION.md` files for completeness.

After execution a `dist/` folder will exist. It has the following structure:
```
dist/
├─ Xervexl.exe
├─ runtime/
├─ start.ps1
├─ data/
├─ screenshots/
├─ OREON‑INTEGRATION.md
```

## 5. Verify the Release

Run the simple launch script:
```powershell
.
start.ps1
```
Make sure that:
* The executable runs without admin rights.
* All resources are present.
* The smoke tests in step 3 run again successfully from the `dist` directory.

## 6. Documentation & Versioning

* Clear license: GPL‑v3.
* Each release should include a changelog in `CHANGELOG.md`.
* Maintain a `VERSION.txt` with the current semantic version.

---

> **Tip** – The `build.ps1` script accepts a `-Compiler` argument if another MinGW build tool is desired:
> ```powershell
> build.ps1 -Compiler C:\Path\to\g++.exe
> ```
> 
> This keeps the build deterministic across machines.
