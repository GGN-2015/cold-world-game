import { t } from './i18n.js';

const element = (tag, className = '', text = '') => {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
};
const setText = (node, text) => { if (node.textContent !== text) node.textContent = text; };

export function lastLoginText(timestamp, now) {
  if (!Number.isFinite(timestamp)) return t('players.unknownLogin');
  const seconds = Math.max(0, now - timestamp);
  if (seconds <= 300) return t('players.justNow');
  if (seconds < 3600) return t('players.minutesAgo', { count: Math.floor(seconds / 60) });
  if (seconds < 86400) return t('players.hoursAgo', { count: Math.floor(seconds / 3600) });
  return t('players.daysAgo', { count: Math.floor(seconds / 86400) });
}

export class PlayerRoster {
  constructor(controls) {
    this.controls = controls;
    this.root = document.getElementById('player-roster');
    this.button = document.getElementById('players-button');
    this.list = document.getElementById('players-list');
    this.rows = new Map();
    this.groups = [element('div', 'roster-group'), element('div', 'roster-group offline')];
    this.reset();
    this.button.addEventListener('click', () => {
      if (this.expanded) this.collapse();
      else {
        this.controls.open();
        this.expanded = true;
        this.root.hidden = false;
        this.button.setAttribute('aria-expanded', 'true');
        this.refresh();
      }
    });
    document.getElementById('players-close').addEventListener('click', () => { this.collapse(); this.button.focus({ preventScroll: true }); });
    this.root.addEventListener('pointerdown', (event) => { event.stopPropagation(); this.controls.stop(); });
    window.addEventListener('cold-world-languagechange', () => this.refresh());
    document.addEventListener('visibilitychange', () => { if (!document.hidden) this.refresh(); });
    new ResizeObserver(() => {
      const bounds = document.querySelector('.game-header').getBoundingClientRect();
      document.documentElement.style.setProperty('--roster-top', `${bounds.bottom + 18}px`);
    }).observe(document.querySelector('.game-header'));
    setInterval(() => { if (!document.hidden && this.expanded) this.refresh(); }, 1000);
  }

  reset(playerId = null) {
    this.playerId = playerId;
    this.data = null;
    this.connected = false;
    this.received = 0;
    this.order = '';
    this.rows.clear();
    this.list.replaceChildren();
    this.collapse();
    this.refresh();
  }

  collapse() {
    this.expanded = false;
    this.root.hidden = true;
    this.button.setAttribute('aria-expanded', 'false');
  }

  update(data) {
    this.data = data;
    this.received = performance.now() / 1000;
    this.refresh();
  }

  setConnected(connected) {
    this.connected = connected;
    this.refresh();
  }

  row(player) {
    let row = this.rows.get(player.id);
    if (row) return row;
    const card = element('article', 'roster-player');
    card.setAttribute('role', 'listitem');
    card.dataset.playerId = player.id;
    const portrait = element('div', 'roster-portrait');
    const image = document.createElement('img');
    image.alt = '';
    portrait.append(image, element('i', 'roster-status-dot'));
    const identity = element('div', 'roster-identity');
    const name = element('strong', 'roster-name', player.id);
    name.title = player.id;
    const self = element('span', 'roster-self');
    const status = element('span', 'roster-status');
    identity.append(name, self, status);
    const heading = element('div', 'roster-player-heading');
    heading.append(portrait, identity);
    const stats = element('dl', 'roster-stats');
    const values = {};
    for (const stat of ['hunger', 'temperature', 'money']) {
      const cell = element('div', `roster-stat ${stat}`);
      const label = element('dt');
      const value = element('dd');
      cell.append(label, value);
      stats.append(cell);
      values[stat] = { label, value };
    }
    const seen = element('p', 'roster-last-login');
    card.append(heading, stats, seen);
    row = { card, image, self, status, values, seen };
    this.rows.set(player.id, row);
    return row;
  }

  refresh() {
    const players = this.data?.players || [];
    const online = players.filter((player) => player.online).length;
    setText(document.getElementById('players-count'), String(online));
    this.button.setAttribute('aria-label', t('players.toggle', { online, total: players.length }));
    this.button.title = t('players.toggle', { online, total: players.length });
    this.root.classList.toggle('stale', !this.connected);
    if (!this.expanded) return;
    setText(document.getElementById('players-summary'), t('players.summary', { online, total: players.length }));
    setText(document.getElementById('players-footer'), t(this.connected ? 'players.footer' : 'players.reconnecting'));
    const now = (this.data?.server_time || 0) + Math.max(0, performance.now() / 1000 - this.received);
    const ordered = [];
    for (const [index, active] of [true, false].entries()) {
      const group = players.filter((player) => player.online === active);
      if (!group.length) continue;
      setText(this.groups[index], t(active ? 'players.onlineGroup' : 'players.offlineGroup', { count: group.length }));
      ordered.push(this.groups[index]);
      for (const player of group) {
        const row = this.row(player);
        row.card.classList.toggle('online', active);
        row.card.classList.toggle('offline', !active);
        const source = `/static/assets/roster_${active ? 'online' : 'offline'}.png`;
        if (row.image.getAttribute('src') !== source) row.image.src = source;
        row.self.hidden = player.id !== this.playerId;
        setText(row.self, t('players.you'));
        setText(row.status, t(active ? 'players.online' : 'players.offline'));
        for (const stat of ['hunger', 'temperature', 'money']) setText(row.values[stat].label, t(`players.${stat}`));
        setText(row.values.hunger.value, player.hunger.toFixed(1));
        setText(row.values.temperature.value, `${player.temperature.toFixed(1)}°C`);
        setText(row.values.money.value, String(player.money));
        row.values.hunger.value.classList.toggle('warning', player.hunger < 5);
        row.values.temperature.value.classList.toggle('warning', player.temperature < 5);
        row.seen.hidden = active;
        if (!active) setText(row.seen, t('players.lastLogin', { time: lastLoginText(player.last_login_at, now) }));
        ordered.push(row.card);
      }
    }
    const order = JSON.stringify(players.map((player) => [player.id, player.online]));
    if (order !== this.order) {
      const scroll = this.list.scrollTop;
      this.list.replaceChildren(...ordered);
      this.list.scrollTop = scroll;
      this.order = order;
      const identifiers = new Set(players.map((player) => player.id));
      for (const identifier of this.rows.keys()) if (!identifiers.has(identifier)) this.rows.delete(identifier);
    }
    document.getElementById('players-empty').hidden = players.length > 0;
  }
}
