param([string]$InputFile, [switch]$Browser, [switch]$Cpu)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$environmentDir = if ($Cpu) { '.venv-cpu' } else { '.venv' }
$readerPython = Join-Path $PSScriptRoot "$environmentDir\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $readerPython) -or -not (Test-Path -LiteralPath 'ui-dist\index.html')) {
    if ($Cpu) { & "$PSScriptRoot\setup.ps1" -Cpu }
    else { & "$PSScriptRoot\setup.ps1" -ReuseInstalledTts }
}
if ($Browser) {
    $readerArguments = @('app.py', '--browser')
    if ($InputFile) { $readerArguments += @('--input', $InputFile) }
    if ($Cpu) { $readerArguments += @('--device', 'cpu') }
    & $readerPython @readerArguments
    if ($LASTEXITCODE -ne 0) { throw "The reader exited with code $LASTEXITCODE. Check %LOCALAPPDATA%\TTSReader\reader.log." }
} else {
    $readerPythonWindowless = Join-Path $PSScriptRoot "$environmentDir\Scripts\pythonw.exe"
    $readerArguments = @(('"' + (Join-Path $PSScriptRoot 'app.py') + '"'))
    if ($InputFile) { $readerArguments += @('--input', ('"' + $InputFile + '"')) }
    if ($Cpu) { $readerArguments += @('--device', 'cpu') }
    Start-Process -FilePath $readerPythonWindowless -ArgumentList $readerArguments -WorkingDirectory $PSScriptRoot -WindowStyle Normal
}
