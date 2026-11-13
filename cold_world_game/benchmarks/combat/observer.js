async () => {
  const [{ WorldRenderer }, { GameConnection }, { StateSync }, { LocalCombat }, { CombatEffects }] = await Promise.all([
    import('/static/js/renderer.js'), import('/static/js/network.js'), import('/static/js/sync.js'),
    import('/static/js/combat.js'), import('/static/js/effects.js'),
  ]);
  class Samples {
    constructor() { this.count = 0; this.total = 0; this.min = Infinity; this.max = -Infinity; this.buckets = new Map(); }
    add(value) {
      if (!Number.isFinite(value)) return;
      const bucket = Math.ceil(value * 10);
      this.buckets.set(bucket, (this.buckets.get(bucket) || 0) + 1);
      this.count++; this.total += value; this.min = Math.min(this.min, value); this.max = Math.max(this.max, value);
    }
    summary() {
      if (!this.count) return { count: 0, mean: null, min: null, max: null, p05: null, p50: null, p95: null, p99: null };
      const result = { count: this.count, mean: this.total / this.count, min: this.min, max: this.max };
      let cumulative = 0;
      for (const [bucket, count] of [...this.buckets].sort((first, second) => first[0] - second[0])) {
        cumulative += count;
        for (const [name, fraction] of [['p05', .05], ['p50', .5], ['p95', .95], ['p99', .99]]) {
          if (cumulative >= Math.ceil(this.count * fraction) && result[name] == null) result[name] = Math.min(this.max, bucket / 10);
        }
      }
      return result;
    }
  }
  const bench = window.combatBenchmark = {
    measuring: false, samples: new Map(), counters: {}, errors: [], jumps: [], bytes: 0,
    swings: new Map(), positions: new Map(), excluded: new Map(), events: 0,
    observe(name, value) { if (this.measuring) { if (!this.samples.has(name)) this.samples.set(name, new Samples()); this.samples.get(name).add(value); } },
    reset() { this.samples.clear(); this.counters = {}; this.bytes = 0; this.jumps = []; this.positions.clear(); this.excluded.clear(); this.swings.clear(); this.lastDraw = null; this.lastState = null; this.lastDensity = 0; },
    start() { this.reset(); this.measuring = true; },
    stop() { this.measuring = false; },
    report() {
      return { samples: Object.fromEntries([...this.samples].map(([name, values]) => [name, values.summary()])), counters: this.counters, bytes_received: this.bytes, fatal_errors: this.errors,
        jumps: this.jumps, connected: Boolean(this.connection?.ready), viewport: this.renderer ? { width: this.renderer.width, height: this.renderer.height, world_width: this.renderer.width / this.renderer.scale, world_height: this.renderer.height / this.renderer.scale, pixel_ratio: devicePixelRatio } : null };
    },
    info() {
      const renderer = this.renderer, state = renderer?.state;
      if (!state || !this.connection?.ready) return null;
      const origin = renderer.movement.enabled ? renderer.movement.position : state.you;
      const weapon = state.you.inventory[state.you.selected]?.kind;
      const laneClear = monster => {
        if (!['rifle', 'shotgun', 'handgun'].includes(weapon)) return true;
        const deltaX = monster.x - origin.x, deltaY = monster.y - origin.y, length = Math.hypot(deltaX, deltaY);
        if (length < .001) return false;
        const spread = weapon === 'shotgun' ? Math.sin(12 * Math.PI / 180) : 0;
        return !state.players.some(teammate => {
          if (teammate.id === state.you.id || teammate.downed) return false;
          const offsetX = teammate.x - origin.x, offsetY = teammate.y - origin.y;
          const along = (offsetX * deltaX + offsetY * deltaY) / length;
          return along > -.6 && along < 19 && Math.abs(offsetX * deltaY - offsetY * deltaX) / length < .6 + Math.max(0, along) * spread;
        });
      };
      const target = state.monsters.reduce((nearest, monster) => monster.hp <= 0 || monster.sleeping || monster.rising != null || !laneClear(monster) ? nearest : !nearest || Math.hypot(monster.x - origin.x, monster.y - origin.y) < Math.hypot(nearest.x - origin.x, nearest.y - origin.y) ? monster : nearest, null);
      const point = renderer.screenPoint(target?.x ?? origin.x + 2, target?.y ?? origin.y);
      const bounds = renderer.canvas.getBoundingClientRect();
      const center = identifier => { const box = document.getElementById(identifier).getBoundingClientRect(); return { x: box.x + box.width / 2, y: box.y + box.height / 2, radius: box.width * .34 }; };
      const own = state.players.find(player => player.id === state.you.id);
      const velocity = renderer.movement.enabled ? renderer.movement.velocity : { x: own?.velocity_x || 0, y: own?.velocity_y || 0 };
      return { x: origin.x, y: origin.y, has_target: Boolean(target), target_x: target?.x ?? origin.x + 2, target_y: target?.y ?? origin.y,
        velocity_x: velocity.x, velocity_y: velocity.y, move_speed: own?.move_speed ?? 4,
        screen_x: Math.max(bounds.left + 4, Math.min(bounds.right - 4, bounds.left + point.x)), screen_y: Math.max(bounds.top + 4, Math.min(bounds.bottom - 4, bounds.top + point.y)),
        weapon, touch_move: center('touch-move'), touch_aim: center('touch-aim'), touch_use: center('touch-use') };
    },
  };
  const open = GameConnection.prototype.open;
  GameConnection.prototype.open = function(...arguments_) {
    bench.connection = this;
    const result = open.apply(this, arguments_);
    this.socket.addEventListener('message', event => { if (bench.measuring) bench.bytes += typeof event.data === 'string' ? new TextEncoder().encode(event.data).length : event.data.byteLength; });
    this.socket.addEventListener('close', () => { if (bench.measuring) bench.errors.push('WebSocket closed during measurement'); });
    return result;
  };
  const command = GameConnection.prototype.command;
  GameConnection.prototype.command = function(type, payload) {
    const started = performance.now();
    return command.call(this, type, payload).then(result => {
      bench.observe('command_rtt_ms', performance.now() - started);
      if (type === 'ping') bench.observe('ping_rtt_ms', performance.now() - started);
      return result;
    }).catch(error => { if (bench.measuring) bench.counters[`error_${error.code || 'unknown'}`] = (bench.counters[`error_${error.code || 'unknown'}`] || 0) + 1; throw error; });
  };
  const apply = StateSync.prototype.apply;
  StateSync.prototype.apply = function(...arguments_) {
    const now = performance.now();
    if (bench.lastState != null) bench.observe('state_gap_ms', now - bench.lastState);
    bench.lastState = now;
    const result = apply.apply(this, arguments_);
    bench.observe('decode_apply_ms', performance.now() - now);
    return result;
  };
  const begin = LocalCombat.prototype.begin;
  LocalCombat.prototype.begin = function(...arguments_) {
    const started = performance.now(), identifier = begin.apply(this, arguments_);
    if (identifier && bench.measuring) bench.swings.set(identifier, started);
    return identifier;
  };
  const axe = CombatEffects.prototype.directionalAxe;
  CombatEffects.prototype.directionalAxe = function(renderer, effect, phase) {
    const result = axe.call(this, renderer, effect, phase), identifier = effect.event.attack_id;
    if (result && bench.swings.has(identifier)) { bench.observe('local_feedback_ms', performance.now() - bench.swings.get(identifier)); bench.swings.delete(identifier); }
    return result;
  };
  const smooth = WorldRenderer.prototype.smooth;
  WorldRenderer.prototype.smooth = function(entity) {
    const point = smooth.call(this, entity);
    if (bench.measuring && (entity.id.startsWith('bench-') || bench.positions.has(entity.id) || bench.positions.size < 48)) {
      const now = performance.now(), previous = bench.positions.get(entity.id);
      if (previous && now - previous.time < 250 && previous.epoch === entity.teleport_epoch && previous.downed === Boolean(entity.downed) && !entity.sleeping && !entity.rising && now > (bench.excluded.get(entity.id) || 0)) {
        const displacement = Math.hypot(point.x - previous.x, point.y - previous.y);
        const maximum = Math.max(entity.move_speed || 0, 4.8) * (now - previous.time) / 1000 + .35;
        if (displacement > maximum) { bench.counters.unexpected_jumps = (bench.counters.unexpected_jumps || 0) + 1; if (bench.jumps.length < 32) bench.jumps.push({ id: entity.id, displacement, frame_ms: now - previous.time, maximum }); }
      }
      bench.positions.set(entity.id, { x: point.x, y: point.y, time: now, epoch: entity.teleport_epoch, downed: Boolean(entity.downed) });
    }
    return point;
  };
  const draw = WorldRenderer.prototype.draw;
  WorldRenderer.prototype.draw = function(...arguments_) {
    bench.renderer = this;
    const now = performance.now();
    if (bench.measuring && this.state) {
      if (bench.lastDraw != null) bench.observe('frame_ms', now - bench.lastDraw);
      bench.lastDraw = now;
      for (const event of this.state.events) {
        if (event.id <= bench.events) continue;
        if (event.knockback?.some(value => Math.abs(value) > .001) || event.type.startsWith('teleport_')) bench.excluded.set(event.target || event.actor, now + 750);
        bench.events = Math.max(bench.events, event.id);
      }
    }
    const started = performance.now(), result = draw.apply(this, arguments_);
    bench.observe('draw_ms', performance.now() - started);
    if (bench.measuring && this.state && now - bench.lastDensity >= 250) {
      bench.lastDensity = now;
      const halfWidth = this.width / this.scale / 2, halfHeight = this.height / this.scale / 2;
      bench.observe('visible_monsters', this.state.monsters.filter(entity => !entity.sleeping && entity.rising == null && Math.abs(entity.x - this.camera.x) <= halfWidth && Math.abs(entity.y - this.camera.y) <= halfHeight).length);
      bench.observe('visible_players', this.state.players.filter(entity => Math.abs(entity.x - this.camera.x) <= halfWidth && Math.abs(entity.y - this.camera.y) <= halfHeight).length);
      bench.observe('socket_buffer_bytes', bench.connection?.socket?.bufferedAmount || 0);
      const active = new Set([...this.state.players, ...this.state.monsters].map(entity => entity.id));
      for (const identifier of bench.positions.keys()) if (!active.has(identifier)) bench.positions.delete(identifier);
      for (const [identifier, until] of bench.excluded) if (until < now) bench.excluded.delete(identifier);
      for (const [identifier, began] of bench.swings) if (now - began > 2000) bench.swings.delete(identifier);
    }
    return result;
  };
  if (PerformanceObserver.supportedEntryTypes.includes('longtask')) new PerformanceObserver(entries => {
    for (const entry of entries.getEntries()) bench.observe('long_task_ms', entry.duration);
  }).observe({ entryTypes: ['longtask'] });
  window.addEventListener('error', event => bench.errors.push(event.message));
  window.addEventListener('unhandledrejection', event => bench.errors.push(String(event.reason)));
}
