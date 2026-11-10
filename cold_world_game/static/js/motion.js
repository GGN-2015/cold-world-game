export class SnapshotMotion {
  constructor() { this.reset(); }

  reset() {
    this.frames = [];
    this.discontinuities = new Map();
    this.time = null;
    this.paused = false;
    this.delay = 0.12;
    this.from = null;
    this.to = null;
  }

  observe(state, now = performance.now() / 1000) {
    if (globalThis.document?.hidden) { this.reset(); return true; }
    const previous = this.frames.at(-1);
    if (previous && state.elapsed < previous.time && !state.paused) return false;
    const reset = !previous || state.paused || state.elapsed - previous.time > 0.5 || now - previous.arrival > 0.75;
    if (reset) this.reset();
    const entities = new Map([...state.players, ...state.monsters, ...(state.projectiles || [])].map((entity) => [entity.id, entity]));
    const frame = { time: state.elapsed, arrival: now, offset: now - state.elapsed, entities };
    for (const [identifier, entity] of entities) {
      const prior = previous?.entities.get(identifier);
      if (!prior || entity.downed !== prior.downed || Math.hypot(entity.x - prior.x, entity.y - prior.y) > Math.max(5, Math.hypot(entity.velocity_x || 0, entity.velocity_y || 0) * (state.elapsed - (previous?.time || 0)) * 1.25)) this.discontinuities.set(identifier, frame.time);
    }
    for (const identifier of this.discontinuities.keys()) if (!entities.has(identifier)) this.discontinuities.delete(identifier);
    if (this.frames.at(-1)?.time === frame.time) this.frames[this.frames.length - 1] = frame;
    else this.frames.push(frame);
    if (this.frames.length > 32) this.frames.splice(0, this.frames.length - 32);
    const offsets = this.frames.slice(-24).map((entry) => entry.offset);
    this.delay = Math.min(0.32, 0.12 + Math.max(...offsets) - Math.min(...offsets));
    if (this.time == null) this.time = frame.time;
    this.paused = Boolean(state.paused);
    return reset;
  }

  advance(seconds, now = performance.now() / 1000) {
    if (!this.frames.length) return;
    const latest = this.frames.at(-1);
    const offset = Math.min(...this.frames.slice(-24).map((frame) => frame.offset));
    const desired = now - offset - this.delay;
    const rate = Math.max(0.85, Math.min(1.15, 1 + (desired - this.time) * 1.5));
    this.time = this.paused ? latest.time : Math.min(latest.time, this.time + Math.max(0, seconds) * rate);
    this.from = this.frames[0];
    this.to = latest;
    for (const frame of this.frames) {
      if (frame.time <= this.time) this.from = frame;
      else { this.to = frame; break; }
    }
  }

  sample(entity) {
    if (!this.from || !this.to || this.paused || entity.downed || this.from.time < (this.discontinuities.get(entity.id) ?? -Infinity)) return { x: entity.x, y: entity.y };
    const first = this.from.entities.get(entity.id);
    const second = this.to.entities.get(entity.id);
    if (!first || !second) return { x: entity.x, y: entity.y };
    const interval = this.to.time - this.from.time;
    const fraction = interval > 0 ? Math.max(0, Math.min(1, (this.time - this.from.time) / interval)) : 0;
    return { x: first.x + (second.x - first.x) * fraction, y: first.y + (second.y - first.y) * fraction };
  }
}
