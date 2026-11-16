import { itemName } from './catalog.js';
import { hasTranslation, initializeLanguage, t } from './i18n.js';
import { loadAssets, WorldRenderer } from './renderer.js';

const node = id => document.getElementById(id);
const label = (key, fallback) => hasTranslation(key) ? t(key) : fallback;
const terminal = new Set(['cleared', 'downed', 'time_limit', 'weapons_depleted', 'stopped']);
let renderer, options, connection, nextConfig, lastConfig, frame;
let status = 'loading', started = false, ready = false;

function render() {
  node('status').removeAttribute('data-i18n');
  node('status').textContent = t(`arena.${status}`);
  node('settings').disabled = !options || status === 'connecting';
  const active = ready && ['running', 'paused'].includes(status);
  node('editor').hidden = !active;
  node('stop').disabled = node('pause').disabled = !active;
  node('pause').textContent = t(status === 'paused' ? 'arena.resume' : 'replay.pause');
  node('pause').removeAttribute('data-i18n');
  const watch = node('watch');
  watch.hidden = !terminal.has(status) || !frame?.run_id;
  if (!watch.hidden) watch.href = `/replay/?run=${frame.run_id}`;
  node('repeat').hidden = watch.hidden || !ready || !lastConfig;
  node('elapsed').textContent = frame ? `${frame.seconds.toFixed(1)} s` : '—';
  node('kills').textContent = frame ? `${frame.kills} / ${frame.spawned}` : '—';
  node('alive').textContent = frame?.alive ?? '—';
  if (!frame) return;
  const you = frame.state.you;
  const item = you.inventory[you.selected];
  node('remaining').textContent = (you.seated ? frame.mounted_ammo : null) ?? item?.ammo ?? item?.uses ?? (item ? t('arena.unlimited') : frame.mounted_ammo ?? '0');
  node('decision').textContent = you.temperature < 5 ? t('arena.reviveHint') : [
    label(`arena.decision.${frame.decision}`, frame.decision), frame.trace?.weapon && itemName(frame.trace.weapon),
    frame.trace?.distance != null ? `${frame.trace.distance} ${t('arena.tiles')}` : null,
  ].filter(Boolean).join(' · ');
  node('player-current').textContent = t('replay.vitals', {
    temperature: you.temperature, hunger: you.hunger, money: you.money,
  });
  node('live-strategy').value = frame.strategy;
  updateSlots();
}

function error(code) {
  const element = node('error');
  element.hidden = !code;
  element.textContent = code ? label(`error.${code}`, t('error.arena_failed')) : '';
}

function sendStart() {
  if (nextConfig) connection.send(JSON.stringify({ type: 'start', config: nextConfig }));
  nextConfig = null;
}

function controls(action, fields = {}) {
  if (!ready) return;
  error(null);
  connection.send(JSON.stringify({ type: 'control', action, ...fields }));
}

function connect() {
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  connection = ws;
  ws.onopen = () => ws.send(JSON.stringify({ type: 'join', password: node('password').value }));
  ws.onmessage = ({ data }) => {
    if (connection !== ws) return;
    const message = JSON.parse(data);
    switch (message.type) {
      case 'ready':
        ready = true;
        sendStart();
        break;
      case 'started':
        started = true;
        lastConfig = message.config;
        frame = null;
        renderer.reset();
        break;
      case 'state':
        if (!started) return;
        frame = message;
        status = frame.status;
        renderer.selected = frame.state.you.selected;
        renderer.setState(frame.state);
        renderer.pointer = { x: frame.aim[0], y: frame.aim[1], active: false };
        break;
      case 'edit_error':
        error(message.code);
        break;
      case 'error':
        error(message.code);
        if (status === 'connecting') status = frame?.status ?? 'ready';
        if (message.code === 'arena_failed') status = 'error';
        break;
    }
    render();
  };
  ws.onclose = () => {
    if (connection !== ws) return;
    connection = null;
    ready = false;
    if (!terminal.has(status)) status = 'ready';
    render();
  };
  ws.onerror = () => error('arena_failed');
}

function readNumbers(form, keys) {
  return Object.fromEntries(keys.flatMap(key => {
    const value = form.elements[key].value;
    return value === '' ? [] : [[key, Number(value)]];
  }));
}

function choices(select, entries, first = null) {
  const value = select.value;
  select.replaceChildren(...(first ? [new Option(t(first), '')] : []), ...entries.map(([id, name]) => new Option(name, id)));
  if ([...select.options].some(option => option.value === value)) select.value = value;
}

function updateSlots() {
  const { storage, slot } = node('loadout').elements;
  const items = frame?.state.you[storage.value] ?? [];
  const value = slot.value;
  const descriptions = items.map((item, index) => `${index + 1} · ${item ? itemName(item.kind) : t('arena.empty')}`);
  if (descriptions.length === slot.options.length && descriptions.every((text, index) => text === slot.options[index].text)) return;
  choices(slot, descriptions.map((text, index) => [String(index), text]));
  if (value) slot.value = value;
}

function showSlot() {
  const { storage, slot, kind, count, remaining } = node('loadout').elements;
  const item = frame?.state.you[storage.value]?.[Number(slot.value)];
  kind.value = item?.kind ?? '';
  count.value = item?.count ?? 1;
  remaining.value = item?.ammo ?? item?.uses ?? '';
}

function populate() {
  const kindOptions = kinds => kinds.map(kind => [kind, itemName(kind)]);
  choices(node('weapon'), kindOptions(options.weapons));
  choices(node('intensity'), Object.entries(options.waves).map(([key, wave]) => [key, t(`arena.intensity.${key}`, { count: wave.length })]));
  choices(node('terrain'), ['open', 'cover', 'forest'].map(key => [key, t(`arena.terrain.${key}`)]));
  const strategies = options.strategies.map(key => [key, t(`arena.strategy.${key}`)]);
  choices(node('strategy'), strategies);
  choices(node('live-strategy'), strategies);
  choices(node('loadout').elements.kind, kindOptions(options.catalog.items), 'arena.empty');
  choices(node('tile-edit').elements.kind, kindOptions(options.terrain), 'arena.remove');
  choices(node('monsters').elements.kind, Object.keys(options.catalog.monster_types).map(kind => [kind, label(`arena.monster.${kind}`, kind)]));
}

function start(config) {
  error(null);
  nextConfig = config;
  status = 'connecting';
  started = false;
  render();
  if (ready && connection?.readyState === WebSocket.OPEN) sendStart();
  else connect();
}

node('configuration').onsubmit = event => {
  event.preventDefault();
  start({ weapon: node('weapon').value, intensity: node('intensity').value, editable: true,
    strategy: node('strategy').value, terrain: node('terrain').value, ...readNumbers(event.target, ['seed', 'duration']) });
};
node('pause').onclick = () => controls(status === 'paused' ? 'resume' : 'pause');
node('stop').onclick = () => controls('stop');
node('repeat').onclick = () => start({ ...lastConfig, setup: frame.setup ?? [] });
node('loadout').onsubmit = event => {
  event.preventDefault();
  const form = event.target;
  controls('equip', { storage: form.elements.storage.value, kind: form.elements.kind.value || null,
    ...readNumbers(form, ['slot', 'count', 'remaining']) });
};
node('loadout').elements.storage.onchange = () => { updateSlots(); showSlot(); };
node('loadout').elements.slot.onchange = showSlot;
node('loadout').elements.kind.onchange = () => { node('loadout').elements.remaining.value = ''; };
node('player-edit').onsubmit = event => { event.preventDefault(); controls('player', readNumbers(event.target, ['x', 'y', 'temperature', 'hunger', 'money'])); };
node('live-strategy').onchange = event => controls('strategy', { strategy: event.target.value });
node('tile-edit').elements.kind.onchange = event => { node('tile-ammo').hidden = event.target.value !== 'mounted_gun'; };
node('tile-edit').onsubmit = event => {
  event.preventDefault();
  const kind = event.target.elements.kind.value || null;
  controls('tile', { kind, ...readNumbers(event.target, kind === 'mounted_gun' ? ['x', 'y', 'ammo'] : ['x', 'y']) });
};
node('world').onclick = event => {
  if (!frame || node('editor').hidden || !node('terrain-editor').open) return;
  const { x, y } = renderer.screenToWorld(event.clientX, event.clientY);
  node('tile-edit').elements.x.value = Math.round(x);
  node('tile-edit').elements.y.value = Math.round(y);
};
node('monsters').onsubmit = event => {
  event.preventDefault();
  const form = event.target;
  const action = event.submitter?.value ?? 'spawn';
  controls(action, { kind: form.elements.kind.value,
    ...readNumbers(form, action === 'spawn' ? ['count', 'x', 'y'] : ['count', 'interval', 'cap']) });
};
node('clear').onclick = () => controls('clear');
node('password').onchange = () => connection?.close();
window.addEventListener('pagehide', () => connection?.close());
window.addEventListener('cold-world-languagechange', () => { if (options) { populate(); render(); } });

initializeLanguage();
try {
  const [assets, response] = await Promise.all([loadAssets(), fetch('/api/info')]);
  if (!response.ok) throw new Error('catalog_unavailable');
  options = await response.json();
  renderer = new WorldRenderer(node('world'), assets.images, assets.animations, assets.effects, options.catalog, [32, 18], assets.monsterHitboxes);
  populate();
  node('weapon').value = 'handgun';
  node('intensity').value = 'medium';
  node('password-field').hidden = !options.password_required;
  node('password').required = options.password_required;
  status = 'ready';
  render();
  let lastDraw = performance.now();
  function draw(now) {
    if (frame) renderer.draw(status === 'running' ? Math.min(.1, (now - lastDraw) / 1000) : 0);
    lastDraw = now;
    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);
} catch (failure) {
  console.error(failure);
  error('arena_failed');
}
