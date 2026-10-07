import './style.css';

type Word = { id: number; text: string; after: string; sentence: number; paragraph: number };
type Chunk = { index: number; word_start: number; word_end: number };
type Reading = { id: string; name: string; format?: 'text' | 'markdown'; words: Word[]; paragraphs: number[][]; chunks: Chunk[]; reloadable: boolean; bookmark: { word: number; offset: number } };
type Timing = { word: number; start: number; end: number; approximate: boolean };
type Job = Chunk & { key: string; status: 'idle'|'queued'|'loading'|'generating'|'ready'|'error'; duration?: number; timings?: Timing[]; url?: string; error?: string };
type Snapshot = { chunks: Job[]; device: string; device_notice?: string; ready: number; total: number };
type Settings = { voice: string; rate: number; fontSize: number; lineHeight: number; follow: boolean; wordHighlight: boolean; dimSurrounding: boolean; highlightMode: 'sentence' | 'line'; volume?: number };
type RecentText = { id: string; name: string; preview: string };
type AppState = { settings: Settings; voices: Record<string,string>; recent: RecentText[] };
declare global {
  interface Window {
    READER_BOOT?: { token: string };
    pywebview?: { api: { open_file(): Promise<Reading | { error: string } | null>; read_clipboard(): Promise<{ text?: string; error?: string }> } };
  }
}

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
<div class="shell">
  <header class="top">
    <div class="brand"><img src="${new URL('./cadence.svg', import.meta.url).href}" alt="" aria-hidden="true" />P.S. | Cadence</div>
    <div class="file-actions"><button id="clipboard">From clipboard</button><button id="open">Open file</button><select id="recent" class="recent" aria-label="Recent texts"><option value="">Recent texts</option></select><button id="manage-recent" class="quiet" aria-label="Manage recent texts" title="Remove recent texts or clear the list">Manage</button><button id="reload" class="quiet" disabled title="Reload a file opened with the desktop file picker">Reload</button><button id="appearance" class="quiet" aria-label="Reading appearance">Aa</button></div>
  </header>
  <section class="toolbar" aria-label="Playback controls">
    <div class="play-actions"><button id="back" disabled title="Previous sentence · Left arrow">↶ Back</button><button id="play" class="primary" disabled title="Play or pause · Space"><span id="play-spinner" class="spinner" aria-hidden="true" hidden></span><span id="play-icon" aria-hidden="true">▶ </span><span id="play-label">Play</span></button><button id="skip" disabled title="Next sentence · Right arrow">Skip ↷</button><button id="prepare" class="quiet" disabled title="Generate and save all audio without starting playback">Prepare audio</button><button id="export" class="quiet" disabled title="Available when all audio is prepared">Export WAV</button></div>
    <div class="voice-actions"><label>Voice <select id="voice" aria-label="Voice"></select></label><label>Speed <select id="rate" aria-label="Playback speed"><option value="0.75">0.75×</option><option value="1">1.0×</option><option value="1.15">1.15×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="1.75">1.75×</option><option value="2">2.0×</option></select></label></div>
  </section>
  <main class="reader-scroll" id="reader-scroll"><div class="drop-hint">Drop a .txt or .md file here</div><article class="page">
    <section id="welcome" class="welcome"><h1>A quieter place to read</h1><p>Open a text or Markdown file, press Play, and follow along. Click any word to listen from there.</p><div class="welcome-actions"><button id="welcome-open" class="primary">Open file</button><button id="sample">Try sample text</button></div><p class="tip">You can also drop a .txt or .md file into the reader.</p></section>
    <div id="chapter" hidden><div class="chapter-meta"><span id="chapter-count"></span><span id="focus-mode">Sentence highlighting</span></div><p id="import-note" class="tip" hidden>Markdown shown as reading text. Formatting, link destinations, metadata, and code blocks are omitted.</p><div id="reading" class="reading" aria-label="Reading text"></div></div>
  </article></main>
  <footer class="bottom"><div class="position-row"><span id="position">No text open</span><span id="clock">0:00</span></div><input id="progress" type="range" min="0" max="1" value="0" aria-label="Reading position" disabled><div class="status-row"><span id="status" role="status">Ready to open text</span><span id="prepared"></span></div></footer>
  <dialog id="settings" class="settings"><div class="settings-header"><h2>Reading appearance</h2><button id="close-settings" aria-label="Close appearance">✕</button></div><label class="settings-field">Text size <output id="font-label"></output><input id="font" type="range" min="16" max="36" step="1"></label><label class="settings-field">Line spacing <output id="spacing-label"></output><input id="spacing" type="range" min="1.3" max="2.4" step="0.05"></label><label class="settings-field">Volume <output id="volume-label"></output><input id="volume" type="range" min="0" max="1" step="0.05" value="1"></label><label class="check"><input id="line-highlight" type="checkbox" aria-describedby="line-highlight-help">Highlight one line at a time</label><p id="line-highlight-help" class="setting-help">Off: highlight sentences, with a line fallback for long sentences. On: follow visible lines as text wraps. Back and Skip follow this setting.</p><label class="check"><input id="word-highlight" type="checkbox" aria-describedby="word-highlight-help">Highlight spoken word</label><p id="word-highlight-help" class="setting-help">Use a subtle burgundy text color for the current word.</p><label class="check"><input id="dim-surrounding" type="checkbox" aria-describedby="dim-surrounding-help">Dim surrounding text</label><p id="dim-surrounding-help" class="setting-help">Soften text outside the focused sentence or line.</p><label class="check"><input id="follow" type="checkbox">Keep the spoken text in view</label><p class="tip">Space: play / pause · ←: previous sentence / line · →: next sentence / line · Ctrl+O: open a file</p><p class="tip">Audio and word timings are saved locally. Changing playback speed reuses the audio.</p></dialog>
  <dialog id="recent-manager" class="settings recent-manager" aria-labelledby="recent-title"><div class="settings-header"><h2 id="recent-title">Recent texts</h2><button id="close-recent" aria-label="Close recent texts">✕</button></div><p class="tip">Remove entries from this list. Your current reading, saved positions, and audio are kept. Opening a text again adds it back.</p><p id="recent-status" class="tip" role="status"></p><ul id="recent-list" class="recent-list"></ul><div class="recent-footer"><button id="clear-recent" class="history-action" disabled>Clear list</button></div></dialog>
  <input type="file" id="file" accept=".txt,.md,text/plain,text/markdown" hidden><audio id="audio" preload="auto"></audio><div class="live-region" id="announcement" aria-live="polite"></div>
</div>`;

const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const audio = el<HTMLAudioElement>('audio');
const settingsDialog = el<HTMLDialogElement>('settings');
const recentDialog = el<HTMLDialogElement>('recent-manager');
let recentEntries: RecentText[] = [];
let recentBusy = false;
let settings: Settings = { voice: 'bm_lewis', rate: 1, fontSize: 23, lineHeight: 1.85, follow: true, wordHighlight: false, dimSurrounding: false, highlightMode: 'sentence', volume: 1 };
let reading: Reading | null = null;
let snapshot: Snapshot | null = null;
let activeWord = 0;
let desiredPlaying = false;
let preparing = false;
let pending: { word: number; offset: number } | null = null;
let loaded: { doc: string; voice: string; chunk: number } | null = null;
let selectionVersion = 0;
let wordNodes: HTMLButtonElement[] = [];
let sentenceNodes = new Map<number, HTMLSpanElement>();
let selectedSentence: number | null = null;
let sentenceBounds = new Map<number, { start: number; end: number; chars: number }>();
let focusRange: { start: number; end: number; line: boolean } | null = null;
let layoutFrame = 0;
let polling = false;
let errorMessage = '';
let endedChapter = false;
let exporting = false;
let savingSettings: ReturnType<typeof setTimeout>;
let latestBookmarkSent = '';

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, { method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Reader-Token': window.READER_BOOT?.token ?? '' },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error ?? `Request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

function fail(error: unknown) {
  errorMessage = error instanceof Error ? error.message : String(error);
  el('status').textContent = errorMessage;
  el('status').classList.add('error');
  el('announcement').textContent = errorMessage;
}

function chunkFor(word: number): number {
  return reading?.chunks.findIndex(c => c.word_start <= word && word < c.word_end) ?? -1;
}

function formatTime(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
}

function paintControls() {
  const loading = desiredPlaying && Boolean(pending || audio.paused || audio.readyState < 3);
  el('play-spinner').hidden = !loading;
  el('play-icon').hidden = loading;
  el('play-icon').textContent = desiredPlaying ? 'Ⅱ ' : '▶ ';
  el('play-label').textContent = desiredPlaying ? 'Pause' : 'Play';
  el('play').setAttribute('aria-busy', String(loading));
  for (const id of ['play', 'back', 'skip', 'prepare', 'progress']) (el(id) as HTMLButtonElement | HTMLInputElement).disabled = !reading;
  el<HTMLButtonElement>('reload').disabled = !reading?.reloadable;
  el<HTMLButtonElement>('export').disabled = exporting || !snapshot || snapshot.ready !== snapshot.total;
  el('position').textContent = reading ? `Word ${activeWord + 1} of ${reading.words.length.toLocaleString()}` : 'No text open';
  el<HTMLInputElement>('progress').value = String(activeWord);
  el('prepared').textContent = snapshot ? `${snapshot.ready}/${snapshot.total} passages ready · ${snapshot.device === 'cuda' ? 'GPU' : snapshot.device === 'auto' ? 'Auto' : snapshot.device.toUpperCase()}` : '';
  el('prepared').title = snapshot?.device_notice ?? '';
  el('status').classList.toggle('error', Boolean(errorMessage));
  if (errorMessage) { el('status').textContent = errorMessage; return; }
  const target = snapshot?.chunks[chunkFor(pending?.word ?? activeWord)];
  let status = 'Ready to open text';
  if (reading) {
    if (target?.status === 'error') { status = target.error ?? 'Speech generation failed. Press Play to retry.'; el('status').classList.add('error'); }
    else if (desiredPlaying && pending) status = target?.status === 'loading' ? 'Preparing voice…' : target?.status === 'ready' ? 'Starting playback…' : 'Preparing the selected passage…';
    else if (desiredPlaying) status = 'Playing · click any word to jump';
    else if (endedChapter) status = 'Reading complete';
    else if (preparing && snapshot && snapshot.ready < snapshot.total) status = 'Paused · preparing audio in the background';
    else status = target?.status === 'ready' ? 'Paused · audio saved' : 'Ready · press Play to prepare audio';
  }
  el('status').textContent = status;
  updateClock();
}

function updateClock() {
  if (!snapshot || !loaded) { el('clock').textContent = '0:00'; return; }
  const previous = snapshot.chunks.slice(0, loaded.chunk);
  const prefixKnown = previous.every(c => c.status === 'ready');
  const elapsed = audio.currentTime + (prefixKnown ? previous.reduce((s,c) => s + (c.duration ?? 0), 0) : 0);
  const total = snapshot.ready === snapshot.total ? formatTime(snapshot.chunks.reduce((s,c) => s + (c.duration ?? 0), 0)) : '…';
  el('clock').textContent = prefixKnown ? `${formatTime(elapsed)} / ${total}` : `Passage ${formatTime(elapsed)}`;
}

function lineRange(word: number): { start: number; end: number } {
  const node = wordNodes[word];
  if (!node || !reading) return { start: word, end: word + 1 };
  const top = node.getBoundingClientRect().top;
  // Inspect only neighboring words, not the full document on each audio tick.
  const sameLine = (id: number) => reading!.words[id].paragraph === reading!.words[word].paragraph
    && Math.abs(wordNodes[id].getBoundingClientRect().top - top) < 2;
  let start = word, end = word + 1;
  while (start > 0 && sameLine(start - 1)) start--;
  while (end < wordNodes.length && sameLine(end)) end++;
  return { start, end };
}

function rangeFor(word: number): { start: number; end: number; line: boolean } {
  const bounds = sentenceBounds.get(reading!.words[word].sentence);
  const height = sentenceNodes.get(reading!.words[word].sentence)?.getBoundingClientRect().height ?? 0;
  const lineHeight = settings.fontSize * settings.lineHeight;
  const maxHeight = Math.max(3 * lineHeight, Math.min(6 * lineHeight, el('reader-scroll').clientHeight * 0.65));
  // Punctuation-free prose and giant sentences should never light up a whole page.
  if (settings.highlightMode === 'line' || !bounds || bounds.chars > 600 || bounds.end - bounds.start > 80 || height > maxHeight)
    return { ...lineRange(word), line: true };
  return { start: bounds.start, end: bounds.end, line: false };
}

function highlight(word: number, follow = true) {
  if (!reading) return;
  word = Math.max(0, Math.min(reading.words.length - 1, word));
  wordNodes[activeWord]?.classList.remove('active');
  wordNodes[activeWord]?.removeAttribute('aria-current');
  activeWord = word;
  wordNodes[word]?.classList.add('active');
  wordNodes[word]?.setAttribute('aria-current', 'true');
  const sentence = reading.words[word].sentence;
  const range = rangeFor(word);
  el('reading').classList.add('has-focus');
  const lineMarker = el('line-marker');
  lineMarker.hidden = !range.line;
  if (range.line) {
    const first = wordNodes[range.start].getBoundingClientRect();
    const last = wordNodes[range.end - 1].getBoundingClientRect();
    const container = el('reading').getBoundingClientRect();
    Object.assign(lineMarker.style, { left: `${first.left - container.left}px`, top: `${first.top - container.top}px`,
      width: `${Math.max(1, last.right - first.left)}px`, height: `${first.height}px` });
  }
  if (!focusRange || range.start !== focusRange.start || range.end !== focusRange.end || range.line !== focusRange.line) {
    if (focusRange) for (let id = focusRange.start; id < focusRange.end; id++) wordNodes[id]?.classList.remove('focused');
    if (selectedSentence !== null) sentenceNodes.get(selectedSentence)?.classList.remove('active');
    for (let id = range.start; id < range.end; id++) {
      wordNodes[id].classList.add('focused');
    }
    selectedSentence = range.line ? null : sentence;
    if (!range.line) sentenceNodes.get(sentence)?.classList.add('active');
    focusRange = range;
    if (follow && settings.follow) ensureVisible(word);
  }
  el('focus-mode').textContent = range.line ? settings.highlightMode === 'line' ? 'Line highlighting' : 'Line highlighting · long sentence' : 'Sentence highlighting';
  el('back').title = `Previous ${range.line ? 'line' : 'sentence'} · Left arrow`;
  el('skip').title = `Next ${range.line ? 'line' : 'sentence'} · Right arrow`;
  el<HTMLInputElement>('progress').value = String(word);
  el('position').textContent = `Word ${word + 1} of ${reading.words.length.toLocaleString()}`;
}

function ensureVisible(word: number) {
  const node = wordNodes[word];
  if (!node) return;
  const box = node.getBoundingClientRect();
  const frame = el('reader-scroll').getBoundingClientRect();
  if (box.top < frame.top + 24 || box.bottom > frame.bottom - 32) {
    node.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }
}

function applySettings() {
  document.documentElement.style.setProperty('--reading-size', `${settings.fontSize}px`);
  document.documentElement.style.setProperty('--reading-spacing', String(settings.lineHeight));
  el<HTMLInputElement>('font').value = String(settings.fontSize);
  el<HTMLInputElement>('spacing').value = String(settings.lineHeight);
  el<HTMLInputElement>('follow').checked = settings.follow;
  el<HTMLInputElement>('word-highlight').checked = settings.wordHighlight;
  el<HTMLInputElement>('dim-surrounding').checked = settings.dimSurrounding;
  el<HTMLInputElement>('line-highlight').checked = settings.highlightMode === 'line';
  el('reading').classList.toggle('word-highlighting', settings.wordHighlight);
  el('reading').classList.toggle('dim-surrounding', settings.dimSurrounding);
  el('font-label').textContent = `${settings.fontSize}px`;
  el('spacing-label').textContent = `${settings.lineHeight.toFixed(2)}×`;
  audio.playbackRate = settings.rate;
  audio.defaultPlaybackRate = settings.rate;
  audio.preservesPitch = true;
  audio.volume = settings.volume ?? 1;
  el<HTMLInputElement>('volume').value = String(audio.volume);
  el('volume-label').textContent = `${Math.round(audio.volume * 100)}%`;
  if (reading) highlight(activeWord, false);
}

function refreshLayout() {
  cancelAnimationFrame(layoutFrame);
  layoutFrame = requestAnimationFrame(() => { if (reading) highlight(activeWord, false); });
}
const layoutObserver = new ResizeObserver(refreshLayout);
layoutObserver.observe(el('reading'));
layoutObserver.observe(el('reader-scroll'));
document.fonts.ready.then(refreshLayout);

function saveSettings() {
  clearTimeout(savingSettings);
  savingSettings = setTimeout(() => api<Settings>('/api/settings', settings).catch(fail), 250);
}

async function refreshRecent() {
  const state = await api<AppState>('/api/state');
  const recent = el<HTMLSelectElement>('recent');
  recent.replaceChildren(new Option('Recent texts', ''));
  state.recent.forEach(doc => recent.add(new Option(doc.name, doc.id)));
  recent.value = state.recent.some(doc => doc.id === reading?.id) ? reading!.id : '';
}

function setRecentBusy(busy: boolean) {
  recentBusy = busy;
  recentDialog.setAttribute('aria-busy', String(busy));
  recentDialog.querySelectorAll<HTMLButtonElement>('.history-action').forEach(button => {
    button.disabled = busy || (button.id === 'clear-recent' && !recentEntries.length);
  });
}

async function renderRecentManager() {
  recentEntries = await api<RecentText[]>('/api/recent');
  const list = el('recent-list');
  list.replaceChildren();
  for (const doc of recentEntries) {
    const item = document.createElement('li');
    const description = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = doc.name;
    const preview = document.createElement('p');
    const excerpt = doc.preview.replace(/\s+/g, ' ').trim();
    preview.textContent = excerpt.slice(0, 160) + (excerpt.length > 160 ? '…' : '');
    description.append(name, preview);
    const remove = document.createElement('button');
    remove.className = 'history-action';
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', `Remove ${doc.name}: ${excerpt.slice(0, 60)} from recent texts`);
    remove.addEventListener('click', () => void changeRecent(doc.id, remove));
    item.append(description, remove);
    list.append(item);
  }
  el('recent-status').textContent = recentEntries.length
    ? `${recentEntries.length} recent ${recentEntries.length === 1 ? 'text' : 'texts'}` : 'No recent texts.';
}

async function changeRecent(docId?: string, trigger?: HTMLButtonElement) {
  if (recentBusy) return;
  const buttons = [...recentDialog.querySelectorAll<HTMLButtonElement>('#recent-list button')];
  const removedIndex = trigger ? buttons.indexOf(trigger) : -1;
  setRecentBusy(true);
  try {
    await api(docId ? '/api/recent/remove' : '/api/recent/clear', docId ? { document: docId } : {});
    await refreshRecent();
    await renderRecentManager();
    // The removed button no longer exists; keep keyboard focus inside the dialog.
    const remaining = [...recentDialog.querySelectorAll<HTMLButtonElement>('#recent-list button')];
    (remaining[Math.min(removedIndex, remaining.length - 1)] ?? el('close-recent')).focus();
  } catch (error) {
    el('recent-status').textContent = error instanceof Error ? error.message : String(error);
  } finally { setRecentBusy(false); }
}

async function openRecentManager() {
  if (recentBusy) return;
  recentDialog.showModal();
  recentEntries = [];
  el('recent-list').replaceChildren();
  el('recent-status').textContent = 'Loading recent texts…';
  setRecentBusy(true);
  try { await renderRecentManager(); }
  catch (error) { el('recent-status').textContent = error instanceof Error ? error.message : String(error); }
  finally { setRecentBusy(false); }
}

async function saveBookmark(force = false) {
  if (!reading) return;
  const timing = snapshot?.chunks[chunkFor(activeWord)]?.timings?.find(t => t.word === activeWord);
  const offset = loaded?.doc === reading.id && !pending && timing ? Math.max(0, audio.currentTime - timing.start) : pending?.offset ?? 0;
  const bookmark = { document: reading.id, word: activeWord, offset: Math.round(offset * 100) / 100 };
  const key = JSON.stringify(bookmark);
  if (!force && key === latestBookmarkSent) return;
  latestBookmarkSent = key;
  await api('/api/bookmark', bookmark).catch(fail);
}

async function openReading(doc: Reading) {
  await saveBookmark(true);
  if (reading?.id === doc.id) doc = await api<Reading>(`/api/document/${doc.id}`);
  await api('/api/cancel', {}).catch(fail);
  selectionVersion++;
  desiredPlaying = false;
  preparing = false;
  audio.pause();
  audio.removeAttribute('src');
  audio.load();
  loaded = null;
  snapshot = null;
  errorMessage = '';
  endedChapter = false;
  reading = doc;
  activeWord = doc.bookmark.word;
  pending = { word: activeWord, offset: doc.bookmark.offset };
  selectedSentence = null;
  focusRange = null;
  latestBookmarkSent = '';
  wordNodes = [];
  sentenceNodes = new Map();
  sentenceBounds = new Map();
  const content = el('reading');
  const fragment = document.createDocumentFragment();
  const marker = document.createElement('div');
  marker.id = 'line-marker'; marker.className = 'line-marker'; marker.hidden = true;
  marker.setAttribute('aria-hidden', 'true');
  fragment.append(marker);
  doc.paragraphs.forEach(ids => {
    const paragraph = document.createElement('p');
    let sentence: HTMLSpanElement | null = null;
    let sentenceId = -1;
    ids.forEach(id => {
      const word = doc.words[id];
      const bounds = sentenceBounds.get(word.sentence);
      if (bounds) { bounds.end = id + 1; bounds.chars += word.text.length + word.after.length; }
      else sentenceBounds.set(word.sentence, { start: id, end: id + 1, chars: word.text.length + word.after.length });
      if (sentenceId !== word.sentence) {
        sentence = document.createElement('span');
        sentence.className = 'sentence';
        sentenceId = word.sentence;
        sentenceNodes.set(sentenceId, sentence);
        paragraph.append(sentence);
      }
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'word'; button.textContent = word.text;
      button.setAttribute('aria-label', `Listen from ${word.text}`);
      button.addEventListener('click', () => {
        if (window.getSelection()?.toString()) return;
        void seekWord(id).catch(fail);
      });
      wordNodes[id] = button;
      sentence!.append(button, document.createTextNode(word.after || ' '));
    });
    fragment.append(paragraph);
  });
  content.replaceChildren(fragment);
  el('welcome').hidden = true;
  el('chapter').hidden = false;
  el('import-note').hidden = doc.format !== 'markdown';
  el('chapter-count').textContent = `${doc.words.length.toLocaleString()} words · ${doc.chunks.length} passages`;
  el<HTMLInputElement>('progress').max = String(doc.words.length - 1);
  highlight(activeWord, false);
  paintControls();
  requestAnimationFrame(() => ensureVisible(activeWord));
  await refreshRecent();
  await poll();
}

async function openFile() {
  if (window.pywebview?.api) {
    const result = await window.pywebview.api.open_file();
    if (result && 'error' in result) throw new Error(result.error);
    if (result) await openReading(result);
  } else el<HTMLInputElement>('file').click();
}

async function fromClipboard() {
  const button = el<HTMLButtonElement>('clipboard');
  button.disabled = true;
  try {
    let text: string;
    if (window.pywebview?.api) {
      const result = await window.pywebview.api.read_clipboard();
      if (result.error) throw new Error(result.error);
      text = result.text ?? '';
    } else {
      try { text = await navigator.clipboard.readText(); }
      catch { throw new Error('Clipboard access was unavailable. Allow clipboard access in your browser and try again.'); }
    }
    if (!text.trim()) throw new Error('The clipboard has no readable text. Copy some text and try again.');
    if (new Blob([text]).size > 5_000_000) throw new Error('Please copy text smaller than 5 MB.');
    await openReading(await api<Reading>('/api/import', { name: 'Clipboard text', text }));
  } finally { button.disabled = false; }
}

async function importFile(file: File) {
  if (!/\.(txt|md)$/i.test(file.name)) throw new Error('Please select a text (.txt) or Markdown (.md) file.');
  if (file.size > 5_000_000) throw new Error('Please select a text file smaller than 5 MB.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  let text: string;
  if (bytes[0] === 255 && bytes[1] === 254) text = new TextDecoder('utf-16le').decode(bytes);
  else if (bytes[0] === 254 && bytes[1] === 255) text = new TextDecoder('utf-16be').decode(bytes);
  else { try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch { text = new TextDecoder('windows-1252').decode(bytes); } }
  await openReading(await api<Reading>('/api/import', { name: file.name, text }));
}

async function queuePassages(chunk: number) {
  if (!reading) return;
  preparing = true;
  await api('/api/prepare', { document: reading.id, voice: settings.voice, chunk });
}

async function seekWord(word: number, offset = 0, prioritize = true) {
  if (!reading) return;
  errorMessage = ''; endedChapter = false;
  selectionVersion++;
  audio.pause();
  pending = { word, offset };
  highlight(word);
  paintControls();
  const chunk = chunkFor(word);
  if (prioritize && (desiredPlaying || preparing)) await queuePassages(chunk);
  await resolvePending();
  paintControls();
  await saveBookmark(true);
}

async function resolvePending() {
  if (!pending || !reading || !snapshot) return;
  const chunk = chunkFor(pending.word);
  const job = snapshot.chunks[chunk];
  if (!job || job.status !== 'ready' || !job.url || !job.timings) return;
  const timing = job.timings.find(t => t.word === pending!.word);
  if (!timing) return;
  const version = selectionVersion;
  const targetTime = Math.max(0, Math.min((job.duration ?? 0) - 0.01, timing.start + pending.offset - (pending.offset ? 0 : 0.025)));
  const start = async () => {
    if (version !== selectionVersion) return;
    audio.currentTime = targetTime;
    audio.playbackRate = settings.rate;
    pending = null;
    if (desiredPlaying) {
      try { await audio.play(); }
      catch (error) {
        if (version !== selectionVersion) return;
        desiredPlaying = false;
        if (error instanceof DOMException && error.name === 'NotAllowedError') errorMessage = 'Audio is ready. Press Play to listen.';
        else fail(error);
      }
    }
    paintControls();
  };
  if (loaded?.doc === reading.id && loaded.voice === settings.voice && loaded.chunk === chunk && audio.readyState >= 1) {
    await start();
  } else {
    if (loaded?.doc === reading.id && loaded.voice === settings.voice && loaded.chunk === chunk && audio.src.endsWith(job.url)) return;
    loaded = { doc: reading.id, voice: settings.voice, chunk };
    audio.onloadedmetadata = () => { void start().catch(fail); };
    audio.src = job.url;
    audio.playbackRate = settings.rate;
    audio.load();
  }
}

async function togglePlay() {
  if (!reading) return;
  errorMessage = '';
  if (desiredPlaying) {
    desiredPlaying = false;
    audio.pause();
    paintControls();
    await saveBookmark(true);
    return;
  }
  const restart = endedChapter;
  desiredPlaying = true;
  endedChapter = false;
  paintControls();
  try {
    if (restart) { await seekWord(0); return; }
    if (!preparing || snapshot?.chunks[chunkFor(activeWord)]?.status === 'error') await queuePassages(chunkFor(activeWord));
    if (loaded && !pending && audio.readyState >= 1) await audio.play();
    else {
      if (!pending) pending = { word: activeWord, offset: 0 };
      await resolvePending();
    }
  } catch (error) { desiredPlaying = false; throw error; }
  finally { paintControls(); }
}

async function sentenceJump(direction: number) {
  if (!reading) return;
  const range = rangeFor(activeWord);
  if (range.line) {
    const target = direction > 0 ? Math.min(reading.words.length - 1, range.end)
      : range.start > 0 ? lineRange(range.start - 1).start : 0;
    await seekWord(target);
    return;
  }
  const ids = [...sentenceNodes.keys()];
  const current = ids.indexOf(reading.words[activeWord].sentence);
  const target = ids[Math.max(0, Math.min(ids.length - 1, current + direction))];
  await seekWord(reading.words.find(w => w.sentence === target)!.id);
}

async function poll() {
  if (!reading || polling) return;
  polling = true;
  const docId = reading.id, voice = settings.voice;
  try {
    const result = await api<Snapshot>(`/api/jobs/${docId}?voice=${voice}`);
    if (reading?.id !== docId || settings.voice !== voice) return;
    snapshot = result;
    if (pending && result.chunks[chunkFor(pending.word)]?.status === 'error') {
      desiredPlaying = false;
      audio.pause();
    }
    await resolvePending();
    paintControls();
  } catch (error) { fail(error); }
  finally { polling = false; }
}

function trackAudio() {
  if (reading && snapshot && loaded && !pending && !audio.paused) {
    const timings = snapshot.chunks[loaded.chunk]?.timings;
    if (timings?.length) {
      const time = audio.currentTime;
      // Binary search finds the latest word boundary. Punctuation shares a boundary.
      let low = 0, high = timings.length;
      while (low < high) { const mid = (low + high) >>> 1; if (timings[mid].start <= time) low = mid + 1; else high = mid; }
      const current = timings[Math.max(0, low - 1)];
      if (current.word !== activeWord) highlight(current.word);
    }
    updateClock();
  }
  requestAnimationFrame(trackAudio);
}

audio.addEventListener('ended', () => {
  if (!reading || !loaded) return;
  const next = reading.chunks[loaded.chunk + 1];
  if (!next) { desiredPlaying = false; endedChapter = true; paintControls(); void saveBookmark(true); }
  else { void seekWord(next.word_start, 0, false).then(() => {
    if (snapshot?.chunks[next.index]?.status !== 'ready') return queuePassages(next.index);
  }).catch(fail); }
});
audio.addEventListener('error', () => {
  if (!audio.getAttribute('src')) return;
  desiredPlaying = false;
  loaded = null;
  pending = null;
  fail(new Error('The saved audio could not be played. Press Play to retry.'));
  paintControls();
});
for (const event of ['waiting', 'playing', 'canplay', 'pause']) audio.addEventListener(event, paintControls);

el('open').addEventListener('click', () => void openFile().catch(fail));
el('clipboard').addEventListener('click', () => void fromClipboard().catch(fail));
el('welcome-open').addEventListener('click', () => void openFile().catch(fail));
el<HTMLInputElement>('file').addEventListener('change', event => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0]; if (file) void importFile(file).catch(fail); input.value = '';
});
el('sample').addEventListener('click', () => void api<Reading>('/api/sample', {}).then(openReading).catch(fail));
el<HTMLSelectElement>('recent').addEventListener('change', event => {
  const id = (event.target as HTMLSelectElement).value;
  if (id) void api<Reading>(`/api/document/${id}`).then(openReading).catch(fail);
});
el('manage-recent').addEventListener('click', () => void openRecentManager());
el('close-recent').addEventListener('click', () => recentDialog.close());
el('clear-recent').addEventListener('click', () => void changeRecent());
el('reload').addEventListener('click', () => { if (reading) void api<Reading>(`/api/reload/${reading.id}`, {}).then(openReading).catch(fail); });
el('play').addEventListener('click', () => void togglePlay().catch(fail));
el('back').addEventListener('click', () => void sentenceJump(-1).catch(fail));
el('skip').addEventListener('click', () => void sentenceJump(1).catch(fail));
el('prepare').addEventListener('click', () => {
  errorMessage = '';
  void queuePassages(chunkFor(activeWord)).then(poll).catch(fail);
});
el<HTMLInputElement>('progress').addEventListener('change', event => void seekWord(Number((event.target as HTMLInputElement).value)).catch(fail));
el<HTMLSelectElement>('voice').addEventListener('change', async event => {
  await saveBookmark(true);
  selectionVersion++; desiredPlaying = false; preparing = false; audio.pause(); loaded = null; snapshot = null;
  settings.voice = (event.target as HTMLSelectElement).value;
  pending = { word: activeWord, offset: 0 };
  errorMessage = ''; endedChapter = false;
  await api('/api/cancel', {}).catch(fail);
  saveSettings(); paintControls(); void poll();
});
el<HTMLSelectElement>('rate').addEventListener('change', event => { settings.rate = Number((event.target as HTMLSelectElement).value); applySettings(); saveSettings(); });
el('appearance').addEventListener('click', () => settingsDialog.showModal());
el('close-settings').addEventListener('click', () => settingsDialog.close());
el<HTMLInputElement>('font').addEventListener('input', event => { settings.fontSize = Number((event.target as HTMLInputElement).value); applySettings(); saveSettings(); });
el<HTMLInputElement>('spacing').addEventListener('input', event => { settings.lineHeight = Number((event.target as HTMLInputElement).value); applySettings(); saveSettings(); });
el<HTMLInputElement>('volume').addEventListener('input', event => { settings.volume = Number((event.target as HTMLInputElement).value); applySettings(); saveSettings(); });
el<HTMLInputElement>('follow').addEventListener('change', event => { settings.follow = (event.target as HTMLInputElement).checked; saveSettings(); });
el<HTMLInputElement>('word-highlight').addEventListener('change', event => { settings.wordHighlight = (event.target as HTMLInputElement).checked; applySettings(); saveSettings(); });
el<HTMLInputElement>('dim-surrounding').addEventListener('change', event => { settings.dimSurrounding = (event.target as HTMLInputElement).checked; applySettings(); saveSettings(); });
el<HTMLInputElement>('line-highlight').addEventListener('change', event => { settings.highlightMode = (event.target as HTMLInputElement).checked ? 'line' : 'sentence'; applySettings(); saveSettings(); });
el('export').addEventListener('click', async () => {
  if (!reading || exporting) return;
  exporting = true;
  const button = el<HTMLButtonElement>('export'); button.disabled = true; button.textContent = 'Exporting…';
  try {
    const response = await fetch(`/api/export/${reading.id}?voice=${settings.voice}`);
    if (!response.ok) throw new Error((await response.json()).error);
    const link = document.createElement('a'); const url = URL.createObjectURL(await response.blob());
    link.href = url; link.download = `${reading.name.replace(/\.(txt|md)$/i, '')}-${settings.voice}.wav`;
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 60_000);
    el('announcement').textContent = 'Audio exported.';
  } catch (error) { fail(error); }
  finally { exporting = false; button.textContent = 'Export WAV'; paintControls(); }
});
let dragDepth = 0;
document.addEventListener('dragenter', event => { if (event.dataTransfer?.types.includes('Files')) { event.preventDefault(); dragDepth++; el('reader-scroll').classList.add('dragging'); } });
document.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; el('reader-scroll').classList.remove('dragging'); } });
document.addEventListener('dragover', event => event.preventDefault());
document.addEventListener('drop', event => { event.preventDefault(); dragDepth = 0; el('reader-scroll').classList.remove('dragging'); const file = event.dataTransfer?.files[0]; if (file) void importFile(file).catch(fail); });
document.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'o') { event.preventDefault(); void openFile().catch(fail); return; }
  if (settingsDialog.open || recentDialog.open || (event.target as HTMLElement).closest('input,select,textarea,button')) return;
  if (event.code === 'Space') { event.preventDefault(); void togglePlay().catch(fail); }
  else if (event.key === 'ArrowLeft') { event.preventDefault(); void sentenceJump(-1).catch(fail); }
  else if (event.key === 'ArrowRight') { event.preventDefault(); void sentenceJump(1).catch(fail); }
});
document.addEventListener('visibilitychange', () => { if (document.hidden) void saveBookmark(true); });
window.addEventListener('pagehide', () => {
  if (!reading) return;
  const timing = snapshot?.chunks[chunkFor(activeWord)]?.timings?.find(t => t.word === activeWord);
  void fetch('/api/bookmark', { method: 'POST', keepalive: true,
    headers: { 'Content-Type': 'application/json', 'X-Reader-Token': window.READER_BOOT?.token ?? '' },
    body: JSON.stringify({ document: reading.id, word: activeWord, offset: pending?.offset ?? (timing ? Math.max(0, audio.currentTime - timing.start) : 0) }) });
});

async function init() {
  const state = await api<AppState>('/api/state');
  settings = { ...settings, ...state.settings };
  const voice = el<HTMLSelectElement>('voice');
  Object.entries(state.voices).forEach(([id,name]) => voice.add(new Option(name,id)));
  voice.value = settings.voice;
  el<HTMLSelectElement>('rate').value = String(settings.rate);
  applySettings();
  await refreshRecent();
  if (state.recent.length) await openReading(await api<Reading>(`/api/document/${state.recent[0].id}`));
  setInterval(() => void poll(), 800);
  setInterval(() => void saveBookmark(), 2000);
  requestAnimationFrame(trackAudio);
}
void init().catch(fail);
