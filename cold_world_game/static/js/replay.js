import { itemName } from './catalog.js';
import { hasTranslation, initializeLanguage, t } from './i18n.js';
import { loadAssets, WorldRenderer } from './renderer.js';

const node = id => document.getElementById(id);
const localized = (key, fallback) => hasTranslation(key) ? t(key) : fallback;
const formatTime = seconds => seconds < 60 ? `${seconds.toFixed(1)} s` : `${Math.floor(seconds / 60)}:${(seconds % 60).toFixed(1).padStart(4, '0')}`;
const sourceName = source => localized(`replay.source.${source}`, source);
let renderer, current, frame, segment, number = -1, records = [];
let playing = false, previousTime = null, clock = 0, selection = 0, seek = 0, loading = false;
const segments = new Map();

function error(code) {
  node('error').hidden = !code;
  node('error').textContent = code ? localized(`error.${code}`, t('error.replay_file')) : '';
}

async function request(path, options = {}) {
  const password = node('password')?.value ?? '';
  const response = await fetch(path, { ...options, headers: { 'X-Replay-Password-Encoded': encodeURIComponent(password) } });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.error ?? 'replay_file');
  }
  return response;
}

function title(entry) {
  const name = entry.source === 'arena' && entry.configuration?.weapon ? itemName(entry.configuration.weapon) : entry.title;
  return [name, entry.configuration?.batch, sourceName(entry.source), formatTime(entry.duration),
    localized(`arena.${entry.status}`, localized(`replay.status.${entry.status}`, entry.status))].filter(Boolean).join(' · ');
}

function renderRecords() {
  const source = node('source').value, query = node('replay-search').value.trim().toLowerCase();
  const list = records.filter(item => (!source || item.location === source) && (!query || title(item).toLowerCase().includes(query)));
  node('records').replaceChildren(...list.map(item => {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.run = item.id;
    button.textContent = title(item);
    button.setAttribute('aria-pressed', String(item.id === current?.id));
    button.onclick = () => openRun(item.id);
    return button;
  }));
  if (!list.length) node('records').textContent = t('replay.none');
}

async function listRecords(initial = false) {
  error(null);
  try {
    records = (await (await request('/api/replays')).json()).records;
    renderRecords();
    const id = new URLSearchParams(location.search).get('run');
    if (initial && /^[a-f0-9]{32}$/.test(id ?? '')) await openRun(id);
  } catch (failure) {
    error(failure.message);
  }
}

function getSegment(index) {
  if (!segments.has(index)) {
    const entry = current.segments[index];
    const id = current.id;
    if (!entry) return Promise.resolve(null);
    const pending = request(`/api/replays/${id}/segments/${entry.number}`).then(response => response.json()).then(data => {
      let state;
      const seen = new Set();
      data.events = [];
      for (const sample of data.frames) {
        state = sample.state ?? { ...state, ...sample.changes };
        sample.state = { ...state, structures: data.terrain[sample.terrain] };
        for (const note of sample.notes ?? []) data.events.push({ seconds: sample.seconds, frameTime: sample.seconds, data: note });
        for (const event of state.events) {
          if (seen.has(event.id)) continue;
          seen.add(event.id);
          const seconds = sample.seconds + (event.time ?? state.elapsed) - state.elapsed;
          if (seconds >= entry.start - .2) data.events.push({ seconds: Math.max(entry.start, seconds), frameTime: sample.seconds, data: event });
        }
      }
      data.events.sort((a, b) => a.seconds - b.seconds);
      return data;
    });
    segments.set(index, pending);
    pending.catch(() => { if (segments.get(index) === pending) segments.delete(index); });
    for (const cached of segments.keys()) {
      if (Math.abs(cached - index) > 1) segments.delete(cached);
    }
  }
  return segments.get(index);
}

function lastBefore(values, seconds, time) {
  let low = 0, high = values.length;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (time(values[mid]) <= seconds) low = mid + 1;
    else high = mid;
  }
  return Math.max(0, low - 1);
}

function play(value) {
  playing = value;
  previousTime = null;
  node('play').textContent = t(value ? 'replay.pause' : 'replay.play');
}

function summarizeEvent(event) {
  const key = `arena.decision.${event.decision}`;
  if (event.type === 'decision') return [localized(key, event.decision), event.weapon && itemName(event.weapon), event.target].filter(Boolean).join(' · ');
  const type = localized(`replay.event.${event.type}`, event.type);
  const action = event.command?.action ?? event.command?.type ?? event.kind;
  const outcome = event.accepted === false ? t('replay.rejected') : '';
  return [type, action && localized(`arena.edit.${action}`, action), event.actor, event.target, outcome, event.error].filter(Boolean).join(' · ');
}

function renderEvents() {
  const list = node('events');
  list.replaceChildren(...(segment?.events ?? []).map(event => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${formatTime(event.seconds)} · ${summarizeEvent(event.data)}`;
    button.onclick = () => {
      play(false);
      node('event-detail').textContent = JSON.stringify(event.data, null, 2);
      seekTo(event.frameTime, true);
    };
    return button;
  }));
  if (!list.childElementCount) list.textContent = t('replay.noEvents');
}

function itemLabel(item) {
  const remaining = item.ammo ?? item.uses;
  return `${itemName(item.kind)}${item.count > 1 ? ` ×${item.count}` : ''}${remaining != null ? ` · ${remaining}` : ''}`;
}

function renderPlayer() {
  const you = frame.state.you;
  node('vitals').textContent = t('replay.vitals', { temperature: you.temperature, hunger: you.hunger, money: you.money });
  const equipment = ['inventory', 'backpack'].flatMap(storage => (you[storage] ?? []).flatMap((item, slot) => {
    if (!item) return [];
    const span = document.createElement('span');
    span.textContent = `${t(`arena.storage.${storage}`)} ${slot + 1} · ${itemLabel(item)}`;
    if (storage === 'inventory' && slot === you.selected) span.className = 'selected';
    return [span];
  }));
  node('equipment').replaceChildren(...equipment);
  const container = frame.state.container;
  node('opened-container').textContent = container?.slots ? `${t('replay.container')} · ${container.slots.filter(Boolean).map(itemLabel).join(' / ')}` : '';
  const trace = frame.trace;
  node('trace').textContent = trace?.decision
    ? [summarizeEvent({ type: 'decision', ...trace }), JSON.stringify(trace, null, 2)].join('\n')
    : frame.decision ? localized(`arena.decision.${frame.decision}`, frame.decision) : '';
}

function draw(sample, jump) {
  const previous = frame;
  frame = sample;
  if (sample === previous && !jump) return;
  const state = frame.state;
  const elapsed = jump ? 0 : Math.max(0, state.elapsed - renderer.elapsed);
  if (jump) { renderer.reset(); renderer.elapsed = state.elapsed; }
  renderer.selected = state.you.selected ?? 0;
  renderer.pointer = { x: frame.aim?.[0] ?? state.you.x, y: frame.aim?.[1] ?? state.you.y, active: false };
  renderer.setState({ ...state, movement: { mode: 'server' }, paused: !playing });
  if (jump) renderer.effects.restore(state);
  renderer.draw(elapsed);
  renderPlayer();
}

async function seekTo(seconds, jump = false) {
  if (!current) return;
  const id = ++seek;
  const index = lastBefore(current.segments, seconds, entry => entry.start);
  if (index !== number) loading = true;
  try {
    const data = index === number ? segment : await getSegment(index);
    if (id !== seek) return;
    if (index !== number) {
      segment = data;
      number = index;
      node('event-detail').textContent = '';
      renderEvents();
    }
    clock = seconds;
    draw(segment.frames[lastBefore(segment.frames, seconds, entry => entry.seconds)], jump || !frame);
    node('timeline').value = String(clock);
    node('time').textContent = `${formatTime(clock)} / ${formatTime(current.duration)}`;
    if (index + 1 < current.segments.length) getSegment(index + 1).catch(() => {});
    if (clock >= current.duration && playing) play(false);
  } catch (failure) {
    if (id === seek) {
      console.error(failure);
      error(failure.message);
      play(false);
    }
  } finally {
    if (id === seek) loading = false;
  }
}

async function openRun(id) {
  const active = ++selection;
  ++seek;
  play(false);
  error(null);
  try {
    const meta = await (await request(`/api/replays/${id}`)).json();
    if (selection !== active) return;
    current = meta;
    frame = null;
    segment = null;
    number = -1;
    segments.clear();
    node('timeline').min = current.segments[0].start;
    node('timeline').max = current.duration;
    node('timeline').disabled = node('play').disabled = current.duration <= current.segments[0].start;
    node('download').disabled = false;
    node('inspection').hidden = node('replay-config').hidden = false;
    node('config-detail').textContent = JSON.stringify({
      game_version: current.game_version, item_catalog_version: current.item_catalog_version,
      terrain_version: current.terrain_version, configuration: current.configuration, result: current.result,
    }, null, 2);
    node('replay-status').removeAttribute('data-i18n');
    node('replay-status').textContent = title(current);
    const url = new URL(location.href);
    url.searchParams.set('run', current.id);
    history.replaceState(null, '', url);
    renderRecords();
    await seekTo(current.segments[0].start, true);
  } catch (failure) { if (selection === active) error(failure.message); }
}

function animate(now) {
  if (playing && !loading && frame) {
    if (previousTime !== null) seekTo(Math.min(current.duration, clock + Math.min(.2, (now - previousTime) / 1000) * Number(node('speed').value)));
    previousTime = now;
  } else {
    previousTime = null;
  }
  requestAnimationFrame(animate);
}

initializeLanguage();
node('history').onsubmit = event => { event.preventDefault(); if (renderer) listRecords(true); };
node('source').onchange = node('replay-search').oninput = renderRecords;
node('play').onclick = () => {
  if (!playing && clock >= current.duration) seekTo(current.segments[0].start, true);
  play(!playing);
};
node('timeline').oninput = event => { play(false); seekTo(Number(event.target.value), true); };
node('upload').onsubmit = async event => {
  event.preventDefault();
  error(null);
  node('upload-button').disabled = true;
  try {
    const entry = await (await request('/api/replays/upload', { method: 'POST', body: new FormData(event.target) })).json();
    node('source').value = 'uploads';
    node('replay-search').value = '';
    node('file').value = '';
    await listRecords();
    await openRun(entry.id);
  } catch (failure) {
    error(failure.message);
  } finally {
    node('upload-button').disabled = false;
  }
};
node('download').onclick = async () => {
  error(null);
  try {
    const entry = current;
    const response = await request(`/api/replays/${entry.id}/download`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = `${entry.id}.replay`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (failure) { error(failure.message); }
};

try {
  const [assets, response] = await Promise.all([loadAssets(), fetch('/api/info')]);
  if (!response.ok) throw new Error('catalog_unavailable');
  const info = await response.json();
  renderer = new WorldRenderer(node('world'), assets.images, assets.animations, assets.effects, info.catalog ?? info,
    [32, 18], assets.monsterHitboxes, { replay: true });
  renderer.recordedFrames = true;
  new ResizeObserver(() => { if (frame) renderer.draw(0); }).observe(node('world'));
  node('refresh').disabled = false;
  node('upload-button').disabled = false;
  requestAnimationFrame(animate);
  if (!node('password')) listRecords(true);
  window.addEventListener('cold-world-languagechange', () => {
    renderRecords();
    node('play').textContent = t(playing ? 'replay.pause' : 'replay.play');
    if (current) node('replay-status').textContent = title(current);
    if (frame) renderPlayer();
    renderEvents();
  });
} catch (failure) {
  console.error(failure);
  error(failure.message);
}
