param([switch]$Vulkan, [switch]$OpenGL)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!(Test-Path build/Xervexl.exe)) { throw "Build the game first using build.ps1." }
$healthy = $false
$expectedVersion = (Get-Content "$PSScriptRoot\project.json" -Raw | ConvertFrom-Json).version
try {
    $health = Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 2
    $healthy = $health.name -eq "Xervexl"
} catch {}
if ($healthy -and $health.version -ne $expectedVersion) { throw "The local arena server is an older version. Restart server.py before opening the updated game." }
if (!$healthy) {
    $python = (Get-Command python.exe).Source
    New-Item -ItemType Directory -Path "$PSScriptRoot\data" -Force | Out-Null
    $serverProcess = Start-Process -FilePath $python -ArgumentList @('"' + "$PSScriptRoot\server.py" + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\server.log" -RedirectStandardError "$PSScriptRoot\server-error.log" -PassThru
    $serverProcess.Id | Set-Content "$PSScriptRoot\data\server.pid"
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 100
        try {
            $health = Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 1
            if ($health.name -eq "Xervexl") { $healthy = $true; break }
        } catch {}
    }
    if (!$healthy) { throw "Local arena server did not start. Read server-error.log." }
}
$clientArgs = @()
if ($Vulkan) { $clientArgs += "--vulkan" }
if ($OpenGL) { $clientArgs += "--opengl" }
if ($clientArgs.Count) { Start-Process -FilePath "$PSScriptRoot\build\Xervexl.exe" -ArgumentList $clientArgs }
else { Start-Process -FilePath "$PSScriptRoot\build\Xervexl.exe" }
