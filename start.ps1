param([switch]$Vulkan, [switch]$OpenGL, [ValidateRange(1024,65503)][int]$Port=8765)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!(Test-Path build/Xervexl.exe)) { throw "Build the game first using build.ps1." }
New-Item -ItemType Directory -Path "$PSScriptRoot\data" -Force | Out-Null
$healthy = $false
$availablePort = $null
$serverAddress = $null
$portFile = Join-Path $PSScriptRoot 'data\local-server.json'
$expectedVersion = (Get-Content "$PSScriptRoot\project.json" -Raw | ConvertFrom-Json).version
$ports = @($Port..($Port+31))
try {
    $savedPort = (Get-Content -LiteralPath $portFile -Raw | ConvertFrom-Json).port
    if ($savedPort -is [int] -and $savedPort -ge $Port -and $savedPort -le ($Port+31)) { $ports = @($savedPort) + @($ports | Where-Object {$_ -ne $savedPort}) }
} catch {}
foreach ($candidatePort in $ports) {
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$candidatePort)
    $probe.Server.ExclusiveAddressUse=$true
    try {
        $probe.Start()
        if ($null -eq $availablePort) { $availablePort=$candidatePort }
        continue
    } catch {} finally { $probe.Stop() }
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:$candidatePort/health" -TimeoutSec 1
        if ($health.name -ne 'Xervexl') { continue }
        if ($health.version -ne $expectedVersion) { throw 'XervexlVersionMismatch' }
        $serverAddress="http://127.0.0.1:$candidatePort"; $healthy=$true; break
    } catch {
        if ($_.Exception.Message -eq 'XervexlVersionMismatch') { throw 'The local Xervexl server is an older version. Restart that server before opening the updated game.' }
    }
}
if (!$healthy) {
    if ($null -eq $availablePort) { throw 'No local game port is available. Select another range with start.ps1 -Port 9000.' }
    $serverAddress="http://127.0.0.1:$availablePort"
    $python = (Get-Command python.exe).Source
    New-Item -ItemType Directory -Path "$PSScriptRoot\data" -Force | Out-Null
    $serverProcess = Start-Process -FilePath $python -ArgumentList @('"' + "$PSScriptRoot\server.py" + '"','--port',"$availablePort") -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\server.log" -RedirectStandardError "$PSScriptRoot\server-error.log" -PassThru
    $serverProcess.Id | Set-Content "$PSScriptRoot\data\server.pid"
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 100
        try {
            $health = Invoke-RestMethod "$serverAddress/health" -TimeoutSec 1
            if ($health.name -eq "Xervexl") { $healthy = $true; break }
        } catch {}
    }
    if (!$healthy) { throw "Local arena server did not start. Read server-error.log." }
}
@{port=[int]([uri]$serverAddress).Port} | ConvertTo-Json | Set-Content -LiteralPath $portFile
$clientArgs = @("--server=$serverAddress")
if ($Vulkan) { $clientArgs += "--vulkan" }
if ($OpenGL) { $clientArgs += "--opengl" }
if ($clientArgs.Count) { Start-Process -FilePath "$PSScriptRoot\build\Xervexl.exe" -ArgumentList $clientArgs }
else { Start-Process -FilePath "$PSScriptRoot\build\Xervexl.exe" }
