import { getLanguage, t } from './i18n.js';

const byId = identifier => document.getElementById(identifier);

export class ArenaReplay {
  constructor({ request, display, changed, fail }) {
    Object.assign(this, { request, display, changed, fail });
    this.live = null;
    this.record = null;
    this.current = null;
    this.records = [];
    this.cache = new Map();
    this.generation = 0;
    this.playing = false;
    this.loading = false;
    this.clearing = false;
    this.elapsed = 0;
    this.speed = 1;
    byId('timeline').addEventListener('input', () => {
      if (!this.playing && this.live?.status !== 'running') this.seek(Number(byId('timeline').value));
    });
    byId('return-live').addEventListener('click', () => this.returnLive());
    byId('history-refresh').addEventListener('click', () => this.refresh());
    byId('history-delete-all').addEventListener('click', () => this.deleteAll());
    byId('replay-play').addEventListener('click', () => this.toggle());
    byId('replay-speed').addEventListener('change', () => {
      const speed = Number(byId('replay-speed').value);
      if ([0.5, 1, 1.25, 1.5, 2].includes(speed)) this.speed = speed;
    });
  }

  reset() {
    this.generation++;
    this.live = this.record = this.current = null;
    this.playing = this.loading = false;
    this.cache.clear();
    this.render();
  }

  acceptLive(frame) {
    const wasRunning = this.live?.status === 'running';
    if (this.live?.run_id === frame.run_id && this.live.history_deleted) frame.history_deleted = true;
    this.live = frame;
    if (!this.record) {
      this.generation++;
      this.loading = false;
      this.current = frame;
      this.display(frame, { playing: frame.status === 'running', seek: false });
    }
    this.render();
    if (wasRunning !== (frame.status === 'running')) this.renderList();
  }

  render() {
    const total = this.record?.frame_count ?? (this.live && !this.live.history_deleted ? this.live.frame + 1 : 0);
    const seconds = this.record?.seconds ?? this.live?.seconds ?? 0;
    byId('timeline').max = Math.max(0, total - 1);
    byId('timeline').value = this.current?.frame ?? 0;
    byId('timeline').disabled = !total || this.playing || this.live?.status === 'running';
    byId('timeline-time').textContent = `${(this.current?.seconds ?? 0).toFixed(2)} / ${seconds.toFixed(2)} s`;
    byId('return-live').disabled = !this.live || !this.record && this.current?.frame === this.live.frame;
    byId('replay-controls').hidden = !this.record;
    byId('replay-play').disabled = this.loading || !total;
    byId('replay-play').textContent = t(this.playing ? 'arena.pauseReplay' : 'arena.playReplay');
    for (const button of byId('history-list').querySelectorAll('[data-action="watch"]')) button.disabled = this.clearing || this.live?.status === 'running';
  }

  renderList() {
    const container = byId('history-list');
    byId('history-delete-all').disabled = this.clearing || !this.records.length;
    if (!this.records.length) { container.textContent = t('arena.historyEmpty'); return; }
    container.replaceChildren(...this.records.map(record => {
      const row = document.createElement('article');
      row.className = 'history-record';
      row.dataset.id = record.id;
      const text = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = new Date(record.created_at).toLocaleString(getLanguage() === 'en' ? 'en-US' : 'zh-CN');
      const details = document.createElement('p');
      details.className = 'hint';
      details.textContent = t('arena.recordDetails', { seed: record.config.seed, seconds: record.seconds.toFixed(2), kills: record.kills, status: t(`arena.record.${record.status}`) });
      text.append(title, details);
      const actions = document.createElement('div');
      actions.className = 'record-actions';
      const watch = document.createElement('button');
      watch.type = 'button'; watch.textContent = t('arena.historyWatch'); watch.dataset.action = 'watch';
      watch.disabled = this.clearing || this.live?.status === 'running' || !record.frame_count;
      watch.addEventListener('click', () => this.open(record.id));
      const remove = document.createElement('button');
      remove.type = 'button'; remove.textContent = t('arena.historyDelete'); remove.dataset.action = 'delete';
      remove.disabled = this.clearing;
      remove.addEventListener('click', async () => {
        if (!confirm(t('arena.historyConfirm'))) return;
        try {
          await this.request(`/api/history/${record.id}`, { method: 'DELETE' });
          this.discard([record.id]);
          await this.refresh();
        } catch (error) { this.fail(error.message); }
      });
      actions.append(watch, remove); row.append(text, actions);
      return row;
    }));
  }

  async refresh() {
    try {
      const response = await this.request('/api/history');
      this.records = response.records;
      byId('history-directory').textContent = response.directory;
      this.renderList();
    } catch (error) { this.fail(error.message); }
  }

  discard(identifiers) {
    const liveDeleted = identifiers.includes(this.live?.run_id);
    if (liveDeleted) this.live.history_deleted = true;
    if (identifiers.includes(this.record?.id) || liveDeleted && !this.record) this.returnLive();
    this.render();
  }

  async deleteAll() {
    if (this.clearing || !this.records.length || !confirm(t('arena.historyConfirmAll'))) return;
    this.clearing = true;
    this.renderList();
    try {
      const response = await this.request('/api/history', { method: 'DELETE' });
      this.discard(response.deleted);
      await this.refresh();
    } catch (error) { this.fail(error.message); }
    finally { this.clearing = false; this.renderList(); }
  }

  async open(identifier) {
    if (this.clearing || this.live?.status === 'running') return;
    const generation = ++this.generation;
    this.playing = false;
    this.cache.clear();
    try {
      const record = await this.request(`/api/history/${identifier}`);
      if (generation !== this.generation) return;
      this.record = record;
      await this.seek(0);
      byId('battle-heading').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) { this.fail(error.message); }
  }

  async seek(index, playback = false) {
    if (!this.record && this.live?.history_deleted) return;
    const identifier = this.record?.id ?? this.live?.run_id;
    if (!identifier) return;
    const generation = ++this.generation;
    this.loading = true;
    try {
      if (!this.cache.has(index)) {
        const response = await this.request(`/api/history/${identifier}/frames?start=${index}&limit=64`);
        if (generation !== this.generation) return;
        this.cache.clear();
        for (const frame of response.frames) this.cache.set(frame.frame, frame);
      }
      if (generation !== this.generation) return;
      const frame = this.cache.get(index);
      if (!frame) throw new Error('arena_history_missing');
      this.current = frame;
      this.display(frame, { playing: this.playing, seek: !playback, catalog: this.record?.catalog });
      this.render(); this.changed();
    } catch (error) {
      if (generation === this.generation) { this.playing = false; this.fail(error.message); this.changed(); }
    } finally { if (generation === this.generation) { this.loading = false; this.render(); this.changed(); } }
  }

  returnLive() {
    this.generation++;
    this.record = null; this.playing = this.loading = false;
    this.cache.clear();
    this.current = this.live;
    this.display(this.live, { seek: true, playing: this.live?.status === 'running' });
    this.render(); this.changed();
  }

  async toggle() {
    if (!this.record || this.loading) return;
    this.playing = !this.playing;
    this.elapsed = 0;
    if (this.playing && this.current?.frame >= this.record.frame_count - 1) await this.seek(0);
    if (this.current) this.display(this.current, { seek: true, playing: this.playing, catalog: this.record.catalog });
    this.render(); this.changed();
  }

  advance(seconds) {
    if (!this.playing || !this.current || this.loading) return;
    if (this.current.frame >= this.record.frame_count - 1) {
      this.playing = false;
      this.display(this.current, { seek: true, playing: false, catalog: this.record.catalog });
      this.render(); this.changed();
      return;
    }
    this.elapsed += seconds * this.speed;
    const next = this.cache.get(this.current.frame + 1);
    const interval = next ? next.seconds - this.current.seconds : 0.1;
    if (this.elapsed >= interval) {
      this.elapsed -= interval;
      this.seek(this.current.frame + 1, true);
    }
  }
}
