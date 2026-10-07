param([switch]$Cpu, [switch]$ReuseInstalledTts)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($Cpu -and $ReuseInstalledTts) { throw 'Choose CPU packaging or reuse of your installed TTS environment.' }
$environmentDir = if ($Cpu) { '.venv-cpu' } else { '.venv' }
if (-not (Test-Path -LiteralPath "$environmentDir\Scripts\python.exe")) {
    $venvArgs = @('-m', 'venv')
    if ($ReuseInstalledTts) { $venvArgs += '--system-site-packages' }
    $venvArgs += $environmentDir
    & python @venvArgs
    if ($LASTEXITCODE -ne 0) { throw 'Creating the Python environment failed. Install Python 3.11 first.' }
}
$readerPython = Join-Path $PSScriptRoot "$environmentDir\Scripts\python.exe"
& $readerPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Updating pip failed.' }
if ($Cpu) {
    & $readerPython -m pip install 'torch==2.5.1' --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'Installing the CPU speech runtime failed.' }
}
$readerRequirements = if ($Cpu -and (Test-Path -LiteralPath 'requirements-cpu.lock.txt')) { 'requirements-cpu.lock.txt' } else { 'requirements.txt' }
& $readerPython -m pip install -r $readerRequirements
if ($LASTEXITCODE -ne 0) { throw 'Installing reader dependencies failed.' }
& npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Installing frontend build dependencies failed.' }
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Building the reader interface failed.' }
Write-Output "Ready. Python environment: $environmentDir"
