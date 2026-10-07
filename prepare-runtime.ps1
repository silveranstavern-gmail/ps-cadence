param([string]$PythonPath)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $PSScriptRoot '.venv-release\Scripts\python.exe' }
New-Item -ItemType Directory -Force -Path vendor,vendor\licenses | Out-Null
& $PythonPath packaging\prepare_speech.py
if ($LASTEXITCODE -ne 0) { throw 'Staging the pinned speech assets failed.' }
$readerCab = Join-Path $PSScriptRoot 'vendor\webview2-154.0.4258.53-x64.cab'
$readerCabHash = 'EC12B2DB6423D127FB8E1935D34E2E68ABC70FE8ECB1F6162BA1C1CCC2825F6D'
if (-not (Test-Path -LiteralPath $readerCab)) {
    Invoke-WebRequest 'https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/0b89c3a3-0043-4746-b39e-65830da7744d/Microsoft.WebView2.FixedVersionRuntime.154.0.4258.53.x64.cab' -OutFile $readerCab
}
if ((Get-FileHash -LiteralPath $readerCab -Algorithm SHA256).Hash -ne $readerCabHash) {
    throw 'WebView2 archive checksum mismatch. Do not package it.'
}
$readerVendor = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'vendor'))
$readerExpanded = Join-Path $readerVendor 'webview2-expanded\Microsoft.WebView2.FixedVersionRuntime.154.0.4258.53.x64'
$readerRuntime = Join-Path $readerVendor 'webview2'
if (-not (Test-Path -LiteralPath (Join-Path $readerRuntime 'msedgewebview2.exe'))) {
    New-Item -ItemType Directory -Force (Join-Path $readerVendor 'webview2-expanded') | Out-Null
    & expand.exe $readerCab '-F:*' (Join-Path $readerVendor 'webview2-expanded') | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Extracting WebView2 failed.' }
    foreach ($readerPath in @($readerExpanded, $readerRuntime)) {
        if (-not ([IO.Path]::GetFullPath($readerPath)).StartsWith($readerVendor + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Browser staging path escaped vendor directory.'
        }
    }
    Move-Item -LiteralPath $readerExpanded -Destination $readerRuntime
}
if ((Get-AuthenticodeSignature (Join-Path $readerRuntime 'msedgewebview2.exe')).Status -ne 'Valid') {
    throw 'The bundled WebView2 executable does not have a valid Microsoft signature.'
}
Write-Output 'Pinned speech assets and fixed browser runtime are ready.'
