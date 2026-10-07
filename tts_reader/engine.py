"""One warm model, one inference worker, persistent passage cache."""
from __future__ import annotations

import hashlib
import heapq
import json
import logging
import threading
import time
from pathlib import Path

from .text import align_tokens
from .runtime import VOICE_IDS, configure_offline, require_speech_assets, speech_root

log = logging.getLogger(__name__)
SAMPLE_RATE = 24_000
CACHE_VERSION = 'kokoro-0.9.4-reader-1'


class Engine:
    def __init__(self, directory: Path, device='auto', synthesizer=None, assets: Path | None = None):
        self.directory = directory.resolve() / 'audio'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.device = device
        self.actual_device = None
        self.device_notice = ''
        self.assets = assets or speech_root()
        self._cpu_fallback = False
        self._attempted_device = None
        self.pipelines = {}
        self.voice_packs = {}
        self.synthesizer = synthesizer
        self.condition = threading.Condition(threading.RLock())
        self.queue, self.queued, self.jobs = [], set(), {}
        self.sequence = 0
        self.epoch = 0
        self.closed = False
        self.worker = threading.Thread(target=self._work, name='kokoro-worker', daemon=True)
        self.worker.start()

    @staticmethod
    def key(chunk: dict, voice: str) -> str:
        return hashlib.sha256(f'{CACHE_VERSION}\0{voice}\0{chunk["text"]}'.encode('utf-8')).hexdigest()

    def cached(self, key: str) -> dict | None:
        path = self.directory / f'{key}.json'
        if not path.is_file() or not (self.directory / f'{key}.wav').is_file():
            return None
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            return None

    def snapshot(self, document: dict, voice: str) -> dict:
        chunks = []
        for chunk in document['chunks']:
            key = self.key(chunk, voice)
            cached = self.cached(key)
            with self.condition:
                job = dict(self.jobs.get(key, {'status': 'idle'}))
            item = {'index': chunk['index'], 'word_start': chunk['word_start'], 'word_end': chunk['word_end'],
                    'key': key, **job}
            if cached:
                item.update(status='ready', duration=cached['duration'],
                            timings=[{**t, 'word': t['local_word'] + chunk['word_start']} for t in cached['timings']],
                            url=f'/api/audio/{key}')
            chunks.append(item)
        return {'chunks': chunks, 'device': self.actual_device or self.device, 'device_notice': self.device_notice,
                'ready': sum(c['status'] == 'ready' for c in chunks), 'total': len(chunks)}

    def prepare(self, document: dict, voice: str, start_chunk: int):
        if not 0 <= start_chunk < len(document['chunks']):
            raise ValueError('Invalid passage.')
        # A seek supersedes queued work. An in-flight inference completes atomically.
        with self.condition:
            self.epoch += 1
            for key in self.queued:
                if self.jobs.get(key, {}).get('status') == 'queued':
                    self.jobs.pop(key, None)
            self.queue.clear()
            self.queued.clear()
            order = list(range(start_chunk, len(document['chunks']))) + list(range(start_chunk))
            for priority, n in enumerate(order):
                chunk = document['chunks'][n]
                key = self.key(chunk, voice)
                if key in self.queued or self.cached(key) or self.jobs.get(key, {}).get('status') in ('generating', 'loading'):
                    continue
                self.sequence += 1
                heapq.heappush(self.queue, (priority, self.sequence, self.epoch, key, chunk, voice))
                self.queued.add(key)
                self.jobs[key] = {'status': 'queued'}
            self.condition.notify()

    def cancel_pending(self):
        with self.condition:
            for key in self.queued:
                if self.jobs.get(key, {}).get('status') == 'queued':
                    self.jobs.pop(key, None)
            self.queue.clear()
            self.queued.clear()

    def _pipeline(self, voice: str):
        configure_offline()
        require_speech_assets(self.assets)
        from kokoro import KModel, KPipeline
        import spacy.util
        import torch
        if not spacy.util.is_package('en_core_web_sm'):
            raise RuntimeError('Cadence pronunciation files are missing. Reinstall the offline package.')
        if voice not in VOICE_IDS:
            raise ValueError('Unknown voice.')
        lang = voice[0]
        if lang not in self.pipelines:
            if not self.pipelines:
                device = 'cpu' if self._cpu_fallback else self.device
                if device == 'auto':
                    device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self._attempted_device = device
                model = KModel(repo_id='hexgrad/Kokoro-82M', config=str(self.assets / 'config.json'),
                               model=str(self.assets / 'kokoro-v1_0.pth')).to(device).eval()
                self.pipelines[lang] = KPipeline(lang_code=lang, repo_id='hexgrad/Kokoro-82M', model=model)
                self.actual_device = device
            else:
                model = next(iter(self.pipelines.values())).model
                self.pipelines[lang] = KPipeline(lang_code=lang, repo_id='hexgrad/Kokoro-82M', model=model)
        return self.pipelines[lang]

    def synthesize(self, chunk: dict, voice: str) -> tuple:
        try:
            return self._synthesize_once(chunk, voice)
        except RuntimeError:
            if self.device != 'auto' or self._cpu_fallback or self._attempted_device != 'cuda':
                raise
            log.exception('GPU generation failed; retrying this passage on CPU')
        # Leave the exception scope before freeing GPU tensors (the traceback
        # can otherwise keep a failed model allocation alive).
        self.pipelines.clear()
        self._cpu_fallback = True
        self.actual_device = None
        self.device_notice = 'GPU acceleration is unavailable. Cadence is using the CPU.'
        import gc
        import torch
        gc.collect()
        try:
            torch.cuda.empty_cache()
        except RuntimeError:
            pass
        return self._synthesize_once(chunk, voice)

    def _synthesize_once(self, chunk: dict, voice: str) -> tuple:
        import numpy as np
        import torch
        pipeline = self._pipeline(voice)
        if voice not in self.voice_packs:
            self.voice_packs[voice] = torch.load(self.assets / 'voices' / f'{voice}.pt',
                                                  map_location='cpu', weights_only=True)
        arrays, spans, samples, cursor = [], [], 0, 0
        # Token text is retained by Misaki; phoneme expansion does not replace display text.
        comparable = chunk['text'].translate(str.maketrans({'“': '"', '”': '"', '’': "'", '‘': "'"}))
        with torch.inference_mode():
            # Pass a local tensor: Kokoro splits string voice names on commas,
            # which would break a legitimate Windows username/path with a comma.
            for result in pipeline(chunk['text'], voice=self.voice_packs[voice],
                                   speed=1, split_pattern=None):
                if result.audio is None:
                    continue
                audio = result.audio.detach().cpu().numpy()
                offset = samples / SAMPLE_RATE
                for token in result.tokens or []:
                    token_text = token.text.translate(str.maketrans({'“': '"', '”': '"', '’': "'", '‘': "'"}))
                    start = comparable.find(token_text, cursor)
                    if start < 0:
                        log.warning('Unmapped token: %r', token.text)
                        continue
                    cursor = start + len(token_text)
                    if token.start_ts is not None and token.end_ts is not None:
                        spans.append({'char_start': start, 'char_end': cursor,
                                      'start': offset + token.start_ts, 'end': offset + token.end_ts})
                arrays.append(audio)
                samples += len(audio)
        if not arrays:
            raise RuntimeError('Kokoro returned no audio for this passage.')
        waveform = np.concatenate(arrays)
        timings = align_tokens(chunk['local_words'], spans, len(waveform) / SAMPLE_RATE)
        if not any(not t['approximate'] for t in timings):
            raise RuntimeError('Kokoro did not provide word timings. Check the installed English pipeline.')
        return waveform, timings

    def _work(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.queue or self.closed)
                if self.closed:
                    return
                _, _, _, key, chunk, voice = heapq.heappop(self.queue)
                self.queued.discard(key)
                self.jobs[key] = {'status': 'loading' if not self.pipelines and not self.synthesizer else 'generating'}
            began = time.perf_counter()
            try:
                import soundfile as sf
                waveform, timings = (self.synthesizer or self.synthesize)(chunk, voice)
                wav_path = self.directory / f'{key}.wav'
                tmp_path = self.directory / f'{key}.wav.tmp'
                sf.write(tmp_path, waveform, SAMPLE_RATE, format='WAV', subtype='PCM_16')
                tmp_path.replace(wav_path)
                metadata = {'duration': len(waveform) / SAMPLE_RATE, 'timings': timings,
                            'generation_seconds': round(time.perf_counter() - began, 3)}
                json_tmp = self.directory / f'{key}.json.tmp'
                json_tmp.write_text(json.dumps(metadata), encoding='utf-8')
                json_tmp.replace(self.directory / f'{key}.json')
                with self.condition:
                    self.jobs[key] = {'status': 'ready'}
                log.info('Prepared %s: %.1fs audio in %.2fs', key[:8], metadata['duration'], metadata['generation_seconds'])
            except Exception as error:
                log.exception('Speech generation failed')
                with self.condition:
                    self.jobs[key] = {'status': 'error', 'error': str(error)}

    def close(self):
        with self.condition:
            self.closed = True
            self.queue.clear()
            self.condition.notify()
