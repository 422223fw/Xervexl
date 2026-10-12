param([switch]$Vulkan)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!(Test-Path build/Xervexl.exe)) { throw "Build the game first using build.ps1." }
$healthy = $false
try {
    $health = Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 2
    $healthy = $health.name -eq "Xervexl"
} catch {}
if (!$healthy) {
    $python = (Get-Command python.exe).Source
    Start-Process -FilePath $python -ArgumentList @('"' + "$PSScriptRoot\server.py" + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\server.log" -RedirectStandardError "$PSScriptRoot\server-error.log"
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
if ($clientArgs.Count) { Start-Process -FilePath "$PSScriptRoot\build\Xervexl.exe" -ArgumentList $clientArgs }
else { Start-Process -FilePath "$PSScriptRoot\build\Xervexl.exe" }
