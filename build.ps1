param([string]$Compiler = "C:\Users\Anabel\Documents\Downloads\C\cpp-toolchain\mingw64\bin\g++.exe", [string]$OutputPath = "build/Xervexl.exe", [string]$JavaHome="", [switch]$ReuseAudio)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!(Test-Path -LiteralPath $Compiler)) { throw "Set -Compiler to your g++.exe path." }
New-Item -ItemType Directory -Path build -Force | Out-Null
if(!$JavaHome){$JavaHome=(Get-Content build/java-tools/toolchain.json -Raw | ConvertFrom-Json).java_home}
if (!(Test-Path runtime/oreon/xervexl-oreon.jar)) { & .\build-oreon.ps1; if($LASTEXITCODE){throw 'Oreon build failed'} }
& $Compiler -std=c++20 -O2 -Wno-misleading-indentation -static -Isrc tools/export_combat_geometry.cpp -o build/export_combat_geometry.exe
if ($LASTEXITCODE) { throw "Collision pose export build failed" }
& .\build\export_combat_geometry.exe assets/combat_geometry.json
if ($LASTEXITCODE) { throw "Collision pose export failed" }
python tools/make_shaders.py
if ($LASTEXITCODE) { throw "Shader assembly failed" }
if (!(Test-Path shaders/arena.vert.spv) -or !(Test-Path shaders/arena.frag.spv)) { throw "Compile shaders using glslang first." }
& $Compiler -std=c++20 -O2 -Wall -Wextra -Wno-missing-field-initializers -Wno-misleading-indentation -static -mwindows -Isrc -Ivendor ('-I'+$JavaHome+'/include') ('-I'+$JavaHome+'/include/win32') src/main.cpp -o $OutputPath -lopengl32 -lgdi32 -lwinhttp -lwinmm -luser32 -lcrypt32
if ($LASTEXITCODE) { throw "C++ build failed" }
if (!$ReuseAudio) {
    python tools/make_audio.py
    if ($LASTEXITCODE) { throw "Audio generation failed" }
}
Write-Host "Built $OutputPath. Run Play-Xervexl.cmd to play."
