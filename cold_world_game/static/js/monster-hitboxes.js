export function monsterSprite(entity, elapsed) {
  const kind = entity.big ? 'big' : entity.fast ? 'fast' : entity.species || 'small';
  if ((entity.big || entity.fast) && entity.sleeping) return `monster_${kind}_sleep`;
  if (entity.big && entity.rising != null) return 'monster_big_rise';
  return `monster_${kind}${elapsed < (entity.frozen_until ?? 0) ? '_frozen' : ''}`;
}

export class MonsterHitboxes {
  constructor(definition = {}) {
    this.profiles = definition.profiles || {};
    this.size = definition.size || 32;
    this.bulletRadius = definition.bullet_radius ?? 0.1;
  }

  profile(entity, elapsed) {
    return this.profiles[monsterSprite(entity, elapsed)];
  }

  contains(entity, point, elapsed) {
    const profile = this.profile(entity, elapsed);
    if (!profile) return Math.hypot(point.x - entity.x, point.y - entity.y) < (entity.big ? 0.65 : 0.5);
    const horizontal = Math.floor(((point.x - entity.x) / profile.width + 0.5) * this.size);
    const vertical = Math.floor(((point.y - entity.y + profile.offset) / profile.height + 0.5) * this.size);
    return horizontal >= 0 && horizontal < this.size && vertical >= 0 && vertical < this.size && Boolean(profile.rows[vertical] & (1 << horizontal));
  }
}
