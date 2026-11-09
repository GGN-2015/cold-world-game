import { errorText, tileAt } from './catalog.js';
import { GameConnection } from './network.js';
import { loadAssets, WorldRenderer } from './renderer.js';
import { GameUI } from './ui.js';
import { GameAudio } from './audio.js';
import { initializeLanguage, t } from './i18n.js';

const byId = (identifier) => document.getElementById(identifier);
const canvas = byId('world');
const connection = new GameConnection();
const audio = new GameAudio();
const keys = new Set();
let renderer;
let ui;
let state = null;
let selected = 0;
let pendingSelected = false;
let attackHeld = false;
let pointerClient = null;
let initialized = false;
let lastInput = 0;
let lastHint = 0;
let lastFrame = performance.now();
let lastError = '';
let lastErrorTime = 0;
let loginError = null;
let joining = false;
let connectionStatus = { phase: 'connecting' };
let latency = null;
let serverStatus = { key: 'server.loading', parameters: {}, offline: false };

function stop() {
  keys.clear();
  attackHeld = false;
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

function input() {
  if (!connection.ready || !state) return;
  const horizontal = (keys.has('KeyD') ? 1 : 0) - (keys.has('KeyA') ? 1 : 0);
  const vertical = (keys.has('KeyS') ? 1 : 0) - (keys.has('KeyW') ? 1 : 0);
  const magnitude = Math.max(1, Math.hypot(horizontal, vertical));
  const aim = pointerClient ? renderer.screenToWorld(pointerClient.x, pointerClient.y) : { x: state.you.x + 1, y: state.you.y };
  const target = renderer.findTarget();
  connection.send('input', { move: ui.helpOpen || document.hidden ? [0, 0] : [horizontal / magnitude, vertical / magnitude], aim: [aim.x, aim.y], target_id: target?.id || null });
}

function leave() {
  stop();
  audio.reset();
  connection.disconnect();
  state = null;
  ui.reset();
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
  stop();
  audio.reset(event.detail.state.event_sequence || 0);
  pendingSelected = false;
  ui.reset();
  renderer.reset();
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
  renderer.setState(state);
  ui.update(state);
  audio.consume(state);
});

connection.addEventListener('loginerror', (event) => {
  if (state) leave();
  showLoginError(event.detail);
});

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
  renderConnectionStatus();
  if (!connected) {
    audio.stopAll();
    keys.clear();
    attackHeld = false;
    if (state) {
      ui.closePanel(false);
      ui.helpOpen = false;
      byId('help-overlay').hidden = true;
    }
  }
  if (!state && phase === 'reconnecting') {
    setServerStatus('server.retrying', {}, true);
  }
});

canvas.addEventListener('pointermove', (event) => {
  pointerClient = { x: event.clientX, y: event.clientY };
  if (renderer) renderer.pointer = { ...renderer.screenToWorld(event.clientX, event.clientY), active: true };
});
window.addEventListener('pointermove', (event) => { pointerClient = { x: event.clientX, y: event.clientY }; });
canvas.addEventListener('pointerleave', () => { if (renderer) renderer.pointer.active = false; });
canvas.addEventListener('pointerdown', (event) => {
  if (!connection.ready || !state || ui.helpOpen) return;
  event.preventDefault();
  focus();
  renderer.pointer = { ...renderer.screenToWorld(event.clientX, event.clientY), active: true };
  pointerClient = { x: event.clientX, y: event.clientY };
  input();
  if (event.button === 0 && !ui.panel) {
    attackHeld = true;
    connection.send('attack', { pressed: true, shift: event.shiftKey });
  } else if (event.button === 2 && !ui.panel) {
    ui.action('place', { x: tileAt(renderer.pointer.x), y: tileAt(renderer.pointer.y) });
  }
});
window.addEventListener('pointerup', (event) => {
  if (event.button === 0 && attackHeld) {
    attackHeld = false;
    connection.send('attack', { pressed: false });
  }
});
canvas.addEventListener('contextmenu', (event) => event.preventDefault());
const scrollSelect = (event) => {
  if (!connection.ready || ui.helpOpen) return;
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
    input();
    ui.transfer(ui.dragSource.endpoint, { kind: 'ground' }, ui.dragSource.item);
  }
});

window.addEventListener('keydown', (event) => {
  if (!state || !connection.ready || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target.closest('input,textarea,select,[contenteditable="true"]')) return;
  if (event.code === 'Escape') {
    event.preventDefault();
    if (ui.helpOpen) ui.toggleHelp(false);
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
window.addEventListener('blur', () => { stop(); audio.suspendPlayback(); });
window.addEventListener('focus', () => audio.resumePlayback());
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { stop(); audio.suspendPlayback(); }
  else audio.resumePlayback();
});
window.addEventListener('pagehide', () => { stop(); connection.disconnect(); });
window.addEventListener('pointerdown', () => audio.unlock(), { capture: true });
window.addEventListener('keydown', () => audio.unlock(), { capture: true });

function updateSoundButton() {
  const button = byId('sound-button');
  button.textContent = t(audio.available ? (audio.muted ? 'sound.off' : 'sound.on') : 'sound.unavailable');
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
    const [images, response] = await Promise.all([loadAssets(), fetch('/api/info')]);
    if (!response.ok) throw new Error('catalog_unavailable');
    const catalog = await response.json();
    if (catalog.protocol !== 1) throw new Error('protocol_mismatch');
    renderer = new WorldRenderer(canvas, images);
    ui = new GameUI(connection, catalog, { stop, select, selected: () => selected, leave, focus });
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
  if (pointerClient && renderer.pointer.active) renderer.pointer = { ...renderer.screenToWorld(pointerClient.x, pointerClient.y), active: true };
  renderer.panelOpen = ui.isOpen();
  renderer.draw(delta);
  if (now - lastInput >= 65) { input(); lastInput = now; }
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
  ui?.updateHint(renderer?.target);
}

window.addEventListener('cold-world-languagechange', refreshLanguage);
initializeLanguage();
refreshLanguage();
initialize();
