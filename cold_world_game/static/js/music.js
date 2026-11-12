export function threatLevel(score) {
  return score > 12.5 ? 'high' : score > 6.5 ? 'medium' : 'calm';
}

export function visibleThreat(state, camera, viewport, positions, types = {}) {
  let score = 0;
  for (const monster of state.monsters) {
    if (monster.hp <= 0 || monster.sleeping || monster.rising != null) continue;
    const point = positions?.get(monster.id) || monster;
    if (Math.abs(point.x - camera.x) > viewport[0] / 2 || Math.abs(point.y - camera.y) > viewport[1] / 2) continue;
    const species = monster.species || (monster.big ? 'big' : monster.fast ? 'fast' : 'small');
    score += types[species]?.score ?? (monster.big ? 4 : monster.fast ? 2.5 : 1);
  }
  return score;
}

export class GameMusic extends EventTarget {
  constructor() {
    super();
    this.available = Boolean(window.AudioContext || window.webkitAudioContext);
    this.muted = false;
    try { this.muted = localStorage.getItem('cold-world-music-muted-v1') === 'true'; } catch {}
    this.tracks = [];
    this.urls = new Map();
    this.slots = [];
    this.active = false;
    this.suspended = false;
    this.score = 0;
    this.tier = 'calm';
    this.pendingTier = 'calm';
    this.pendingSince = 0;
    this.cursor = 0;
    this.prepare();
  }

  changed() { this.dispatchEvent(new Event('change')); }

  async prepare() {
    if (!this.available || this.active || this.loading) return;
    this.loading = true;
    const controller = new AbortController();
    this.controller = controller;
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      if (!this.tracks.length) {
        const response = await fetch('/static/music/manifest.json', { signal: controller.signal });
        if (!response.ok) throw new Error('music_manifest');
        this.tracks = (await response.json()).tracks;
      }
      const groups = ['calm', 'medium', 'high'].map(tier => this.tracks.filter(track => track.tier === tier));
      const order = groups[0].flatMap((track, index) => groups.map(group => group[index]).filter(Boolean));
      for (const track of order) {
        if (this.active || controller.signal.aborted) break;
        if (this.urls.has(track.id)) continue;
        try {
          const response = await fetch(`/static/music/${track.file}`, { signal: controller.signal });
          if (!response.ok) continue;
          const blob = await response.blob();
          if (!this.active && !controller.signal.aborted) this.urls.set(track.id, URL.createObjectURL(blob));
          this.changed();
        } catch {
          if (controller.signal.aborted) break;
        }
      }
    } catch {} finally {
      clearTimeout(timeout);
      this.loading = false;
      this.changed();
      if (!this.active && controller.signal.aborted && (!this.tracks.length || this.urls.size < this.tracks.length)) {
        clearTimeout(this.retry);
        this.retry = setTimeout(() => this.prepare(), 10000);
      }
    }
  }

  unlock() {
    if (!this.available || this.muted || document.hidden) return;
    try {
      if (!this.context) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        this.context = new AudioContext();
        this.master = this.context.createGain();
        this.master.gain.value = 0.075;
        this.master.connect(this.context.destination);
        for (let index = 0; index < 2; index++) {
          const audio = new Audio();
          audio.preload = 'auto';
          audio.setAttribute('playsinline', '');
          const gain = this.context.createGain();
          gain.gain.value = 0;
          const source = this.context.createMediaElementSource(audio);
          source.connect(gain);
          gain.connect(this.master);
          const slot = { audio, gain, source, track: null };
          audio.addEventListener('ended', () => {
            if (this.current === slot) {
              this.current = null;
              this.nextAt = performance.now() + 2000;
            }
          });
          this.slots.push(slot);
        }
      }
      this.context.resume().catch(() => {});
      if (!this.active) {
        const track = this.tracks.find(entry => this.urls.has(entry.id));
        if (track) for (const slot of this.slots) {
          if (!slot.audio.src) slot.audio.src = this.urls.get(track.id);
          slot.audio.play().then(() => { if (!this.active) slot.audio.pause(); }).catch(() => {});
        }
      }
      this.suspended = false;
    } catch {
      this.available = false;
      this.changed();
    }
  }

  enter() {
    this.active = true;
    clearTimeout(this.fadeTimer);
    for (const slot of this.slots) slot.audio.pause();
    this.current = null;
    this.switching = false;
    this.controller?.abort();
    clearTimeout(this.retry);
    this.pendingSince = performance.now();
    this.nextAt = 0;
    this.changed();
  }

  leave() {
    this.active = false;
    this.fadeOut();
    this.prepare();
  }

  fadeOut(duration = 0.4) {
    clearTimeout(this.fadeTimer);
    this.switching = false;
    this.current = null;
    if (!this.context) return;
    const now = this.context.currentTime;
    for (const slot of this.slots) {
      slot.gain.gain.cancelScheduledValues(now);
      slot.gain.gain.setValueAtTime(slot.gain.gain.value, now);
      slot.gain.gain.linearRampToValueAtTime(0, now + duration);
    }
    this.fadeTimer = setTimeout(() => {
      for (const slot of this.slots) slot.audio.pause();
    }, duration * 1000 + 30);
  }

  toggle() {
    this.muted = !this.muted;
    try { localStorage.setItem('cold-world-music-muted-v1', String(this.muted)); } catch {}
    if (this.muted) this.fadeOut();
    else { clearTimeout(this.fadeTimer); this.unlock(); this.nextAt = 0; }
    this.changed();
  }

  suspend() {
    this.suspended = true;
    this.fadeOut(0.15);
  }

  observe(state, camera, viewport, positions, types, now = performance.now()) {
    this.score = visibleThreat(state, camera, viewport, positions, types);
    const target = threatLevel(this.score);
    if (target !== this.pendingTier) { this.pendingTier = target; this.pendingSince = now; }
    const priority = { calm: 0, medium: 1, high: 2 };
    if (target !== this.tier && now - this.pendingSince >= (priority[target] > priority[this.tier] ? 2000 : 6000)) {
      this.tier = target;
      this.changed();
    }
    if (!this.active || !this.available || this.muted || this.suspended || document.hidden || state.paused || this.context?.state !== 'running' || this.switching || now < (this.nextAt || 0)) return;
    const day = state.environment.hour >= 6 && state.environment.hour < 18;
    if (this.current?.track.tier === this.tier && this.current.track[day ? 'day' : 'night']) return;
    const candidates = this.tracks.filter(track => track.tier === this.tier && track[day ? 'day' : 'night'] && this.urls.has(track.id) && track.id !== this.current?.track.id);
    if (!candidates.length) {
      if (this.current && (!this.current.track[day ? 'day' : 'night'] || this.current.track.tier !== this.tier)) this.fadeOut(2.5);
      return;
    }
    this.transition(candidates[this.cursor++ % candidates.length]);
  }

  transition(track) {
    const previous = this.current;
    const next = this.slots.find(slot => slot !== previous);
    if (!next) return;
    this.switching = true;
    clearTimeout(this.fadeTimer);
    next.audio.pause();
    next.audio.src = this.urls.get(track.id);
    next.audio.currentTime = 0;
    next.track = track;
    const now = this.context.currentTime;
    next.gain.gain.cancelScheduledValues(now);
    next.gain.gain.setValueAtTime(0, now);
    next.audio.play().then(() => {
      if (!this.active || this.muted || this.suspended || document.hidden) { next.audio.pause(); this.switching = false; return; }
      const began = this.context.currentTime;
      next.gain.gain.linearRampToValueAtTime(1, began + 2.5);
      if (previous) {
        previous.gain.gain.cancelScheduledValues(began);
        previous.gain.gain.setValueAtTime(previous.gain.gain.value, began);
        previous.gain.gain.linearRampToValueAtTime(0, began + 2.5);
      }
      this.current = next;
      this.changed();
      this.fadeTimer = setTimeout(() => {
        previous?.audio.pause();
        this.switching = false;
      }, 2600);
    }).catch(() => { this.switching = false; this.nextAt = performance.now() + 3000; });
  }
}
