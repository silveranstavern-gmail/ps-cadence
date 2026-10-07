$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv-release\Scripts\python.exe')) {
    & python -m venv .venv-release
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 x64 on the build machine.' }
}
$readerPython = Join-Path $PSScriptRoot '.venv-release\Scripts\python.exe'
& $readerPython -m pip install 'pip==25.3'
if ($LASTEXITCODE -ne 0) { throw 'Installing pinned pip failed.' }
& $readerPython -m pip install -r requirements-nvidia.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Installing the locked release dependencies failed.' }
& $readerPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Release dependencies are inconsistent.' }
Write-Output 'Isolated NVIDIA + CPU release environment is ready.'
