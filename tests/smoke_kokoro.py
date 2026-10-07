"""Optional real-model verification (downloads missing model assets)."""
import argparse
import json
import tempfile
import time
from pathlib import Path

from tts_reader.engine import Engine, SAMPLE_RATE
from tts_reader.text import parse_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', choices=['cpu', 'cuda', 'auto'], default='auto')
    args = parser.parse_args()
    doc = parse_text('Ian opened his eyes. Talent: 3200→3300! Ian said, “Again.”')
    with tempfile.TemporaryDirectory() as directory:
        engine = Engine(Path(directory), device=args.device)
        start = time.perf_counter()
        try:
            waveform, timings = engine.synthesize(doc['chunks'][0], 'bm_lewis')
            duration = len(waveform) / SAMPLE_RATE
            assert len(timings) == len(doc['words'])
            assert len(waveform) > SAMPLE_RATE
            assert all(0 <= t['start'] <= t['end'] <= duration for t in timings)
            assert all(a['start'] <= b['start'] for a,b in zip(timings, timings[1:]))
            number = next(w['id'] for w in doc['words'] if '3200' in w['text'])
            assert not timings[number]['approximate']
            assert timings[number]['end'] > timings[number]['start']
            print(json.dumps({'device': engine.actual_device, 'duration': round(duration, 3),
                'generation_seconds': round(time.perf_counter()-start, 3),
                'words': len(timings), 'approximate': sum(t['approximate'] for t in timings)}))
        finally:
            engine.close()


if __name__ == '__main__':
    main()
