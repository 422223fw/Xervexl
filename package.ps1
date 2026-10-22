$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python package-release.py
if ($LASTEXITCODE) { throw 'Public runtime/source packaging failed.' }
