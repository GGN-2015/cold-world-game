import { buildings, containers, errorText, seats, tileAt } from './catalog.js';
import { GameConnection } from './network.js';
import { loadAssets, WorldRenderer } from './renderer.js';
import { GameUI } from './ui.js';
import { GameAudio } from './audio.js';
import { GameMusic } from './music.js';
import { initializeLanguage, t } from './i18n.js';
import { isMobileDevice, MobileControls } from './mobile.js';
import { PlayerRoster } from './roster.js';
import { LocalCombat } from './combat.js';
import { AdminConsole } from './admin.js';
import { GameCompass } from './compass.js';

const byId = (identifier) => document.getElementById(identifier);
const canvas = byId('world');
const connection = new GameConnection();
const audio = new GameAudio();
const music = new GameMusic();
const compass = new GameCompass();
const keys = new Set();
let renderer;
let ui;
let playerRoster;
let localCombat;
let adminConsole;
let state = null;
let selected = 0;
let pendingSelected = false;
let attackHeld = false;
let pointerClient = null;
let mobileControls;
let mobileMove = { x: 0, y: 0 };
let mobileAim = { x: 2, y: 0 };
let initialized = false;
let lastInput = 0;
let lastHint = 0;
let lastMusic = 0;
let lastFrame = performance.now();
let lastError = '';
let lastErrorTime = 0;
let loginError = null;
let joining = false;
let connectionStatus = { phase: 'connecting' };
let latency = null;
let serverStatus = { key: 'server.loading', parameters: {}, offline: false };

function stop() {
  ui?.cancelDemolition();
  keys.clear();
  attackHeld = false;
  mobileMove = { x: 0, y: 0 };
  renderer?.movement.setInput(0, 0);
  mobileControls?.reset();
  if (connection.ready && state) input(true);
  connection.send('stop');
}

function focus() { canvas.focus({ preventScroll: true }); }

function renderLogin() {
  byId('login-error').textContent = loginError ? errorText(loginError) : '';
  byId('login-error').hidden = !loginError;
  byId('join-button').disabled = !initialized || joining;
  byId('join-button').firstElementChild.textContent = t(joining ? 'login.joining' : 'login.join');
  const visible = byId('server-password').type === 'text';
  byId('password-toggle').textContent = t(visible ? 'login.hide' : 'login.show');
  byId('password-toggle').setAttribute('aria-label', t(visible ? 'login.hidePassword' : 'login.showPassword'));
}

function showLoginError(error) {
  loginError = error;
  joining = false;
  renderLogin();
}

function renderServerStatus() {
  byId('server-status').lastElementChild.textContent = t(serverStatus.key, serverStatus.parameters);
  byId('server-status').classList.toggle('offline', serverStatus.offline);
}

function setServerStatus(key, parameters = {}, offline = false) {
  serverStatus = { key, parameters, offline };
  renderServerStatus();
}

function renderConnectionStatus() {
  const connected = connectionStatus.phase === 'connected';
  byId('connection').classList.toggle('warning', !connected);
  byId('connection').lastElementChild.textContent = connected && latency != null ? `${latency} ms` : t(`connection.${connectionStatus.phase}`);
  byId('connection-banner').hidden = !state || (connected && !state.fault);
  byId('connection-banner').textContent = state?.fault ? t('connection.fault') : t('connection.retry', { seconds: connectionStatus.delay ? (connectionStatus.delay / 1000).toFixed(1) : t('connection.wait') });
}

function select(slot) {
  if (!connection.ready || slot < 0 || slot > 9) return;
  attackHeld = false;
  connection.send('attack', { pressed: false });
  selected = slot;
  pendingSelected = true;
  renderer.selected = slot;
  connection.command('select', { slot }).catch((error) => {
    pendingSelected = false;
    ui.toast(() => errorText(error));
  });
  if (state) ui.update(state);
}

function aimPoint() {
  const player = renderer.movement.enabled ? renderer.movement.position : state.you;
  if (isMobileDevice) return { x: player.x + mobileAim.x, y: player.y + mobileAim.y };
  return pointerClient ? renderer.screenToWorld(pointerClient.x, pointerClient.y) : { x: player.x + 1, y: player.y };
}

function updateMovement() {
  if (!renderer) return;
  const horizontal = (keys.has('KeyD') ? 1 : 0) - (keys.has('KeyA') ? 1 : 0) + mobileMove.x;
  const vertical = (keys.has('KeyS') ? 1 : 0) - (keys.has('KeyW') ? 1 : 0) + mobileMove.y;
  const active = Boolean(connection.ready && state && !ui.helpOpen && !adminConsole?.expanded && !document.hidden && (!isMobileDevice || !ui.isOpen()));
  renderer.movement.active = active;
  renderer.movement.setInput(active ? horizontal : 0, active ? vertical : 0);
}

function input(force = false) {
  if (!connection.ready || !state) return;
  updateMovement();
  const now = performance.now();
  if (!force && now - lastInput < 50) return;
  const aim = aimPoint();
  if (isMobileDevice) renderer.pointer = { ...aim, active: true };
  const target = renderer.findTarget();
  if (connection.send('input', { move: [renderer.movement.input.x, renderer.movement.input.y], aim: [aim.x, aim.y], target_id: target?.id || null, viewport: renderer.viewport(), ...renderer.movement.report() })) lastInput = now;
}

function leave() {
  stop();
  compass.reset();
  music.leave();
  localCombat.reset();
  audio.reset();
  connection.disconnect();
  state = null;
  ui.reset();
  playerRoster.reset();
  adminConsole?.update(null);
  renderer.reset();
  pendingSelected = false;
  byId('game-hud').hidden = true;
  byId('login-screen').hidden = false;
  byId('connection-banner').hidden = true;
  showLoginError('');
  byId('player-id').focus();
}

function rememberCredentials(credentials) {
  try {
    if (byId('remember-login').checked) localStorage.setItem('cold-world-login-v1', JSON.stringify(credentials));
    else localStorage.removeItem('cold-world-login-v1');
  } catch {
    ui.toast(() => t('login.storageUnavailable'));
  }
}

byId('join-button').disabled = true;
try {
  const remembered = JSON.parse(localStorage.getItem('cold-world-login-v1') || 'null');
  if (remembered && typeof remembered.player_id === 'string' && typeof remembered.password === 'string') {
    byId('player-id').value = remembered.player_id;
    byId('server-password').value = remembered.password;
  }
} catch {}

byId('password-toggle').onclick = () => {
  const input = byId('server-password');
  const visible = input.type === 'password';
  input.type = visible ? 'text' : 'password';
  renderLogin();
};

byId('login-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (!initialized) return;
  const credentials = { player_id: byId('player-id').value.trim(), password: byId('server-password').value };
  if (!credentials.player_id || !credentials.password) return;
  showLoginError('');
  joining = true;
  renderLogin();
  connection.connect(credentials);
});

connection.addEventListener('welcome', (event) => {
  joining = false;
  state = null;
  localCombat.reset();
  renderer.reset();
  compass.configure(event.detail.navigation_config);
  stop();
  audio.reset(event.detail.state.event_sequence || 0);
  music.enter();
  pendingSelected = false;
  ui.reset();
  playerRoster.reset(event.detail.player_id);
  byId('login-screen').hidden = true;
  byId('game-hud').hidden = false;
  rememberCredentials(connection.credentials);
  focus();
});

connection.addEventListener('state', (event) => {
  state = event.detail;
  if (!pendingSelected || state.you.selected === selected) {
    selected = state.you.selected;
    pendingSelected = false;
  }
  renderer.selected = selected;
  const visualState = localCombat.reconcile(state);
  renderer.setState(visualState);
  adminConsole.update(state);
  ui.update(state);
  audio.consume(visualState);
});

connection.addEventListener('loginerror', (event) => {
  if (state) leave();
  showLoginError(event.detail);
});

connection.addEventListener('roster', (event) => playerRoster.update(event.detail));

connection.addEventListener('commanderror', (event) => {
  const text = errorText(event.detail);
  if (text !== lastError || performance.now() - lastErrorTime > 2500) {
    ui.toast(() => errorText(event.detail));
    lastError = text;
    lastErrorTime = performance.now();
  }
});

connection.addEventListener('status', (event) => {
  connectionStatus = event.detail;
  latency = null;
  const { phase } = connectionStatus;
  const connected = phase === 'connected';
  playerRoster?.setConnected(connected);
  renderConnectionStatus();
  if (!connected) {
    localCombat?.reset();
    audio.stopAll();
    if (music.active) music.suspend();
    stop();
    if (state) {
      ui.closePanel(false);
      ui.helpOpen = false;
      byId('help-overlay').hidden = true;
    }
  }
  if (connected && music.active) music.unlock();
  if (!state && phase === 'reconnecting') {
    setServerStatus('server.retrying', {}, true);
  }
});

function attack(pressed, shift = false) {
  const fresh = pressed && !attackHeld;
  attackHeld = pressed;
  input(true);
  const attackId = fresh && state.you.seated !== 'mounted_gun' ? localCombat.begin(state, selected, aimPoint()) : null;
  if (!attackId) { connection.send('attack', { pressed, shift }); return; }
  connection.command('attack', { pressed, shift, attack_id: attackId }).then((result) => {
    if (result.swing !== true) localCombat.reject(attackId);
  }).catch(() => localCombat.reject(attackId));
}

canvas.addEventListener('pointermove', (event) => {
  if (isMobileDevice) return;
  pointerClient = { x: event.clientX, y: event.clientY };
  if (renderer) renderer.pointer = { ...renderer.screenToWorld(event.clientX, event.clientY), active: true };
});
window.addEventListener('pointermove', (event) => { if (!isMobileDevice) pointerClient = { x: event.clientX, y: event.clientY }; });
canvas.addEventListener('pointerleave', () => { if (renderer && !isMobileDevice) renderer.pointer.active = false; });
canvas.addEventListener('pointerdown', (event) => {
  if (isMobileDevice) return;
  if (!connection.ready || !state || ui.helpOpen || adminConsole?.expanded) return;
  event.preventDefault();
  focus();
  renderer.pointer = { ...renderer.screenToWorld(event.clientX, event.clientY), active: true };
  pointerClient = { x: event.clientX, y: event.clientY };
  if (event.button === 0 && !ui.panel) {
    const item = state.you.inventory[selected];
    const point = { x: tileAt(renderer.pointer.x), y: tileAt(renderer.pointer.y) };
    const container = state.structures.some((entity) => containers.has(entity.kind) && entity.x === point.x && entity.y === point.y);
    const seat = state.structures.find(entity => seats.has(entity.kind) && entity.x === point.x && entity.y === point.y);
    if (state.you.seated === 'mounted_gun') {
      attack(true, event.shiftKey);
    } else if (seat && !event.shiftKey) {
      stop(); input(true); ui.action('sit', { id: seat.id });
    } else if (buildings.has(item?.kind) && (!container || event.shiftKey)) {
      input(true);
      attackHeld = false;
      connection.send('attack', { pressed: false });
      ui.action('place', point);
    } else {
      attack(true, event.shiftKey);
    }
  }
});
window.addEventListener('pointerup', (event) => {
  if (isMobileDevice) return;
  if (event.button === 0 && attackHeld) {
    attack(false);
  }
});
canvas.addEventListener('contextmenu', (event) => event.preventDefault());
const scrollSelect = (event) => {
  if (!connection.ready || ui.helpOpen || adminConsole?.expanded) return;
  event.preventDefault();
  if (Math.abs(event.deltaY) < 1) return;
  const now = performance.now();
  if (now - (scrollSelect.last || 0) < 110) return;
  scrollSelect.last = now;
  select((selected + (event.deltaY > 0 ? 1 : 9)) % 10);
};
canvas.addEventListener('wheel', scrollSelect, { passive: false });
byId('hotbar').addEventListener('wheel', scrollSelect, { passive: false });
canvas.addEventListener('dragover', (event) => { if (ui?.dragSource) event.preventDefault(); });
canvas.addEventListener('drop', (event) => {
  event.preventDefault();
  if (ui?.dragSource) {
    pointerClient = { x: event.clientX, y: event.clientY };
    input(true);
    ui.transfer(ui.dragSource.endpoint, { kind: 'ground' }, ui.dragSource.item);
  }
});

window.addEventListener('keydown', (event) => {
  if (!state || !connection.ready || event.ctrlKey || event.metaKey || event.altKey) return;
  if (adminConsole?.expanded) {
    if (event.code === 'Escape') { event.preventDefault(); adminConsole.toggle(false); }
    return;
  }
  if (event.target.closest('input,textarea,select,[contenteditable="true"]')) return;
  if (event.code === 'Escape') {
    event.preventDefault();
    if (ui.helpOpen) ui.toggleHelp(false);
    else if (playerRoster.expanded) playerRoster.collapse();
    else ui.closePanel();
    stop(); focus(); return;
  }
  if (event.code === 'KeyH' || event.key === '?') {
    if (!event.repeat) ui.toggleHelp();
    event.preventDefault(); return;
  }
  if (ui.helpOpen) return;
  if (['KeyW', 'KeyA', 'KeyS', 'KeyD'].includes(event.code)) {
    event.preventDefault();
    keys.add(event.code);
    input();
  } else if (/^Digit[0-9]$/.test(event.code)) {
    event.preventDefault();
    if (!event.repeat) select((Number(event.code.slice(-1)) + 9) % 10);
  } else if (event.code === 'KeyQ') {
    event.preventDefault();
    if (!event.repeat) { stop(); input(); ui.action('drop', { slot: selected }); }
  } else if (event.code === 'KeyB' || event.code === 'KeyI') {
    event.preventDefault();
    if (!event.repeat) ui.togglePanel('inventory');
  }
});
window.addEventListener('keyup', (event) => {
  if (keys.delete(event.code)) input();
});
window.addEventListener('blur', () => { stop(); audio.suspendPlayback(); music.suspend(); });
window.addEventListener('focus', () => { audio.resumePlayback(); music.unlock(); });
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { stop(); audio.suspendPlayback(); music.suspend(); renderer?.effects.clear(); renderer?.motion.reset(); renderer?.movement.reset(); renderer?.positions.clear(); renderer?.animator.reset(); }
  else { audio.resumePlayback(); music.unlock(); }
});
window.addEventListener('pagehide', () => { stop(); connection.disconnect(); });
window.addEventListener('pointerdown', () => { audio.unlock(); music.unlock(); }, { capture: true });
window.addEventListener('keydown', () => { audio.unlock(); music.unlock(); }, { capture: true });

function updateMusicButton() {
  const button = byId('music-button');
  button.textContent = isMobileDevice ? (music.muted ? '♫×' : '♫') : t(music.muted ? 'music.off' : 'music.on');
  button.disabled = !music.available;
  button.setAttribute('aria-pressed', String(!music.muted));
  button.setAttribute('aria-label', t(music.muted ? 'music.enable' : 'music.disable'));
  button.title = t(!music.available ? 'music.unavailable' : music.urls.size < music.tracks.length || !music.tracks.length ? 'music.preloading' : 'music.hint');
}

byId('music-button').onclick = () => music.toggle();
music.addEventListener('change', updateMusicButton);
updateMusicButton();

function updateSoundButton() {
  const button = byId('sound-button');
  const prefix = isMobileDevice ? 'touch.sound' : 'sound';
  button.textContent = t(audio.available ? (audio.muted ? `${prefix}.off` : `${prefix}.on`) : `${prefix}.unavailable`);
  button.disabled = !audio.available;
  button.setAttribute('aria-pressed', String(!audio.muted));
  button.setAttribute('aria-label', t(audio.muted ? 'sound.enable' : 'sound.disable'));
  button.title = t('sound.hint');
}

byId('sound-button').onclick = () => audio.toggleMute();
audio.addEventListener('change', updateSoundButton);
updateSoundButton();

setInterval(() => {
  if (!connection.ready) return;
  const started = performance.now();
  connection.command('ping').then(() => {
    latency = Math.round(performance.now() - started);
    renderConnectionStatus();
  }).catch(() => {});
}, 4000);

async function initialize() {
  try {
    const [assets, response] = await Promise.all([loadAssets(), fetch('/api/info')]);
    if (!response.ok) throw new Error('catalog_unavailable');
    const catalog = await response.json();
    if (catalog.protocol !== 1) throw new Error('protocol_mismatch');
    renderer = new WorldRenderer(canvas, assets.images, assets.animations, assets.effects, catalog, null, assets.monsterHitboxes);
    localCombat = new LocalCombat(renderer, audio, catalog);
    ui = new GameUI(connection, catalog, { stop, select, selected: () => selected, leave, focus, adminOpen: () => adminConsole?.expanded, closeAdmin: () => adminConsole?.toggle(false), closeRoster: () => playerRoster?.collapse(), dropItem: (source) => {
      stop(); input();
      ui.transfer(source.endpoint, { kind: 'ground' }, source.item);
    } });
    playerRoster = new PlayerRoster({ stop, open: () => {
      adminConsole?.toggle(false);
      if (ui.helpOpen) ui.toggleHelp(false);
      else ui.closePanel();
      stop();
    } });
    adminConsole = new AdminConsole(connection, { stop, focus, prepare: () => {
      playerRoster.collapse();
      if (ui.helpOpen) ui.toggleHelp(false);
      ui.closePanel(false);
    } });
    mobileControls = new MobileControls(canvas, {
      canPlay: () => Boolean(connection.ready && state && !ui.isOpen() && !playerRoster.expanded && !document.hidden),
      cancel: stop,
      move: (vector) => { mobileMove = vector; input(); },
      aim: (vector) => {
        if (Math.hypot(vector.x, vector.y) > 0.12) mobileAim = { x: vector.x * 3, y: vector.y * 3 };
        input();
      },
      aimPoint: (horizontal, vertical) => {
        const point = renderer.screenToWorld(horizontal, vertical);
        const player = renderer.movement.enabled ? renderer.movement.position : state.you;
        mobileAim = { x: point.x - player.x, y: point.y - player.y };
        input();
      },
      use: attack,
      useAtPoint: () => {
        const point = aimPoint();
        return Boolean(state?.you.seated === 'mounted_gun' || state?.structures.some(entity => seats.has(entity.kind) && entity.x === tileAt(point.x) && entity.y === tileAt(point.y)) || catalog.explosive_weapons?.[state?.you.inventory[selected]?.kind] || catalog.revival_items?.[state?.you.inventory[selected]?.kind]);
      },
      place: () => { input(true); const point = aimPoint(); ui.action('place', { x: tileAt(point.x), y: tileAt(point.y) }); },
      drop: () => { stop(); input(); ui.action('drop', { slot: selected }); },
    });
    initialized = true;
    renderLogin();
    requestAnimationFrame(frame);
    fetch('/health').then((reply) => reply.json()).then((health) => {
      setServerStatus(health.ok ? 'server.ready' : 'server.paused', { online: health.online }, !health.ok);
    }).catch(() => {
      setServerStatus('server.unreachable', {}, true);
    });
  } catch (error) {
    setServerStatus('server.loadFailed', {}, true);
    showLoginError(error);
    console.error(error);
  }
}

function frame(now) {
  const delta = Math.min((now - lastFrame) / 1000, 0.1);
  lastFrame = now;
  if (isMobileDevice && state) renderer.pointer = { ...aimPoint(), active: true };
  else if (pointerClient && renderer.pointer.active) renderer.pointer = { ...renderer.screenToWorld(pointerClient.x, pointerClient.y), active: true };
  renderer.panelOpen = ui.isOpen();
  mobileControls?.sync();
  updateMovement();
  renderer.draw(delta);
  compass.update(now, Boolean(state && connection.ready && ui.hasCompass), renderer.camera, renderer.camera, renderer.viewport());
  if (now - lastInput >= 50) input();
  if (state && connection.ready && now - lastMusic >= 500) {
    music.observe(state, renderer.camera, renderer.viewport(), renderer.positions, renderer.catalog.monster_types, now);
    lastMusic = now;
  }
  if (now - lastHint >= 150) {
    ui.updateHint(renderer.target);
    byId('fps-label').textContent = `${Math.round(renderer.fps)} FPS`;
    lastHint = now;
  }
  requestAnimationFrame(frame);
}

function refreshLanguage() {
  renderLogin();
  renderServerStatus();
  renderConnectionStatus();
  updateSoundButton();
  updateMusicButton();
  ui?.updateHint(renderer?.target);
  adminConsole?.refreshLanguage();
}

window.addEventListener('cold-world-languagechange', refreshLanguage);
initializeLanguage();
refreshLanguage();
initialize();
