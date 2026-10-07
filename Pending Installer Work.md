# Pending Installer Work

This is the handoff checklist for finishing the P.S. | Cadence Windows 11
installer. Follow `How to ensure changes to core app are included in the
installer.md` for every app or packaging change. Update this checklist with
evidence as work is completed; do not infer a pass from an older release.

## Product requirements to preserve

- One complete offline installer: download, install, launch from Start menu.
- Windows 11 x64 on Intel/AMD hardware; ARM64 is currently excluded.
- No customer-installed Python, PyTorch, CUDA toolkit, voice downloads, developer
  tools, accounts, or online activation.
- All six voices, model, pronunciation resources, NVIDIA/CPU runtime libraries,
  and fixed WebView2 are included. Acceleration uses a compatible system NVIDIA
  display driver. CPU use remains possible without NVIDIA acceleration.
- Bundled versions remain fixed until a deliberate app release updates them.
  Windows and display drivers are system components, outside that guarantee.
- Updates and uninstall preserve the customer's reading library and audio.
- Do not introduce a downloader or mandatory online license check to reduce size
  or add monetization without an explicit product decision.

## Completed baseline: 0.2.0 unsigned engineering preview

The current artifact is
`dist/installers/Cadence-0.2.0-Windows11-x64-Offline-Setup.exe`.
It is 2,851,537,232 bytes (2.85 GB); its application payload is approximately
6.3 GB before user audio caches. SHA-256:

```text
ac96102e3bcbf2ec24c76d20f295b381dfde45f1695c3179ab5c7eebbc07439c
```

Evidence: `dist/verification/Cadence-0.2.0.json`, with references to detailed
local test reports. Generated evidence and build artifacts are ignored by Git;
preserve them separately when handing this work to another machine.

- [x] Full offline payload and one-file installer built with Inno Setup 7.1.0 x64.
- [x] Isolated locked release environment, model pin, browser archive checksum,
  component manifest, license notices, and payload checksums implemented.
- [x] 30 source tests and the TypeScript/Vite build passed.
- [x] All six voices passed GPU and simulated CPU-only checks with empty download
  caches, developer paths removed, unavailable proxies, and the app's Python
  external-network guard.
- [x] Actual bundled browser window and installed desktop passed.
- [x] Installer, reinstall, and uninstall passed in an isolated directory with
  spaces, a comma, and an accented character; the test library was preserved.

These checks used Windows 11 Home build 26200 on the development computer with
an RTX 3060 Laptop GPU. They do not establish clean-machine compatibility,
compatibility with all NVIDIA cards, or readiness for proprietary commercial sale.

## Release blockers: complete before public sale

### 1. Resolve licensing and corresponding-source obligations

**Owner:** product owner with appropriate licensing advice; an agent can inventory
components and prepare the chosen implementation/documentation.

Read `THIRD_PARTY_NOTICES.txt`, `packaging/licenses/`, and the generated
`dist/Cadence/_internal/release-manifest.json`. The speech process currently loads
GPL components, including phonemizer-fork and eSpeak NG. Merely copying license
text into the installer does not resolve all combined-work or source obligations.

- [x] Decide the intended distribution/license model. Decision (2026-10-07):
  Cadence is released under GPL-3.0-or-later (`LICENSE`) and sold as a GPL
  application, keeping eSpeak NG and phonemizer-fork. Remaining work is to
  deliver Corresponding Source for each sold binary and finish the inventory.
- [ ] Review the complete bundled dependency inventory, including native
  Microsoft/NVIDIA libraries, model/voice assets, and libsndfile.
- [ ] Implement the chosen path: fulfill applicable license/source obligations,
  or replace incompatible components and revalidate pronunciation, timing, audio,
  offline operation, and redistribution rights.
- [ ] Prepare required license documents, notices, source/build materials and
  delivery mechanism for the exact binaries being distributed.

**Done when:** the owner records the approved distribution approach and its
requirements, and those requirements are fulfilled for the release artifact.
Do not mark this complete just because a license inventory exists.

### 2. Implement production signing

**Owner:** owner supplies an appropriate signing identity/service; an agent
implements the build integration without committing credentials.

The current build does not sign the app, installer, or generated uninstaller.

- [ ] Provision the owner's signing identity and secure credential access.
- [ ] Add a release signing stage for the application after PyInstaller/resource
  staging and before generating the final payload checksum inventory.
- [ ] Configure installer compilation/signing so the installer and generated
  uninstaller receive the intended production signatures. Check the installed
  uninstaller as well as the outer setup EXE.
- [ ] Preserve vendor signatures on third-party binaries. Use timestamping and
  verify signatures using the chosen signing provider's documented procedure.
- [ ] Generate the installer SHA-256 after all signing. Repeat lifecycle tests
  against the final signed EXE and retain signature verification evidence.

**Done when:** final app, installer and uninstaller signatures verify with the
intended publisher, hashes match final bytes, and final-artifact tests pass.
Signing is not a promise that a new publisher will never trigger SmartScreen.

### 3. Prove the clean-computer customer workflow

**Owner:** tester with a clean Windows 11 x64 VM or spare machine. Do not uninstall
developer tools or drivers from the owner's working computer to simulate this.

- [ ] Prepare a standard Windows user with no Python, Node, CUDA toolkit,
  developer environment, model cache, or Cadence installation. Use a clean image;
  hiding PATH entries on the development computer is insufficient.
- [ ] Transfer only the final installer and optional checksum, then disconnect
  networking before installation. Record Windows build and available system
  runtimes. Ensure the app uses its bundled WebView2, even if the OS has another.
- [ ] Install through the normal visible wizard without administrator elevation,
  launch from Start menu, and confirm no dependency/account prompts occur.
- [ ] Import TXT and Markdown, play every voice, seek, change voice and playback
  speed, prepare audio, export a non-silent WAV, and reopen the app.
- [ ] Confirm saved readings, position and preferences survive reopening.
- [ ] Reinstall/upgrade using the normal default data directory
  `%LOCALAPPDATA%\TTSReader`; confirm library and generated audio survive.
- [ ] Uninstall through Windows Settings, verify installed files/shortcuts and
  registration are removed, confirm user data remains, then reinstall and confirm
  the existing library is usable. Do this on a test account with test readings.
- [ ] Include an account/path containing spaces and non-ASCII characters; test
  both the default install location and an intentionally changed location.
- [ ] Record cold launch/first speech time, installation time, disk requirements,
  visible errors, and logs. Fix discovered issues and repeat affected checks.

**Done when:** the final installer passes disconnected on a clean Windows 11
computer without adding a runtime manually. Record failures as packaging bugs;
do not solve them by telling customers to install Python or developer tools.

### 4. Validate and publish the supported hardware envelope

**Owner:** tester with the required hardware; an agent can add targeted checks
and improve errors/fallback behavior.

- [ ] Test a physically non-NVIDIA/driver-free computer for automatic CPU use.
  Current CPU evidence only hides CUDA on a machine with a working driver.
- [ ] Test representative supported NVIDIA cards/drivers, including the oldest
  combination to be advertised and newer architectures to be advertised. Bundled
  CUDA libraries and compiled GPU architectures alone do not prove compatibility.
- [ ] Exercise insufficient VRAM/unavailable GPU cases. Verify successful CPU
  fallback or an actionable user-facing error; no hangs or technical setup steps.
- [ ] Establish supported driver, RAM, VRAM, storage, and Windows requirements
  from evidence. Record cold and warm timing using a consistent passage, and do
  not advertise development-machine timings as universal guarantees.

**Done when:** the published support claims match tested configurations and the
fallback/error behavior is validated on the final artifact.

## Release engineering work

These tasks make future releases less error-prone. Complete the release record
and archive before publishing; scope the automation improvements separately.

- [ ] **Preserve build inputs.** Archive the source snapshot, Python installer,
  exact dependency wheels (including the spaCy model), npm package inputs,
  compiler installer, pinned model/voices, fixed browser archive, licenses and
  hashes in durable storage. `vendor/` and the current virtual environment alone
  are not a complete portable build kit. The current app works offline, but
  `build.ps1` still invokes npm and staging operations that can access upstreams.
  To claim offline rebuilding, add a local-input build path and demonstrate a
  build without network access. Pinned versions do not ensure upstream survival
  or byte-for-byte reproducible output.
- [ ] **Make release evidence automatic.** Record source identity, version,
  toolchain, installer hash/size, payload manifest and exact test results after
  each successful build. The current `dist/verification/Cadence-0.2.0.json` was
  assembled separately and is not regenerated by `build.ps1`.
- [ ] **Prevent stale release publication.** Build to a candidate location or
  otherwise make failed builds unmistakable; retain the previous validated
  release separately. A failed command currently can leave old installer files.
- [ ] **Centralize versioning.** Remove or check duplicated version strings
  listed in the rebuild guide. Keep a stable AppId and test an actual version-to-
  version upgrade, including any data migrations, not just same-version reinstall.
- [ ] **Separate CPU-only artifact naming if offered.** `-Cpu` currently writes
  to the same app and installer names as the NVIDIA build. Do not accidentally
  overwrite or label a CPU build as the NVIDIA product. No separate CPU product
  is necessary to finish the requested all-inclusive installer.
- [ ] **Improve lifecycle-test portability.** `tests/smoke_installer.py` currently
  hardcodes expected CUDA and the default 0.2.0 filename. Parameterize device and
  version as needed, and add checks of normal LocalAppData preservation and real
  cross-version upgrades. Do not weaken existing assertions to manufacture a pass.
- [ ] **Define dependency maintenance.** Keep the browser/model/runtime fixed
  within a release, but provide deliberate tested replacement releases when
  dependencies need updating. Do not add silent runtime downloads. Preserve
  prior installers so a release can be reproduced and investigated.
- [ ] **Prepare the customer handoff.** Finalize installation/uninstall guidance,
  supported hardware, approximate disk usage plus audio-cache growth, support/log
  collection instructions, final checksum and release notes. Publish only when
  explicitly authorized; building the artifact is not authorization to upload it.

## Handoff record required from the next person or agent

For each completed item, record what changed, the source snapshot, exact artifact
hash, commands/machines used, result and evidence location. For any blocked item,
state the specific missing input (for example a signing identity, owner licensing
decision, or clean test machine). Continue independent implementation and tests;
do not silently label an unresolved blocker complete.

The next release is ready for public sale only when the licensing, signing,
clean-machine and advertised-hardware checks above have evidence tied to the
final artifact, and the owner has authorized distribution.
