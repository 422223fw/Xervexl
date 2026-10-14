$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$outputRoot = Join-Path $PSScriptRoot ("build\portable-release-" + [Guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Path $outputRoot, "$outputRoot\build", "$outputRoot\shaders", "$outputRoot\assets", "$outputRoot\vendor" -Force | Out-Null
Copy-Item build/Xervexl.exe "$outputRoot\build"
Copy-Item server.py, rules.py, combat.py, arena_features.py, bot_brain.py, bot_learning.py, start.ps1, Play-Xervexl.cmd, README.md, SCORING.md, THIRD_PARTY.md, VALIDATION.md, project.json, accounts.example.json $outputRoot
Copy-Item shaders/*.spv "$outputRoot\shaders"
Copy-Item assets/*.wav "$outputRoot\assets"
Copy-Item vendor/JSON-LICENSE.txt, vendor/VULKAN-LICENSE.md "$outputRoot\vendor"
Compress-Archive -Path "$outputRoot\*" -DestinationPath build/Xervexl-Windows.zip -Force
Write-Host "Packaged build/Xervexl-Windows.zip (no accounts, credentials, logs or test artifacts)."
