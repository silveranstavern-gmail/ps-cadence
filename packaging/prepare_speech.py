"""Build-time only: stage immutable Kokoro assets, independent of user caches."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tts_reader.runtime import MODEL_REVISION, VOICE_IDS


def main():
    from huggingface_hub import hf_hub_download
    root = Path(__file__).resolve().parents[1] / 'vendor' / 'speech-assets'
    root.mkdir(parents=True, exist_ok=True)
    files = ['config.json', 'kokoro-v1_0.pth', *[f'voices/{v}.pt' for v in VOICE_IDS]]
    records = {}
    for name in files:
        source = Path(hf_hub_download('hexgrad/Kokoro-82M', name, revision=MODEL_REVISION))
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        with destination.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        records[name] = {'bytes': destination.stat().st_size, 'sha256': digest}
    (root / 'manifest.json').write_text(json.dumps({'repository': 'hexgrad/Kokoro-82M',
        'revision': MODEL_REVISION, 'files': records}, indent=2) + '\n', encoding='utf-8')
    print(f'Staged model and {len(VOICE_IDS)} voices: {root}')


if __name__ == '__main__':
    main()
