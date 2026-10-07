# How to ensure changes to core app are included in the installer

This is the release procedure for P.S. | Cadence. It is intended to be followed
by a person or agent without needing the original development conversation.
Commands are PowerShell, run from the `ps-cadence` project directory.

## The rule that prevents stale releases

**Source changes do not update an existing executable or installer.** Finish the
source edits, rebuild the entire package, and test the exact resulting installer.
Do not edit app source while a release build is running. If that happens, discard
that build as a release candidate and start again after the edits are finished.

The build has these separate stages:

| Input | Build step | Output |
| --- | --- | --- |
| `ui/`, `package-lock.json` | `npm ci`, `npm run build` | `ui-dist/` |
| Pinned dependencies | `setup-release.ps1` | Isolated `.venv-release/` |
| Pinned model, voices, browser | `prepare-runtime.ps1` | `vendor/` |
| `app.py`, `tts_reader/`, UI, resources | PyInstaller using `reader.spec` | `dist/Cadence/` |
| Dynamic package resources and fixed browser | `packaging_resources.py` | Completed `dist/Cadence/_internal/` |
| Licenses and component versions | `packaging/finalize_bundle.py` | Notices, release manifest, payload checksums |
| Completed `dist/Cadence/` | Inno Setup using `packaging/cadence.iss` | Offline installer EXE |

`build.ps1` runs these build stages in order, creating the release environment
if missing. Running the installer compiler alone packages whatever app folder
already exists; it does not rebuild Python code or the interface.

## 1. Prepare the build computer

Customers do not need these tools. The build computer needs Windows x64,
Python 3.11 x64, Node.js 22.12+ with npm, and Inno Setup 7.1.0 x64 (the tested
compiler). Ensure `python --version` reports 3.11 before creating environments.
Allow substantial free disk space for environments, staging, output, and test
installations; the installed app alone is approximately 6.3 GB.

```powershell
Set-Location -LiteralPath '<path to your ps-cadence checkout>'
$ErrorActionPreference = 'Stop'
.\setup-release.ps1
if ($LASTEXITCODE -ne 0) { throw 'Release environment setup failed.' }
.\.venv-release\Scripts\python.exe packaging\check_environment.py
if ($LASTEXITCODE -ne 0) { throw 'Release environment check failed.' }
```

Change the project path when working on another computer. The default compiler
location is `.build-tools/inno7/ISCC.exe`. Otherwise supply `-CompilerPath` to the
build command below. Obtain the compiler from its official publisher; the tested
installer and SHA-256 are recorded in `README.md`.

Do not package using the existing development `.venv`, global Python packages,
or `-ReuseInstalledTts`. Release builds use `.venv-release` and
`requirements-nvidia.lock.txt`. Build-time downloads are currently expected;
the finished customer installer and app do not download their dependencies.

## 2. Finish the change and check its packaging inputs

- For Python changes, edit `app.py` or `tts_reader/`. Dynamically imported new
  packages may require hidden imports in `reader.spec`.
- For interface changes, edit `ui/`. Do not hand-edit generated `ui-dist/`.
- For new runtime files, explicitly include them in `reader.spec` or
  `packaging_resources.py`. A file existing in the checkout does not mean it
  will be shipped. Keep private readings, caches, secrets, and test data out.
- For dependency changes, update the release lock deliberately, recreate or
  update the isolated release environment, and recheck licenses. Do not assume
  changing `requirements.txt` changes the NVIDIA release lock.
- For model/voice changes, update the pinned revision and voice definitions in
  `tts_reader/runtime.py`, staging logic, and affected UI/test expectations.
  For browser updates, update the URL, SHA-256, extraction version, and manifest
  version together. Existing `vendor/webview2` is reused by the staging script:
  stage a changed browser into a fresh, verified directory rather than retaining
  the old extracted runtime. Recheck the resulting binary version.
- When speech generation or timing semantics change, consider whether
  `CACHE_VERSION` in `tts_reader/engine.py` needs changing so old generated audio
  does not conceal the change. Do not delete users' libraries to invalidate audio.

For a new distributed release, update the version consistently in:

1. `tts_reader/runtime.py` (`VERSION`).
2. `assets/windows-version.txt` (both numeric tuples and version strings).
3. `packaging/cadence.iss` (`AppVersion`).
4. `package.json` and the corresponding root version fields in `package-lock.json`.
5. `DISTRIBUTION.txt`, current-release README instructions, and test defaults
   referring to the installer filename, particularly `tests/smoke_installer.py`.

Keep the installer `AppId` stable across upgrades. Keep historical verification
records labeled with their original version and hash; do not relabel old evidence.

Run source tests in the development/test environment, not by adding unpinned
tools to the release environment. On this checkout:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Source tests failed.' }
```

On a fresh build machine, prepare a separate test environment first (`setup.ps1`
can create `.venv`; install pytest there if needed). These source tests do not
replace testing the frozen executable.

## 3. Build from fresh packaging intermediates

Close test copies of Cadence that use `dist/Cadence`. The following removes only
generated PyInstaller intermediates after checking the resolved target. It does
not remove source, `vendor`, virtual environments, or reading libraries.

```powershell
$projectRoot = (Get-Location).Path
$intermediatePath = [IO.Path]::GetFullPath((Join-Path $projectRoot 'build\offline'))
# Check the project marker before resolving the generated directory to remove.
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'reader.spec'))) {
    throw 'Run these commands from the ps-cadence project directory.'
}
$expectedPath = Join-Path (Resolve-Path -LiteralPath $projectRoot).Path 'build\offline'
if ($intermediatePath -ne $expectedPath) { throw 'Unexpected cleanup path.' }
if (Test-Path -LiteralPath $intermediatePath) {
    $resolvedPath = (Resolve-Path -LiteralPath $intermediatePath).Path
    if ($resolvedPath -ne $expectedPath) { throw 'Cleanup target resolves elsewhere.' }
    if ((Get-Item -LiteralPath $intermediatePath).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Do not clean a linked build directory.'
    }
    if ((Get-Item -LiteralPath (Join-Path $projectRoot 'build')).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Do not clean through a linked parent directory.'
    }
    Remove-Item -LiteralPath $intermediatePath -Recurse -Force
}
.\build.ps1
if ($LASTEXITCODE -ne 0) { throw 'Release build failed.' }
# Alternatively: .\build.ps1 -CompilerPath 'C:\path\to\ISCC.exe'
```

The script already invokes PyInstaller with `--clean`; the explicit intermediate
cleanup also eliminates retained build artifacts when diagnosing stale code.
Never broadly delete the repository or `%LOCALAPPDATA%\TTSReader`.

For the normal NVIDIA + CPU product, do not pass `-Cpu`. Do not use
`-SkipInstaller` for a finished release. The CPU option currently uses the same
output names and can replace the NVIDIA artifacts. Separate CPU distribution
naming remains pending work.

**Stop on any error.** Old files may still exist after a failed build. Their
existence, or a final informational message by itself, is not proof of success.
Inno Setup 6 previously failed on this payload's size; do not switch back to it.

## 4. Verify the newly built app and the exact installer

Use the current release version in the installer filename. These commands assume
the development Python test runner exists and this host has a compatible NVIDIA
GPU. The test runner is not a customer dependency.

```powershell
$releaseVersion = '0.2.0' # Change for the release being built.
$installerPath = Join-Path $PWD "dist\installers\Cadence-$releaseVersion-Windows11-x64-Offline-Setup.exe"
.\.venv\Scripts\python.exe -m tests.smoke_offline --desktop --expect-device cuda
if ($LASTEXITCODE -ne 0) { throw 'GPU/desktop bundle verification failed.' }
.\.venv\Scripts\python.exe -m tests.smoke_offline --disable-cuda --expect-device cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU bundle verification failed.' }
.\.venv\Scripts\python.exe -m tests.smoke_installer --installer $installerPath
if ($LASTEXITCODE -ne 0) { throw 'Installer lifecycle verification failed.' }
Get-FileHash -LiteralPath $installerPath -Algorithm SHA256
Get-Content -LiteralPath ($installerPath + '.sha256')
```

The lifecycle test currently requires CUDA and refuses to run if Cadence is
already registered as installed for the current user. Use a separate test account;
do not remove a real installation's registration to bypass that check. It tests an
isolated install, actual desktop, six voices, reinstall, and uninstall. It checks
a test library outside the installation directory; default LocalAppData library
preservation also needs the manual checks in `Pending Installer Work.md`.

On a CPU-only host, run the CPU bundle check, then perform the CPU clean-machine
procedure in the pending-work guide. Do not mark the GPU check passed or remove
its expectation merely to make a test green.

**Verify the specific change as well.** Generic smoke tests cannot establish
that a new button, corrected behavior, or new resource made it into the installer.
Install the exact EXE in a test account and reproduce the change's acceptance
case there. Launch the installed shortcut/executable, not `Start Reader.cmd`,
`app.py`, an old shortcut, or `dist/Cadence/Cadence.exe`. Use new input or an
isolated data directory when an existing audio cache could hide a speech change.

## 5. Record and hand off the release

Record the source commit (or an explicit source snapshot identifier), version,
build completion, exact installer path, byte size, SHA-256, test report paths,
change-specific installed-app result, and outstanding limitations. Reports are
written under `.reader-data/offline-verification/` and
`.reader-data/installer-verification/`.

`dist/verification/Cadence-0.2.0.json` describes the original preview only. The
build script does not regenerate that summary. Write new evidence for each new
artifact, even when rebuilding under the same version. Signing changes bytes:
follow the signing order in `Pending Installer Work.md`, then compute final hashes
and verify the final signed artifact.

The deliverable is the complete installer EXE plus its optional checksum, not a
small downloader. For a portable delivery, ship the entire `dist/Cadence` directory;
`Cadence.exe` alone is insufficient. Do not publish until the release blockers in
the pending-work guide are complete.
