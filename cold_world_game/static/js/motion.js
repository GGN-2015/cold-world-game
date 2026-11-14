class ProjectileMotion {
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
    for (const entity of state.projectiles || []) {
      if (entity.kind && entity.kind !== 'bullet' && entity.kind !== 'durian_peel') continue;
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
      track.hostile = Boolean(entity.hostile);
      track.kind = entity.kind;
      track.renderVelocity = entity.downed ? { x: 0, y: 0 } : velocity;
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

const clamp = (value, lower, upper) => Math.max(lower, Math.min(upper, value));

export class SnapshotMotion {
  constructor(collision = null, movement = {}) {
    this.collision = collision;
    this.speeds = { player_speed: 4, monster_speed: 1.2, fast_monster_speed: 4.8, frozen_speed_scale: 0.5, ...movement };
    this.projectiles = new ProjectileMotion(collision);
    this.reset();
  }

  reset() {
    this.tracks = new Map();
    this.projectiles.reset();
    this.time = null;
    this.latest = null;
    this.arrival = null;
    this.paused = false;
    this.offsets = [];
    this.jitter = [];
    this.delay = 0.12;
  }

  pointAt(track, time) {
    const frames = track.frames;
    const first = frames[0];
    if (time <= first.time || track.downed) return { x: first.x, y: first.y };
    for (let index = 1; index < frames.length; index++) {
      const next = frames[index];
      if (next.time < time) continue;
      const previous = frames[index - 1];
      const fraction = clamp((time - previous.time) / (next.time - previous.time), 0, 1);
      return { x: previous.x + (next.x - previous.x) * fraction, y: previous.y + (next.y - previous.y) * fraction };
    }
    const last = frames.at(-1);
    const previous = frames.at(-2);
    const interval = previous ? last.time - previous.time : 0;
    const velocityX = interval > 0 ? (last.x - previous.x) / interval : last.velocity_x;
    const velocityY = interval > 0 ? (last.y - previous.y) / interval : last.velocity_y;
    const fraction = Math.min(1, track.speed / (Math.hypot(velocityX, velocityY) || 1));
    const age = time - last.time;
    const extension = Math.min(age, 0.3) + (age > 0.3 ? 0.12 * (1 - Math.exp(-(age - 0.3) / 0.12)) : 0);
    return { x: last.x + velocityX * extension * fraction, y: last.y + velocityY * extension * fraction };
  }

  observe(state, now = performance.now() / 1000) {
    if (globalThis.document?.hidden) { this.reset(); return true; }
    if (this.latest != null && state.elapsed < this.latest && !state.paused) return false;
    const reset = this.latest == null || now - this.arrival > 1 || state.elapsed - this.latest > 1 || Boolean(state.paused) !== this.paused || state.elapsed < this.latest;
    if (reset) this.reset();
    if (this.time == null) this.time = state.elapsed - (state.paused ? 0 : this.delay);
    if (this.latest != null && state.elapsed > this.latest) {
      this.jitter.push(Math.max(0, now - this.arrival - (state.elapsed - this.latest)));
      if (this.jitter.length > 40) this.jitter.shift();
      const ordered = [...this.jitter].sort((first, second) => first - second);
      const desired = clamp(0.12 + ordered[Math.floor((ordered.length - 1) * 0.95)], 0.12, 0.28);
      this.delay += (desired - this.delay) * (desired > this.delay ? 0.25 : 0.03);
    }
    this.offsets.push(now - state.elapsed);
    if (this.offsets.length > 64) this.offsets.shift();
    const active = new Set();
    for (const entity of [...state.players, ...state.monsters]) {
      active.add(entity.id);
      let track = this.tracks.get(entity.id);
      const frame = { time: state.elapsed, x: entity.x, y: entity.y, velocity_x: entity.velocity_x ?? 0, velocity_y: entity.velocity_y ?? 0 };
      const immobilized = Boolean(entity.downed || entity.sleeping || entity.rising != null);
      const legacyJump = track && entity.teleport_epoch == null && entity.big == null && Math.hypot(entity.x - track.frames.at(-1).x, entity.y - track.frames.at(-1).y) > 5;
      if (!track || state.paused || entity.sleeping || entity.rising != null || immobilized !== track.downed || (entity.teleport_epoch ?? 0) !== track.teleportEpoch || legacyJump) {
        track = { x: entity.x, y: entity.y, frames: [frame], downed: immobilized, teleportEpoch: entity.teleport_epoch ?? 0, correction: { x: 0, y: 0 }, renderVelocity: { x: 0, y: 0 } };
        this.tracks.set(entity.id, track);
      } else {
        const previous = this.pointAt(track, this.time);
        if (track.frames.at(-1).time === frame.time) track.frames[track.frames.length - 1] = frame;
        else track.frames.push(frame);
        while (track.frames.length > 32) track.frames.shift();
        const next = this.pointAt(track, this.time);
        track.correction.x += previous.x - next.x;
        track.correction.y += previous.y - next.y;
      }
      track.baseSpeed = entity.move_speed ?? (entity.fast ? this.speeds.fast_monster_speed : entity.big != null ? this.speeds.monster_speed : this.speeds.player_speed);
      track.isPlayer = entity.big == null;
      track.frozenUntil = entity.frozen_until ?? 0;
      track.speed = track.baseSpeed * (state.elapsed < track.frozenUntil ? this.speeds.frozen_speed_scale : 1);
    }
    for (const identifier of this.tracks.keys()) if (!active.has(identifier)) this.tracks.delete(identifier);
    this.projectiles.observe(state, now);
    this.latest = state.elapsed;
    this.arrival = now;
    this.paused = Boolean(state.paused);
    return reset;
  }

  advance(seconds, now = performance.now() / 1000) {
    this.projectiles.advance(seconds, now);
    if (this.time == null || this.paused) return;
    const delta = clamp(seconds, 0, 0.1);
    if (!delta) return;
    const target = now - Math.min(...this.offsets) - this.delay;
    const error = target - (this.time + delta);
    this.time += delta * (Math.abs(error) < 0.015 ? 1 : clamp(1 + error * 0.8, 0.9, 1.05));
    const decay = Math.exp(-delta / 0.09);
    for (const track of this.tracks.values()) {
      if (track.downed) continue;
      if (now - this.arrival >= 0.5) { track.renderVelocity = { x: 0, y: 0 }; continue; }
      track.speed = track.baseSpeed * (this.time < track.frozenUntil ? this.speeds.frozen_speed_scale : 1);
      const desired = this.pointAt(track, this.time);
      track.correction.x *= decay;
      track.correction.y *= decay;
      const correctionX = desired.x + track.correction.x - track.x;
      const correctionY = desired.y + track.correction.y - track.y;
      const correctionSpeed = track.isPlayer && track.speed > this.speeds.player_speed ? track.speed + this.speeds.player_speed * 0.5 : track.speed * 2.5;
      const fraction = Math.min(1, correctionSpeed * delta / (Math.hypot(correctionX, correctionY) || 1));
      const horizontal = correctionX * fraction;
      const vertical = correctionY * fraction;
      const point = this.collision ? this.collision.move(track, horizontal, vertical) : { x: track.x + horizontal, y: track.y + vertical };
      track.renderVelocity = { x: (point.x - track.x) / delta, y: (point.y - track.y) / delta };
      track.x = point.x;
      track.y = point.y;
      while (track.frames.length > 3 && track.frames[1].time < this.time - 0.2) track.frames.shift();
    }
  }

  sample(entity) {
    if (entity.remaining != null) return this.projectiles.sample(entity);
    const track = this.tracks.get(entity.id);
    return track ? { x: track.x, y: track.y, velocity_x: track.renderVelocity.x, velocity_y: track.renderVelocity.y } : { x: entity.x, y: entity.y };
  }
}
