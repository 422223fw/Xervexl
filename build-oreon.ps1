param([string]$JavaHome="",[string]$Maven="")
$ErrorActionPreference="Stop"
Set-Location $PSScriptRoot
if (!$JavaHome -or !$Maven) {
    $toolFile=Join-Path $PSScriptRoot 'build/java-tools/toolchain.json'
    if (!(Test-Path $toolFile)) { throw 'Supply -JavaHome (JDK 8) and -Maven (mvn.cmd). No administrator installation is needed.' }
    $oreonTools=Get-Content $toolFile -Raw | ConvertFrom-Json
    if (!$JavaHome) {$JavaHome=$oreonTools.java_home};if (!$Maven) {$Maven=$oreonTools.maven}
}
$env:JAVA_HOME=$JavaHome
$oreonOutput=Join-Path $PSScriptRoot 'runtime/oreon'
New-Item -ItemType Directory -Force $oreonOutput,build/oreon-classes,runtime/java | Out-Null
$mavenArgs=@('-B','-Dmaven.repo.local=build/java-tools/m2','-DskipTests','-f','third_party/oreon/oreonengine/pom.xml','-pl','oe-gl-api','-am','install','dependency:copy-dependencies',('-DoutputDirectory='+$oreonOutput))
if(Test-Path build/java-tools/settings.xml){$mavenArgs=@('-s','build/java-tools/settings.xml')+$mavenArgs}
& $Maven @mavenArgs
if($LASTEXITCODE){throw 'Oreon reactor build failed'}
foreach($module in @('oe-core','oe-common-world','oe-gl-api')){Copy-Item "third_party/oreon/oreonengine/$module/target/$module-3.0.0.jar" $oreonOutput -Force}
& "$JavaHome/bin/javac.exe" -encoding UTF-8 -cp "$oreonOutput/*" -d build/oreon-classes oreon-bridge/src/main/java/motlon/xervexl/OreonBridge.java
if($LASTEXITCODE){throw 'Oreon bridge compilation failed'}
& "$JavaHome/bin/jar.exe" cf runtime/oreon/xervexl-oreon.jar -C build/oreon-classes .
if($LASTEXITCODE){throw 'Oreon bridge archive failed'}
Copy-Item "$JavaHome/jre/*" runtime/java -Recurse -Force
Write-Host 'Portable Oreon runtime built.'
