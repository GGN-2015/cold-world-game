const solid = new Set(['tree', 'wall', 'fence', 'chest', 'campfire', 'vending_machine', 'match_machine']);
const allowsPlayerOverlap = (monster, playerId) => playerId != null && !monster.big && monster.overlap_player === playerId;

export class CollisionMap {
  constructor({ radius = 0.35, chunk_size = 15 } = {}) {
    this.radius = radius;
    this.chunkSize = chunk_size;
    this.tiles = new Set();
    this.bulletTiles = new Set();
    this.chunks = new Set();
  }

  update(state) {
    this.tiles = new Set(state.structures.filter((entity) => solid.has(entity.kind)).map((entity) => `${entity.x},${entity.y}`));
    this.bulletTiles = new Set(state.structures.filter((entity) => ['tree', 'chest', 'vending_machine', 'match_machine'].includes(entity.kind)).map((entity) => `${entity.x},${entity.y}`));
    this.chunks = new Set(state.chunks.map(([horizontal, vertical]) => `${horizontal},${vertical}`));
  }

  canStand(horizontal, vertical, bodies = []) {
    const radius = this.radius;
    for (const cornerX of [horizontal - radius, horizontal + radius]) {
      for (const cornerY of [vertical - radius, vertical + radius]) {
        if (!this.chunks.has(`${Math.floor((cornerX + this.chunkSize / 2) / this.chunkSize)},${Math.floor((cornerY + this.chunkSize / 2) / this.chunkSize)}`)) return false;
      }
    }
    for (let tileX = Math.floor(horizontal - radius); tileX <= Math.floor(horizontal + radius + 1); tileX++) {
      for (let tileY = Math.floor(vertical - radius); tileY <= Math.floor(vertical + radius + 1); tileY++) {
        if (!this.tiles.has(`${tileX},${tileY}`)) continue;
        const deltaX = Math.max(Math.abs(horizontal - tileX) - 0.5, 0);
        const deltaY = Math.max(Math.abs(vertical - tileY) - 0.5, 0);
        if (deltaX * deltaX + deltaY * deltaY < radius * radius - 1e-10) return false;
      }
    }
    return !bodies.some((body) => Math.hypot(horizontal - body.x, vertical - body.y) < radius * 2 - 1e-9);
  }

  move(point, horizontal, vertical, bodies = []) {
    const steps = Math.max(1, Math.ceil(Math.hypot(horizontal, vertical) / 0.15));
    const stepX = horizontal / steps, stepY = vertical / steps;
    const result = { x: point.x, y: point.y };
    for (let index = 0; index < steps; index++) {
      if (this.canStand(result.x + stepX, result.y + stepY, bodies)) {
        result.x += stepX;
        result.y += stepY;
      } else {
        if (stepX && this.canStand(result.x + stepX, result.y, bodies)) result.x += stepX;
        if (stepY && this.canStand(result.x, result.y + stepY, bodies)) result.y += stepY;
      }
    }
    return result;
  }

  trace(point, horizontal, vertical) {
    let fraction = 1;
    for (let tileX = Math.floor(Math.min(point.x, point.x + horizontal)) - 1; tileX <= Math.ceil(Math.max(point.x, point.x + horizontal)); tileX++) {
      for (let tileY = Math.floor(Math.min(point.y, point.y + vertical)) - 1; tileY <= Math.ceil(Math.max(point.y, point.y + vertical)); tileY++) {
        if (!this.bulletTiles.has(`${tileX},${tileY}`)) continue;
        let lower = 0, upper = fraction;
        for (const [start, delta, center] of [[point.x, horizontal, tileX], [point.y, vertical, tileY]]) {
          if (Math.abs(delta) < 1e-12) {
            if (Math.abs(start - center) > 0.5) { lower = 1; upper = 0; break; }
          } else {
            const near = (center - 0.5 - start) / delta;
            const far = (center + 0.5 - start) / delta;
            lower = Math.max(lower, Math.min(near, far));
            upper = Math.min(upper, Math.max(near, far));
          }
        }
        if (lower <= upper) fraction = Math.min(fraction, Math.max(0, lower - 1e-6));
      }
    }
    return { x: point.x + horizontal * fraction, y: point.y + vertical * fraction, blocked: fraction < 1 };
  }
}

export class ClientMovement {
  constructor(collision, speed = 4) {
    this.collision = collision;
    this.speed = speed;
    this.reset();
  }

  reset() {
    this.state = null;
    this.position = null;
    this.offset = { x: 0, y: 0 };
    this.velocity = { x: 0, y: 0 };
    this.input = { x: 0, y: 0 };
    this.ghosts = new Set();
    this.epoch = null;
    this.teleportEpoch = null;
    this.enabled = false;
    this.active = false;
    this.stale = false;
    this.arrival = 0;
  }

  observe(state, now = performance.now() / 1000) {
    const previous = this.state;
    const epoch = state.movement?.epoch ?? 0;
    const teleportEpoch = state.movement?.teleport_epoch ?? 0;
    const enabled = state.movement?.mode === 'client';
    const reset = !previous || !this.position || enabled !== this.enabled || this.stale || state.paused || teleportEpoch !== this.teleportEpoch;
    if (reset || epoch !== this.epoch) {
      const prior = this.sample();
      this.position = { x: state.you.x, y: state.you.y };
      this.offset = !reset && prior && Math.hypot(prior.x - state.you.x, prior.y - state.you.y) <= 2
        ? { x: prior.x - state.you.x, y: prior.y - state.you.y } : { x: 0, y: 0 };
      this.velocity = { x: 0, y: 0 };
    }
    this.enabled = enabled;
    this.epoch = epoch;
    this.teleportEpoch = teleportEpoch;
    this.arrival = now;
    this.stale = false;
    this.state = state;
    for (const monster of state.monsters) {
      if ((!previous || previous.you.downed || state.you.downed || allowsPlayerOverlap(monster, state.you.id)) && Math.hypot(monster.x - this.position.x, monster.y - this.position.y) < this.collision.radius * 2) this.ghosts.add(monster.id);
    }
    const monsters = new Set(state.monsters.map((monster) => monster.id));
    for (const identifier of this.ghosts) if (!monsters.has(identifier)) this.ghosts.delete(identifier);
    if (enabled && !this.collision.canStand(this.position.x, this.position.y)) {
      const candidates = [{ x: state.you.x, y: state.you.y }];
      for (let horizontal = -3; horizontal <= 3; horizontal++) {
        for (let vertical = -3; vertical <= 3; vertical++) candidates.push({ x: Math.floor(this.position.x + 0.5) + horizontal, y: Math.floor(this.position.y + 0.5) + vertical });
      }
      const destination = candidates.filter((point) => this.collision.canStand(point.x, point.y)).sort((first, second) => Math.hypot(first.x - this.position.x, first.y - this.position.y) - Math.hypot(second.x - this.position.x, second.y - this.position.y))[0];
      if (destination) { this.position = destination; this.offset = { x: 0, y: 0 }; }
    }
  }

  setInput(horizontal, vertical) {
    const magnitude = Math.max(1, Math.hypot(horizontal, vertical));
    this.input = { x: horizontal / magnitude, y: vertical / magnitude };
    if (!horizontal && !vertical) this.velocity = { x: 0, y: 0 };
  }

  advance(seconds, monsters = [], now = performance.now() / 1000) {
    if (!this.position || !this.enabled) return;
    const delta = Math.max(0, Math.min(seconds, 0.1));
    this.stale = now - this.arrival > 1;
    const you = this.state.you;
    const previous = this.position;
    const colliders = monsters.filter((monster) => {
      if (this.ghosts.has(monster.id) && Math.hypot(monster.x - previous.x, monster.y - previous.y) >= this.collision.radius * 2) this.ghosts.delete(monster.id);
      return !this.ghosts.has(monster.id) && !allowsPlayerOverlap(monster, you.id);
    });
    if (this.active && !this.stale && !this.state.paused && !you.downed) {
      const speed = this.speed * (you.temperature < 18 ? 0.5 : 1) * (you.hunger <= 0 ? 0.5 : 1);
      this.position = this.collision.move(previous, this.input.x * speed * delta, this.input.y * speed * delta, colliders);
    }
    this.velocity = delta > 0 ? { x: (this.position.x - previous.x) / delta, y: (this.position.y - previous.y) / delta } : { x: 0, y: 0 };
    const decay = Math.exp(-delta / 0.08);
    this.offset.x *= decay;
    this.offset.y *= decay;
  }

  sample() {
    return this.position ? { x: this.position.x + this.offset.x, y: this.position.y + this.offset.y } : null;
  }

  report() {
    if (!this.enabled || !this.position || this.stale) return {};
    return { position: [this.position.x, this.position.y], velocity: [this.velocity.x, this.velocity.y], movement_epoch: this.epoch };
  }
}
