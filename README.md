# P.S. | Cadence

A local Windows reader with Kokoro speech, a sepia reading surface, clickable words,
sentence or visible-line highlighting, Markdown imports, and persistent audio caching.
All project files are inside this folder.

The desktop title, reading header, and browser tab use **P.S. | Cadence**, with a
matching book-and-waveform icon for the window, taskbar, and executable. The existing
source launcher and `%LOCALAPPDATA%\TTSReader` data directory stay compatible
with earlier versions, preserving saved readings, positions, and audio. Version 0.2.0
uses `Cadence.exe` for the installed application.

## Install the complete offline application

Run **dist\installers\Cadence-0.2.0-Windows11-x64-Offline-Setup.exe**, then open
**P.S. Cadence** from the Start menu. The installer includes Python, the NVIDIA/CPU
speech engine, model, all six voices, pronunciation resources, and a fixed WebView2
runtime. No developer tools, account, online activation, or first-use downloads are
required. It installs for the current user without administrator permission.
The 0.2.0 NVIDIA + CPU installer is a single 2.85 GB download and needs about
6.3 GB after installation, plus space for saved readings and generated audio.

Target: Windows 11 x64 on Intel/AMD hardware. ARM64 is not supported. NVIDIA
acceleration uses bundled CUDA 12.8 libraries and a compatible system display driver;
CPU operation is available automatically. GPU runtime failures retry the current
passage on CPU and keep using CPU for that session.

The complete **dist\Cadence** folder also runs directly via `Cadence.exe`.
Keep `_internal` and the other supporting files beside it. The portable folder
still stores the library in LocalAppData. Updating or uninstalling keeps that library.

This engineering preview is unsigned. Before commercial distribution, fulfill the
GPL corresponding-source obligations described in `THIRD_PARTY_NOTICES.txt`,
sign the release, and complete clean-machine and supported-GPU validation.

## Run on this computer

Double-click **Start Reader.cmd**. The prepared `.venv` reuses this computer's existing
Kokoro/PyTorch CUDA installation, and the interface has already been built.

Choose **Open file** and select a `.txt` or `.md` file, or drag it into the window.
**From clipboard** replaces the current reading with copied plain text. Empty or non-text
clipboard contents leave the current reading in place. Filenames stay in the
recent list rather than appearing above the reading text.
**Manage**, beside Recent texts, shows previews to distinguish similarly named entries.
Remove individual entries or use **Clear list** to clear the entire history, including
older entries beyond the dropdown's 20-item limit. This keeps the current reading,
saved positions, original files, and audio. Opening or importing a text again adds it back.
**Play** prepares the selected passage first and the rest of the text in the background.
Its spinner shows while audio is loading; press it again to pause during preparation.
Click a word to seek; a paused reader stays paused, and a playing reader continues.
**Back** and **Skip** jump by the focused sentence or visible line.
**Prepare audio** generates and saves all speech without starting playback. Use it to
prepare uninterrupted listening or enable export; Play does not require this extra step.
**Reload** rereads a file opened through the native desktop picker. Changed content becomes a
new reading, so a reused `input.txt` does not inherit the old text's position.

**Aa** changes font size, spacing, volume, and automatic following. **Highlight spoken word**
is off by default, leaving only sentence highlighting; enable it for a burgundy word color
without a word background. **Dim surrounding text** optionally softens text outside the
focused sentence or line into a muted sepia tone and is also off by default. With word
highlighting enabled, other focused words use a brown between normal ink and dimmed text.
**Highlight one line at a time** switches to visible lines; off uses sentences. Sentences
longer than 600 characters, 80 words, or the available reading height automatically use
lines. The mode label explains when this fallback is active. Lines adapt to window width,
font size, and spacing. All options apply immediately without changing playback or seeking;
voice, playback rate, appearance, and per-text word position are saved. **Export WAV** is available when every
passage is ready. Its global word timing JSON is also saved in the app data exports folder.

Keyboard: Space plays/pauses; left/right arrows move by sentence or line; Ctrl+O opens a file.
When a text control or button has focus, its normal keyboard behavior takes precedence.

```powershell
# Open a text file immediately.
.\launch.ps1 -InputFile 'C:\path\to\input.txt'

# Browser fallback, or diagnostic GPU/CPU selection.
.\.venv\Scripts\python.exe app.py --browser
.\.venv\Scripts\python.exe app.py --device cpu
```

## Setup elsewhere

For source development, use Python 3.11, Node 22.12+ and Windows WebView2 Runtime.
`setup.ps1` creates an isolated Python environment and builds the interface.
Use `setup.ps1 -ReuseInstalledTts` only when you intentionally want to reuse an existing TTS setup.
For a CPU-only environment, use `setup.ps1 -Cpu` and `launch.ps1 -Cpu`.
Run `prepare-runtime.ps1 -PythonPath .\.venv\Scripts\python.exe` to stage the pinned
model, voices, and browser for source runs. This is a build/development operation;
the application itself never downloads speech assets. First generation loads the
local model and can take longer than later passages.

## Distribution

Maintainer guides:

- [How to ensure changes to core app are included in the installer](<How to ensure changes to core app are included in the installer.md>)
- [Pending Installer Work](<Pending Installer Work.md>)

```powershell
# Create the isolated, locked NVIDIA + CPU build environment.
.\setup-release.ps1
# Build a complete installer using Inno Setup 7.1.0 x64.
.\build.ps1
# Or pass -CompilerPath 'C:\path\to\ISCC.exe'.
# -SkipInstaller builds the complete app folder only.
# -Cpu uses the separate CPU environment for a smaller optional build.
```

Build dependencies are pinned in `requirements-nvidia.lock.txt`; release builds
reject environments that inherit global packages. Build-time downloads are allowed.
Inno Setup 7 is required for the NVIDIA payload's single EXE size. The tested compiler
is the official `innosetup-7.1.0-x64.exe` (SHA-256
`0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f`).
The model is pinned to revision `f3ff3571791e39611d31c381e3a41a3af07b4987` and
WebView2 to `154.0.4258.53`, with the Microsoft archive SHA-256 checked before use.
Keep `vendor/` and the build environment if you want to retain local build inputs.

The frozen app loads explicit model/voice paths, sets offline library flags, and
denies external Python socket connections while allowing the loopback UI service.
The packaged browser does not self-update. Windows and drivers remain system
components. A future app release is how bundled dependencies are updated.

`dist\Cadence\SHA256SUMS.json` inventories the complete payload;
`_internal\release-manifest.json` records the component versions, and `licenses/`
contains the available component notices. The installer gets a companion SHA-256
file. The bundle includes `demo.txt`, not the developer's reading library or sample novel.
Older `TTSReader` 0.1.0 artifacts are historical builds and are not offline releases.

## Files and behavior

- UI: TypeScript and CSS in `ui/`, built with Vite into `ui-dist/`.
- Desktop entry point: `app.py`, using pywebview/WebView2 and a loopback-only Flask service.
- TTS: one inference worker with a warm shared Kokoro model; auto-selects CUDA when available.
- Readings/settings: `%LOCALAPPDATA%\TTSReader\library.sqlite3`.
- Audio: `%LOCALAPPDATA%\TTSReader\audio`, keyed by passage text, voice and cache format.
- Logs and exported WAV/timing companions: the same app data directory.
- `--data-dir PATH` keeps test data separate. `--no-open --port PORT` runs the local service.

The reader accepts UTF-8, UTF-16 with BOM, and Windows-1252 `.txt` and `.md` files.
Empty text, binary content, and files over 5 MB are rejected. Plain text retains its source
whitespace, while the reading view treats single newlines inside a paragraph as spaces so
hard-wrapped prose reflows with text size and window width. Blank lines still separate
paragraphs; isolated `===` paragraph separators are omitted from speech. English voices
supply word timing tokens; pronunciation expansion and punctuation are mapped back to
visible word IDs. Missing timings
are flagged as approximate and seek to a neighboring spoken boundary.

Markdown is parsed into clean reading text before both display and speech. Headings,
paragraphs, lists, block quotes, link labels, image descriptions, inline code text, and
table cells remain readable. Formatting markers, task checkboxes, link/image destinations,
closed YAML front matter, fenced/indented code blocks, and script/style content are omitted.
HTML is reduced to text and never rendered or executed; no linked assets are downloaded.
Malformed or unsupported Markdown preserves its readable literal content rather than
silently losing prose. This is a reading view, not a full Markdown preview. Imports with
no remaining readable text fail gracefully and leave the current reading unchanged.

Changing playback speed does not regenerate speech. A changed voice uses a separate cache.
Seeking supersedes queued generation and finishes any current inference safely. Short audio
files play consecutively; a small transition pause can occur between passages. Word timings
come from Kokoro's predicted durations and can need perceptual refinement for unusual text.
Cache retention is currently manual; there is no automatic eviction or folder queue.
Pronunciation dictionaries and EPUB import are follow-up features.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
npm run build
.\.venv\Scripts\python.exe -m tests.smoke_kokoro --device cuda
.\.venv\Scripts\python.exe -m tests.smoke_bundle
.\.venv\Scripts\python.exe -m tests.smoke_offline --desktop --expect-device cuda
.\.venv\Scripts\python.exe -m tests.smoke_offline --disable-cuda --expect-device cpu
.\.venv\Scripts\python.exe -m tests.smoke_installer
```

The tests exercise source-word mapping, numeric subtokens, Unicode imports, bookmark
restoration, changed-file reloads, cache persistence, seek priority, repeated passages,
local API authentication, audio byte ranges, full-text export, Markdown conversion,
malformed/empty/binary imports, settings persistence, and existing-library migration. The worker tests use
synthetic waveforms to make concurrency deterministic; actual Kokoro audio is tested separately.
The offline smoke test uses the frozen executable, fresh Hugging Face/Torch caches,
a PATH without developer tools, unavailable HTTP proxies, all six voices, word
timings, byte-range audio, and WAV export. The desktop check verifies the actual
fixed-runtime window and its loaded interface. This is not a substitute for
testing on a disconnected, clean Windows 11 machine without Python or a GPU driver.
The installer lifecycle test installs into an isolated path containing spaces,
commas, and an accented character, runs the desktop and six-voice check, reinstalls,
and uninstalls while checking that the reading library is preserved. It refuses
to run if Cadence is already registered as installed for the current Windows user;
use a separate test account in that case.

## Support

If P.S. | Cadence is useful to you, you can support its development:

- [Donate with Stripe](https://donate.stripe.com/eVa4hvd8sfNx0Pm4gg)
- [Donate with PayPal](https://www.paypal.com/donate/?business=5XBKNVSRQXEYU&no_recurring=0&currency_code=USD)

More ways to help are on the [Pondering Silver support page](https://ponderingsilver.com/support/).

## License

Copyright (C) 2026 Pondering Silver.

P.S. | Cadence is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. It is distributed WITHOUT ANY WARRANTY; see [LICENSE](LICENSE) for details.

Third-party components keep their own licenses; see `THIRD_PARTY_NOTICES.txt`.
