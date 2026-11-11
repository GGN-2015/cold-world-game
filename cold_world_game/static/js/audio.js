const clips = ['handgun', 'shotgun', 'rifle', 'eat', 'place', 'hurt', 'chop', 'break', 'hit', 'axe', 'monster_attack', 'monster_death'];

export class GameAudio extends EventTarget {
  constructor() {
    super();
    this.context = null;
    this.master = null;
    this.buffers = new Map();
    this.sources = new Set();
    this.sequence = 0;
    this.suppressedUntil = 0;
    this.muted = false;
    this.available = Boolean(window.AudioContext || window.webkitAudioContext);
    try { this.muted = localStorage.getItem('cold-world-muted-v1') === 'true'; } catch {}
    this.rawBuffers = this.available ? this.load().catch(() => {
      this.available = false;
      this.dispatchEvent(new Event('change'));
      return [];
    }) : Promise.resolve([]);
  }

  async load() {
    return Promise.all(clips.map(async (name) => {
      const response = await fetch(`/static/audio/${name}.wav`);
      if (!response.ok) throw new Error(`Sound unavailable: ${name}`);
      return [name, await response.arrayBuffer()];
    }));
  }

  async unlock() {
    if (this.muted || !this.available || document.hidden) return;
    try {
      if (!this.context) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        this.context = new AudioContext();
        this.master = this.context.createGain();
        this.master.gain.value = 0.45;
        this.master.connect(this.context.destination);
      }
      if (this.context.state === 'suspended') await this.context.resume();
      if (!this.decoding) {
        this.decoding = this.rawBuffers.then((entries) => Promise.all(entries.map(async ([name, data]) => {
          this.buffers.set(name, await this.context.decodeAudioData(data));
        })));
      }
      await this.decoding;
    } catch {
      this.stopAll();
    }
  }

  toggleMute() {
    this.muted = !this.muted;
    try { localStorage.setItem('cold-world-muted-v1', String(this.muted)); } catch {}
    if (this.master) this.master.gain.value = this.muted ? 0 : 0.45;
    if (this.muted) this.stopAll();
    else this.unlock();
    this.dispatchEvent(new Event('change'));
  }

  reset(sequence = 0) {
    this.sequence = sequence;
    this.stopAll();
  }

  stopAll() {
    for (const source of this.sources) {
      try { source.stop(); } catch {}
    }
    this.sources.clear();
  }

  suspendPlayback() {
    this.suppressedUntil = Infinity;
    this.stopAll();
  }

  resumePlayback() {
    this.suppressedUntil = performance.now() + 200;
  }

  consume(state) {
    const previous = this.sequence;
    this.sequence = state.event_sequence ?? previous;
    if (this.muted || document.hidden || !document.hasFocus() || performance.now() < this.suppressedUntil) return;
    for (const event of state.events || []) {
      if (event.id <= previous || state.elapsed - event.time > 0.6) continue;
      const separation = Math.hypot(event.x - state.you.x, event.y - state.you.y);
      if (separation >= 18) continue;
      const clip = event.type === 'shot' ? (clips.includes(event.kind) ? event.kind : 'handgun') : event.type === 'melee' ? (event.kind === 'axe' ? 'axe' : 'monster_attack') : event.type === 'death' ? 'monster_death' : event.type === 'heal' ? 'eat' : event.type;
      this.play(clip, (1 - separation / 18) ** 2, event.kind === 'monster_big' || (event.type === 'shot' && event.kind === 'monster') ? 0.72 : 1);
    }
  }

  play(name, volume, rate = 1) {
    const buffer = this.buffers.get(name);
    if (this.muted || !buffer || this.context?.state !== 'running') return;
    if (this.sources.size >= 24) {
      const oldest = this.sources.values().next().value;
      oldest.stop();
      this.sources.delete(oldest);
    }
    const source = this.context.createBufferSource();
    const gain = this.context.createGain();
    source.buffer = buffer;
    source.playbackRate.value = rate;
    gain.gain.value = Math.max(0, Math.min(1, volume));
    source.connect(gain);
    gain.connect(this.master);
    this.sources.add(source);
    source.onended = () => {
      this.sources.delete(source);
      source.disconnect();
      gain.disconnect();
    };
    source.start();
  }
}
