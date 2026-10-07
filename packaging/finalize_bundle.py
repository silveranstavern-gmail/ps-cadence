"""Copy licenses and write a verifiable inventory of the final offline payload."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tts_reader.runtime import VERSION, MODEL_REVISION, require_speech_assets

ROOT = Path(__file__).resolve().parents[1]


def main():
    bundle = ROOT / 'dist' / 'Cadence'
    internal = bundle / '_internal'
    require_speech_assets(internal / 'speech-assets')
    if not (internal / 'webview2' / 'msedgewebview2.exe').is_file():
        raise RuntimeError('Fixed WebView2 runtime was not bundled.')
    licenses = bundle / 'licenses'
    licenses.mkdir(exist_ok=True)
    inventory = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
        name = dist.metadata['Name']
        if name.lower() in ('pip', 'pytest', 'iniconfig', 'pluggy'):
            continue
        files = []
        for entry in dist.files or []:
            if not any(part.lower().startswith(('license', 'copying', 'notice', 'copyright')) for part in entry.parts):
                continue
            source = Path(dist.locate_file(entry))
            if not source.is_file():
                continue
            relative = Path(*[p for p in entry.parts if p not in ('..', '.')])
            target = licenses / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            files.append(target.relative_to(bundle).as_posix())
        inventory.append({'name': name, 'version': dist.version,
                          'license_expression': dist.metadata.get('License-Expression'),
                          'license_classifiers': [c for c in dist.metadata.get_all('Classifier', []) if 'License' in c],
                          'license_files': files})
    for name in ('LICENSE', 'DISTRIBUTION.txt', 'THIRD_PARTY_NOTICES.txt'):
        shutil.copyfile(ROOT / name, bundle / name)
    # This component also ships a native GPL library; keep its license visible
    # even when the wheel's dist-info omitted the upstream COPYING file.
    extra = ROOT / 'packaging' / 'licenses'
    if extra.is_dir():
        shutil.copytree(extra, licenses / 'upstream', dirs_exist_ok=True)
    manifest = {'product': 'P.S. | Cadence', 'version': VERSION, 'platform': 'Windows 11 x64',
                'python': sys.version, 'model_revision': MODEL_REVISION,
                'webview2': '154.0.4258.53', 'offline': True, 'dependencies': inventory}
    (internal / 'release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    records = {}
    for path in sorted(bundle.rglob('*')):
        if path.is_file() and path.name != 'SHA256SUMS.json':
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            records[path.relative_to(bundle).as_posix()] = {'bytes': path.stat().st_size, 'sha256': digest}
    (bundle / 'SHA256SUMS.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print(f'Offline bundle: {len(records)} files, {sum(r["bytes"] for r in records.values()):,} bytes')


if __name__ == '__main__':
    main()
