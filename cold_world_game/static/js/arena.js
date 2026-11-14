import { assetUrl, itemName } from './catalog.js';
import { initializeLanguage, getLanguage, t } from './i18n.js';
import { itemGuide } from './item-guide.js';
import { loadAssets, WorldRenderer } from './renderer.js';
import { createSearchIndex, searchItems } from './arena-search.js';
import { GameAudio } from './audio.js';
import { GameMusic } from './music.js';
import { ArenaReplay } from './arena-replay.js';

const byId = identifier => document.getElementById(identifier);
const finishedStatuses = new Set(['downed', 'time_limit', 'weapons_depleted']);
let options, renderer, searchIndex;
let inventory = [], selectedSlot = 0;
let socket = null, pendingConfig = null, lastUpdate = null;
let phase = 'loading', busy = false, errorCode = null;
let awaitingStart = false;
let previousFrame = performance.now();
let viewingPlaying = false;

initializeLanguage();
const audio = new GameAudio({ preferenceKey: null });
const music = new GameMusic({ preferenceKey: null });
const replay = new ArenaReplay({ request: historyRequest, display: displayFrame, changed: renderState, fail: showError });

async function historyRequest(path, settings = {}) {
  const response = await fetch(path, { ...settings, headers: { 'X-Arena-Password': byId('password').value } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || 'arena_history_failed');
  return body;
}

function displayFrame(frame, { playing = false, seek = false, catalog } = {}) {
  if (!renderer) return;
  lastUpdate = frame;
  if (seek) { renderer.reset(); renderer.elapsed = frame?.seconds ?? 0; audio.reset(frame?.state.event_sequence ?? 0); }
  if (!frame) {
    byId('stage-hint').hidden = false;
    viewingPlaying = false;
    music.suspend(); audio.suspendPlayback();
    renderState();
    return;
  }
  renderer.catalog = catalog ?? options.catalog;
  if (!music.active) music.enter();
  byId('stage-hint').hidden = true;
  renderer.selected = frame.state.you.selected;
  renderer.pointer = { x: frame.aim[0], y: frame.aim[1], active: false };
  const state = { ...frame.state, paused: !playing };
  renderer.recordedFrames = seek || !playing || Boolean(replay.record);
  renderer.setState(state);
  if (renderer.recordedFrames) renderer.effects.restore(state);
  if (playing && !viewingPlaying) { audio.resumePlayback(); music.unlock(); }
  if (!playing) { audio.suspendPlayback(); music.suspend(); }
  viewingPlaying = playing;
  if (playing && !seek) audio.consume(state);
  renderState();
}

function renderAudioControls() {
  const sound = byId('sound-button'), background = byId('music-button');
  sound.textContent = t(audio.available ? audio.muted ? 'sound.off' : 'sound.on' : 'sound.unavailable');
  sound.disabled = !audio.available;
  sound.setAttribute('aria-pressed', String(!audio.muted));
  sound.setAttribute('aria-label', t(audio.muted ? 'sound.enable' : 'sound.disable'));
  background.textContent = t(music.muted ? 'arena.musicOff' : 'arena.musicOn');
  background.disabled = !music.available;
  background.setAttribute('aria-pressed', String(!music.muted));
  background.setAttribute('aria-label', t(music.muted ? 'music.enable' : 'music.disable'));
}

byId('sound-button').addEventListener('click', () => audio.toggleMute());
byId('music-button').addEventListener('click', () => music.toggle());
audio.addEventListener('change', renderAudioControls);
music.addEventListener('change', renderAudioControls);
renderAudioControls();
for (const event of ['pointerdown', 'keydown']) window.addEventListener(event, () => {
  audio.unlock();
  if (viewingPlaying) music.unlock();
}, { capture: true });
window.addEventListener('blur', () => { audio.suspendPlayback(); music.suspend(); });
window.addEventListener('focus', () => { if (viewingPlaying) { audio.resumePlayback(); music.unlock(); } });
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { audio.suspendPlayback(); music.suspend(); }
  else if (viewingPlaying && document.hasFocus()) { audio.resumePlayback(); music.unlock(); }
});

function icon(kind) {
  const image = document.createElement('img');
  image.src = assetUrl(kind);
  image.alt = '';
  image.loading = 'lazy';
  return image;
}

function showError(code) {
  errorCode = code;
  byId('error').hidden = !code;
  byId('error').textContent = code ? t(`error.${code}`) : '';
}

function renderInventory() {
  byId('slot-target').textContent = t('arena.addTo', { slot: selectedSlot + 1 });
  byId('inventory').replaceChildren(...inventory.map((kind, index) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'slot';
    const select = document.createElement('button');
    select.type = 'button';
    select.className = 'slot-select';
    select.setAttribute('aria-pressed', String(selectedSlot === index));
    select.setAttribute('aria-label', t('arena.slot', { slot: index + 1, name: kind ? itemName(kind) : t('arena.emptySlot') }));
    const name = document.createElement('span');
    name.textContent = kind ? itemName(kind) : t('arena.emptySlot');
    if (kind) select.append(icon(kind));
    select.append(name);
    select.addEventListener('click', () => { selectedSlot = index; renderInventory(); });
    const number = document.createElement('span');
    number.className = 'slot-number';
    number.textContent = index + 1;
    wrapper.append(select, number);
    if (kind) {
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'slot-remove';
      remove.textContent = '×';
      remove.setAttribute('aria-label', t('arena.remove', { slot: index + 1 }));
      remove.addEventListener('click', () => { inventory[index] = null; selectedSlot = index; renderInventory(); });
      wrapper.append(remove);
    }
    return wrapper;
  }));
  byId('unused-warning').hidden = !inventory.some(kind => kind && searchIndex.find(item => item.kind === kind)?.support === 'unused');
  renderItemDescription();
}

function renderItemDescription() {
  const container = byId('item-description');
  const item = searchIndex.find(candidate => candidate.kind === inventory[selectedSlot]);
  if (!item) {
    container.textContent = t('arena.itemInfoEmpty');
    return;
  }
  const guide = itemGuide(item, options.catalog);
  const header = document.createElement('div');
  header.className = 'item-preview-header';
  const name = document.createElement('strong');
  name.textContent = itemName(item.kind);
  header.append(icon(item.kind), name);
  const paragraphs = [guide.category, guide.detail, guide.effect, guide.use, t(`arena.support.${item.support}`)].map((text, index) => {
    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    if (index === 0) paragraph.className = 'muted';
    if (index === 4) paragraph.className = item.support === 'unused' ? 'warning' : 'support';
    return paragraph;
  });
  container.replaceChildren(header, ...paragraphs);
}

function renderSearch() {
  const results = searchItems(searchIndex, byId('search').value);
  byId('search-count').textContent = t('arena.results', { count: results.length });
  byId('results').replaceChildren(...results.slice(0, 30).map(item => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'result';
    button.dataset.kind = item.kind;
    const text = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = itemName(item.kind);
    const alternate = document.createElement('small');
    alternate.textContent = item.names[getLanguage() === 'en' ? 0 : 1] + ' · ' + t(`arena.support.${item.support}`);
    if (item.support === 'unused') alternate.className = 'unsupported';
    const description = document.createElement('p');
    description.textContent = itemGuide(item, options.catalog).effect;
    button.title = `${name.textContent}\n${description.textContent}\n${t(`arena.support.${item.support}`)}`;
    text.append(name, alternate, description);
    button.append(icon(item.kind), text);
    button.addEventListener('click', () => {
      inventory[selectedSlot] = item.kind;
      renderInventory();
    });
    return button;
  }));
  if (!results.length) byId('results').textContent = t('arena.noResults');
}

function renderState() {
  byId('settings').disabled = phase === 'loading' || phase === 'connecting';
  byId('start').disabled = ['loading', 'connecting'].includes(phase) || busy;
  byId('pause').disabled = busy || (replay.record ? replay.loading : !['running', 'paused'].includes(phase));
  byId('pause').textContent = t(replay.record ? replay.playing ? 'arena.pauseReplay' : 'arena.playReplay' : phase === 'paused' ? 'arena.resume' : 'arena.pause');
  byId('status').textContent = t(replay.record ? replay.playing ? 'arena.replaying' : 'arena.replayPaused' : `arena.${phase === 'error' ? 'ready' : phase}`, { seconds: lastUpdate?.seconds.toFixed(2) ?? '0.00' });
  byId('status').removeAttribute('data-i18n');
  if (!lastUpdate) {
    byId('elapsed').textContent = '0.00 s';
    byId('alive').textContent = '0';
    byId('kills').textContent = '0';
    for (const identifier of ['temperature', 'hunger', 'mounted-remaining']) byId(identifier).textContent = '—';
    byId('decision').textContent = '';
    byId('current-inventory').replaceChildren();
    return;
  }
  const update = lastUpdate, player = update.state.you;
  byId('elapsed').textContent = update.seconds.toFixed(2) + ' s';
  byId('alive').textContent = update.alive;
  byId('kills').textContent = update.kills;
  byId('temperature').textContent = player.temperature.toFixed(2) + ' °C';
  byId('hunger').textContent = player.hunger.toFixed(2);
  byId('mounted-remaining').textContent = update.mounted_ammo ?? '—';
  byId('decision').textContent = finishedStatuses.has(update.status) ? t(`arena.${update.status}`, { seconds: update.seconds.toFixed(2) }) : t(`arena.decision.${update.decision}`);
  byId('current-inventory').replaceChildren(...player.inventory.map((item, index) => {
    const slot = document.createElement('div');
    slot.className = 'current-slot' + (index === player.selected ? ' held' : '');
    slot.title = t('arena.slot', { slot: index + 1, name: item ? itemName(item.kind) : t('arena.emptySlot') });
    if (item) {
      slot.append(icon(item.kind));
      if (item.ammo != null || item.uses != null) {
        const amount = document.createElement('small');
        amount.textContent = item.ammo ?? item.uses;
        slot.append(amount);
      }
    }
    return slot;
  }));
}

function send(message) {
  if (socket?.readyState !== WebSocket.OPEN) throw new Error('arena_failed');
  socket.send(JSON.stringify(message));
}

function connect() {
  const connection = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`);
  socket = connection;
  connection.addEventListener('open', () => send({ type: 'join', password: byId('password').value }));
  connection.addEventListener('message', event => {
    if (socket !== connection) return;
    const message = JSON.parse(event.data);
    if (message.type === 'ready') {
      send({ type: 'start', config: pendingConfig });
      pendingConfig = null;
    } else if (message.type === 'started') {
      awaitingStart = false;
      replay.reset();
      replay.refresh();
      audio.reset();
      music.enter();
      renderer.reset();
      renderer.elapsed = 0;
      lastUpdate = null;
      renderState();
    } else if (message.type === 'state') {
      if (awaitingStart) return;
      phase = message.status;
      busy = false;
      replay.acceptLive(message);
      if (finishedStatuses.has(phase)) replay.refresh();
      renderState();
    } else if (message.type === 'error') {
      showError(message.code);
      busy = false;
      awaitingStart = false;
      if (phase === 'connecting') phase = replay.live?.status ?? 'error';
      if (message.code === 'arena_failed') phase = 'error';
      renderState();
    }
  });
  connection.addEventListener('close', () => {
    if (socket !== connection) return;
    socket = null;
    busy = false;
    awaitingStart = false;
    if (!finishedStatuses.has(phase)) phase = 'disconnected';
    if (replay.live && !finishedStatuses.has(replay.live.status)) replay.live.status = 'stopped';
    if (!replay.record && lastUpdate) displayFrame(lastUpdate, { seek: true });
    replay.render();
    replay.refresh();
    renderState();
  });
  connection.addEventListener('error', () => showError('arena_failed'));
}

byId('configuration').addEventListener('submit', event => {
  event.preventDefault();
  if (busy || ['loading', 'connecting'].includes(phase)) return;
  if (!byId('configuration').reportValidity()) return;
  showError(null);
  const config = { inventory: [...inventory], seed: byId('seed').value.trim(), monster_limit: Number(byId('monster-limit').value),
    ai: byId('ai').value, mounted_gun: byId('mounted').checked, mounted_ammo: Number(byId('mounted-ammo').value),
    ambient_temperature: Number(byId('ambient-temperature').value), hunger_drain: byId('hunger-drain').checked,
    time_limit: byId('time-limit').value.trim() === '' ? null : Number(byId('time-limit').value) };
  phase = 'connecting';
  busy = true;
  awaitingStart = true;
  renderState();
  if (socket?.readyState === WebSocket.OPEN) send({ type: 'start', config });
  else { pendingConfig = config; connect(); }
  if (matchMedia('(max-width: 900px)').matches) byId('battle-heading').scrollIntoView({ behavior: 'smooth', block: 'start' });
});

byId('pause').addEventListener('click', () => {
  if (replay.record) { replay.toggle(); return; }
  if (busy || !['running', 'paused'].includes(phase)) return;
  if (phase === 'paused') replay.returnLive();
  send({ type: phase === 'paused' ? 'resume' : 'pause' });
  busy = true;
  renderState();
});
byId('search').addEventListener('input', renderSearch);
byId('mounted').addEventListener('change', () => { byId('mounted-ammo-field').hidden = !byId('mounted').checked; });
byId('password').addEventListener('change', () => replay.refresh());
window.addEventListener('cold-world-languagechange', () => {
  if (!options) return;
  for (const option of byId('ai').options) option.textContent = t(`arena.ai.${option.value}`);
  renderInventory(); renderSearch(); renderState(); renderAudioControls(); replay.render(); replay.renderList(); showError(errorCode);
});
window.addEventListener('pagehide', () => { socket?.close(); audio.suspendPlayback(); music.suspend(); });

function draw(now) {
  const elapsed = Math.min(0.1, Math.max(0, (now - previousFrame) / 1000));
  previousFrame = now;
  replay.advance(elapsed);
  if (renderer && lastUpdate) {
    renderer.draw(viewingPlaying ? elapsed * (replay.record ? replay.speed : 1) : 0);
    if (viewingPlaying && document.hasFocus()) music.observe(renderer.state, renderer.camera, renderer.viewport(), renderer.positions, renderer.catalog.monster_types);
  }
  requestAnimationFrame(draw);
}

try {
  const response = await fetch('/api/info');
  if (!response.ok) throw new Error('catalog_unavailable');
  options = await response.json();
  const assets = await loadAssets();
  byId('world').style.aspectRatio = options.viewport.join(' / ');
  renderer = new WorldRenderer(byId('world'), assets.images, assets.animations, assets.effects, options.catalog, options.viewport, assets.monsterHitboxes);
  inventory = [...options.default_inventory];
  searchIndex = createSearchIndex(options.items, options.catalog);
  byId('monster-limit').max = options.max_monsters;
  byId('monster-limit').value = Math.min(32, options.max_monsters);
  byId('mounted-ammo').max = options.max_mounted_ammo;
  byId('mounted-ammo').value = options.catalog.outdoor_features.mounted_gun.ammo;
  byId('ambient-temperature').min = options.ambient_temperature_range[0];
  byId('ambient-temperature').max = options.ambient_temperature_range[1];
  byId('ambient-temperature').value = options.default_ambient_temperature;
  byId('password-field').hidden = !options.password_required;
  byId('ai').replaceChildren(...options.ais.map(policy => new Option(t(`arena.ai.${policy.id}`), policy.id)));
  phase = 'ready';
  renderInventory(); renderSearch(); renderState();
  replay.renderList();
  if (!options.password_required) replay.refresh();
  requestAnimationFrame(draw);
} catch (error) {
  showError(['catalog_unavailable', 'assets_unavailable'].includes(error.message) ? error.message : 'arena_failed');
}
