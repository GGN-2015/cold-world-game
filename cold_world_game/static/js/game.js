import { errorText, tileAt } from './catalog.js';
import { GameConnection } from './network.js';
import { loadAssets, WorldRenderer } from './renderer.js';
import { GameUI } from './ui.js';
import { GameAudio } from './audio.js';

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

function stop() {
  keys.clear();
  attackHeld = false;
  connection.send('stop');
}

function focus() { canvas.focus({ preventScroll: true }); }

function showLoginError(message) {
  byId('login-error').textContent = message;
  byId('login-error').hidden = !message;
  byId('join-button').disabled = false;
  byId('join-button').firstElementChild.textContent = '进入雪原';
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
    ui.toast(errorText(error));
  });
  if (state) ui.update(state);
}

function input() {
  if (!connection.ready || !state) return;
  const horizontal = (keys.has('KeyD') ? 1 : 0) - (keys.has('KeyA') ? 1 : 0);
  const vertical = (keys.has('KeyS') ? 1 : 0) - (keys.has('KeyW') ? 1 : 0);
  const magnitude = Math.max(1, Math.hypot(horizontal, vertical));
  const aim = renderer.pointer.active ? renderer.pointer : state.you;
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
    ui.toast('浏览器禁止了本地存储，本次仍可正常游玩。');
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
  byId('password-toggle').textContent = visible ? '隐藏' : '显示';
  byId('password-toggle').setAttribute('aria-label', visible ? '隐藏口令' : '显示口令');
};

byId('login-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (!initialized) return;
  const credentials = { player_id: byId('player-id').value.trim(), password: byId('server-password').value };
  if (!credentials.player_id || !credentials.password) return;
  showLoginError('');
  byId('join-button').disabled = true;
  byId('join-button').firstElementChild.textContent = '正在走进雪原…';
  connection.connect(credentials);
});

connection.addEventListener('welcome', (event) => {
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
  showLoginError(errorText(event.detail));
});

connection.addEventListener('commanderror', (event) => {
  const text = errorText(event.detail);
  if (text !== lastError || performance.now() - lastErrorTime > 2500) {
    ui.toast(text);
    lastError = text;
    lastErrorTime = performance.now();
  }
});

connection.addEventListener('status', (event) => {
  const { phase, delay } = event.detail;
  const connected = phase === 'connected';
  byId('connection').classList.toggle('warning', !connected);
  byId('connection').lastElementChild.textContent = connected ? '已连接' : '重新连接中';
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
  byId('connection-banner').hidden = connected || !state;
  byId('connection-banner').textContent = `连接中断，${delay ? (delay / 1000).toFixed(1) : '稍后'} 秒后重试。未确认的物品操作不会自动重放。`;
  if (!state && phase === 'reconnecting') {
    byId('server-status').classList.add('offline');
    byId('server-status').lastElementChild.textContent = '暂时连接不上服务器，正在重试…';
  }
});

canvas.addEventListener('pointermove', (event) => {
  pointerClient = { x: event.clientX, y: event.clientY };
  if (renderer) renderer.pointer = { ...renderer.screenToWorld(event.clientX, event.clientY), active: true };
});
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
  if (ui?.dragSource) ui.transfer(ui.dragSource.endpoint, { kind: 'ground' }, ui.dragSource.item);
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
    if (!event.repeat) { stop(); ui.action('drop', { slot: selected }); }
  } else if (event.code === 'KeyB' || event.code === 'KeyI') {
    event.preventDefault();
    if (!event.repeat) ui.togglePanel(event.code === 'KeyB' ? 'craft' : 'inventory');
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
  button.textContent = audio.available ? (audio.muted ? '音效 关' : '音效 开') : '音效不可用';
  button.disabled = !audio.available;
  button.setAttribute('aria-pressed', String(!audio.muted));
  button.setAttribute('aria-label', audio.muted ? '开启音效' : '关闭音效');
  button.title = '开枪、进食和建造音效；仅当前前台窗口播放';
}

byId('sound-button').onclick = () => audio.toggleMute();
audio.addEventListener('change', updateSoundButton);
updateSoundButton();

setInterval(() => {
  if (!connection.ready) return;
  const started = performance.now();
  connection.command('ping').then(() => {
    byId('connection').lastElementChild.textContent = `${Math.round(performance.now() - started)} ms`;
  }).catch(() => {});
}, 4000);

async function initialize() {
  try {
    const [images, response] = await Promise.all([loadAssets(), fetch('/api/info')]);
    if (!response.ok) throw new Error('无法读取服务器规则目录。');
    const catalog = await response.json();
    if (catalog.protocol !== 1) throw new Error('客户端与服务器协议版本不一致，请刷新页面。');
    renderer = new WorldRenderer(canvas, images);
    ui = new GameUI(connection, catalog, { stop, select, selected: () => selected, leave, focus });
    initialized = true;
    byId('join-button').disabled = false;
    requestAnimationFrame(frame);
    fetch('/health').then((reply) => reply.json()).then((health) => {
      byId('server-status').lastElementChild.textContent = health.ok ? `雪原已就绪 · ${health.online} 位旅人在线` : '世界暂时暂停，请检查服务器';
      byId('server-status').classList.toggle('offline', !health.ok);
    }).catch(() => {
      byId('server-status').classList.add('offline');
      byId('server-status').lastElementChild.textContent = '暂时无法获取在线状态，仍可尝试连接。';
    });
  } catch (error) {
    byId('server-status').classList.add('offline');
    byId('server-status').lastElementChild.textContent = '资源加载失败，请刷新页面或检查服务器。';
    byId('login-error').textContent = error.message;
    byId('login-error').hidden = false;
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

initialize();
