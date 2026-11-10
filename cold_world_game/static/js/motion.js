export class SnapshotMotion {
  constructor(collision = null) {
    this.collision = collision;
    this.reset();
  }

  reset() {
    this.tracks = new Map();
    this.time = null;
    this.latest = null;
    this.arrival = null;
    this.paused = false;
    this.offsets = [];
  }

  observe(state, now = performance.now() / 1000) {
    if (globalThis.document?.hidden) { this.reset(); return true; }
    if (this.latest != null && state.elapsed < this.latest && !state.paused) return false;
    const reset = this.latest == null || now - this.arrival > 1 || state.elapsed - this.latest > 1;
    if (reset) this.reset();
    if (this.time == null) this.time = state.elapsed;
    this.offsets.push(now - state.elapsed);
    if (this.offsets.length > 64) this.offsets.shift();
    const age = state.paused ? 0 : Math.max(0, Math.min(0.3, now - Math.min(...this.offsets) - state.elapsed));
    const active = new Set();
    for (const entity of [...state.players, ...state.monsters, ...(state.projectiles || [])]) {
      active.add(entity.id);
      let track = this.tracks.get(entity.id);
      const interval = state.elapsed - (track?.serverTime ?? state.elapsed);
      const velocity = { x: entity.velocity_x ?? (interval > 0 ? (entity.x - track.serverX) / interval : 0), y: entity.velocity_y ?? (interval > 0 ? (entity.y - track.serverY) / interval : 0) };
      const speed = Math.hypot(velocity.x, velocity.y);
      const projection = entity.downed ? 0 : Math.min(age, entity.remaining == null || speed === 0 ? age : entity.remaining / speed);
      const projected = this.collision
        ? entity.remaining == null ? this.collision.move(entity, velocity.x * projection, velocity.y * projection) : this.collision.trace(entity, velocity.x * projection, velocity.y * projection)
        : { x: entity.x + velocity.x * projection, y: entity.y + velocity.y * projection };
      if (!track || state.paused || entity.downed !== track.downed || Math.hypot(entity.x - track.x, entity.y - track.y) > 5) {
        track = { ...projected, correction: { x: 0, y: 0 } };
        if (!reset && !this.tracks.has(entity.id) && entity.remaining != null && Number.isFinite(entity.origin_x) && Number.isFinite(entity.origin_y) && entity.spawned_at != null && state.elapsed - entity.spawned_at >= 0 && state.elapsed - entity.spawned_at <= 0.5) {
          track.x = entity.origin_x;
          track.y = entity.origin_y;
          track.correction = { x: projected.x - track.x, y: projected.y - track.y };
          track.debut = true;
        }
        this.tracks.set(entity.id, track);
      } else {
        track.correction = { x: projected.x - track.x, y: projected.y - track.y };
      }
      track.velocity = velocity;
      track.renderVelocity = state.paused || entity.downed ? { x: 0, y: 0 } : velocity;
      track.serverX = entity.x;
      track.serverY = entity.y;
      track.serverTime = state.elapsed;
      track.downed = entity.downed;
      track.remaining = entity.remaining == null ? null : projected.blocked ? 0 : Math.max(0, entity.remaining - speed * projection);
      track.arrival = now;
    }
    for (const identifier of this.tracks.keys()) if (!active.has(identifier)) this.tracks.delete(identifier);
    this.latest = state.elapsed;
    this.arrival = now;
    this.paused = Boolean(state.paused);
    return reset;
  }

  advance(seconds, now = performance.now() / 1000) {
    if (this.time == null || this.paused) return;
    const delta = Math.max(0, Math.min(seconds, 0.1));
    this.time += delta;
    for (const track of this.tracks.values()) {
      if (track.downed) continue;
      if (track.debut) { track.debut = false; continue; }
      const age = now - track.arrival;
      const freshness = Math.max(0, Math.min(1, (0.5 - age) / 0.2));
      track.renderVelocity = { x: track.velocity.x * freshness, y: track.velocity.y * freshness };
      const correction = (1 - Math.exp(-delta / 0.16)) * freshness;
      let horizontal = track.velocity.x * delta * freshness;
      let vertical = track.velocity.y * delta * freshness;
      if (track.remaining != null) {
        const travel = Math.hypot(horizontal, vertical);
        const fraction = travel > 0 ? Math.min(1, track.remaining / travel) : 0;
        horizontal *= fraction;
        vertical *= fraction;
        track.remaining = Math.max(0, track.remaining - travel * fraction);
      }
      horizontal += track.correction.x * correction;
      vertical += track.correction.y * correction;
      const point = this.collision
        ? track.remaining == null ? this.collision.move(track, horizontal, vertical) : this.collision.trace(track, horizontal, vertical)
        : { x: track.x + horizontal, y: track.y + vertical };
      if (point.blocked) track.remaining = 0;
      track.x = point.x;
      track.y = point.y;
      track.correction.x *= 1 - correction;
      track.correction.y *= 1 - correction;
    }
  }

  sample(entity) {
    const track = this.tracks.get(entity.id);
    return track ? { x: track.x, y: track.y, velocity_x: track.renderVelocity.x, velocity_y: track.renderVelocity.y } : { x: entity.x, y: entity.y };
  }
}
