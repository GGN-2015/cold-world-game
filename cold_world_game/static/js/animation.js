function movementDirection(horizontal, vertical, previous) {
  const horizontalDirection = horizontal < 0 ? 'left' : 'right';
  const verticalDirection = vertical < 0 ? 'up' : 'down';
  const difference = Math.abs(Math.abs(horizontal) - Math.abs(vertical));
  if (difference <= Math.max(Math.abs(horizontal), Math.abs(vertical)) * 0.2 && [horizontalDirection, verticalDirection].includes(previous)) return previous;
  return Math.abs(horizontal) > Math.abs(vertical) ? horizontalDirection : verticalDirection;
}

export class ActorAnimator {
  constructor(definitions = {}) {
    this.definitions = definitions;
    this.reset();
  }

  reset() {
    this.actors = new Map();
    this.elapsed = null;
    this.age = 0;
  }

  observe(state) {
    const timeStep = this.elapsed == null ? 0 : state.elapsed - this.elapsed;
    this.elapsed = state.elapsed;
    this.age = 0;
    const active = new Set();
    for (const entity of [...state.players, ...state.monsters]) {
      active.add(entity.id);
      const motion = this.actors.get(entity.id) || { x: entity.x, y: entity.y, direction: 'down', travel: 0, moving: false };
      const horizontal = entity.x - motion.x;
      const vertical = entity.y - motion.y;
      const displacement = Math.hypot(horizontal, vertical);
      const hasVelocity = Number.isFinite(entity.velocity_x) && Number.isFinite(entity.velocity_y);
      const directionX = hasVelocity ? entity.velocity_x : horizontal;
      const directionY = hasVelocity ? entity.velocity_y : vertical;
      motion.moving = timeStep > 0 && !state.paused && !entity.downed && displacement > 0.00001 && displacement <= 5 && Math.hypot(directionX, directionY) > 0.00001;
      if (motion.moving) motion.direction = movementDirection(directionX, directionY, motion.direction);
      else motion.travel = 0;
      motion.x = entity.x;
      motion.y = entity.y;
      this.actors.set(entity.id, motion);
    }
    for (const identifier of this.actors.keys()) if (!active.has(identifier)) this.actors.delete(identifier);
  }

  advance(seconds) {
    this.age += seconds;
  }

  frame(kind, entity, displacement = 0, pose = {}) {
    const definition = this.definitions[kind];
    if (!definition) return null;
    const motion = this.actors.get(entity.id);
    const walking = motion?.moving && this.age <= 0.3 && !entity.downed && !pose.reacting;
    if (motion) motion.travel = walking ? (motion.travel + displacement) % definition.stride : 0;
    const column = walking ? definition.walk_frames[Math.floor(motion.travel / definition.stride * definition.walk_frames.length)] : definition.idle_frame;
    const row = Math.max(0, definition.directions.indexOf(pose.direction || motion?.direction || 'down'));
    return { asset: definition.asset, x: column * definition.frame_width, y: row * definition.frame_height, width: definition.frame_width, height: definition.frame_height };
  }
}
