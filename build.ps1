param([switch]$Cpu, [switch]$SkipInstaller, [string]$CompilerPath)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$environmentDir = if ($Cpu) { '.venv-cpu' } else { '.venv-release' }
$readerPython = Join-Path $PSScriptRoot "$environmentDir\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $readerPython)) {
    if ($Cpu) { & "$PSScriptRoot\setup.ps1" -Cpu }
    else { & "$PSScriptRoot\setup-release.ps1" }
}
$readerCheckArgs = @('packaging\check_environment.py')
if ($Cpu) { $readerCheckArgs += '--cpu' }
& $readerPython @readerCheckArgs
if ($LASTEXITCODE -ne 0) { throw 'The build environment does not match the release lock. Run setup-release.ps1.' }
& npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Installing interface build dependencies failed.' }
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Building the interface failed.' }
& "$PSScriptRoot\prepare-runtime.ps1" -PythonPath $readerPython
# PyInstaller's --noconfirm replaces its output folder. Validate every target
# before allowing the build to remove previous generated files.
$readerProjectRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
foreach ($readerRelative in @('dist', 'dist\Cadence', 'build', 'build\offline')) {
    $readerTarget = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $readerRelative))
    if (-not $readerTarget.StartsWith($readerProjectRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Build target is outside the project: $readerTarget"
    }
    if ((Test-Path -LiteralPath $readerTarget) -and ((Get-Item -LiteralPath $readerTarget).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Build target must not be a directory link: $readerTarget"
    }
}
& $readerPython -m PyInstaller --noconfirm --clean --distpath dist --workpath build\offline reader.spec
if ($LASTEXITCODE -ne 0) { throw 'Packaging Cadence failed.' }
& $readerPython packaging_resources.py
if ($LASTEXITCODE -ne 0) { throw 'Copying runtime resources failed.' }
& $readerPython packaging\finalize_bundle.py
if ($LASTEXITCODE -ne 0) { throw 'Finalizing the release failed.' }
if (-not $SkipInstaller) {
    if (-not $CompilerPath) { $CompilerPath = Join-Path $PSScriptRoot '.build-tools\inno7\ISCC.exe' }
    if (-not (Test-Path -LiteralPath $CompilerPath)) {
        throw 'Install the Inno Setup compiler and pass -CompilerPath PATH. The offline app folder is ready in dist\Cadence.'
    }
    & $CompilerPath /Qp packaging\cadence.iss
    if ($LASTEXITCODE -ne 0) { throw 'Compiling the installer failed.' }
    Get-ChildItem dist\installers -Filter '*.exe' | ForEach-Object {
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        [IO.File]::WriteAllText($_.FullName + '.sha256', "$hash  $($_.Name)`n")
    }
}
Write-Output 'Ready: dist\Cadence\Cadence.exe and dist\installers. No runtime downloads are required.'
