import { buildings, containers, distance, tileAt } from './catalog.js';
import { t } from './i18n.js';
import { ActorAnimator } from './animation.js';
import { isMobileDevice } from './mobile.js';
import { CombatEffects } from './effects.js';
import { SnapshotMotion } from './motion.js';
import { homingPosition } from './missiles.js';
import { ClientMovement, CollisionMap } from './movement.js';
import { MonsterHitboxes, monsterSprite } from './monster-hitboxes.js';

export async function loadAssets() {
  const response = await fetch('/static/assets/manifest.json');
  if (!response.ok) throw new Error('assets_unavailable');
  const manifest = await response.json();
  const images = new Map();
  await Promise.all(Object.entries(manifest.assets).map(async ([name, entry]) => {
    const image = new Image();
    image.src = `/static/assets/${entry.file}`;
    await image.decode();
    images.set(name, image);
  }));
  return { images, animations: manifest.animations || {}, effects: manifest.effects || {}, monsterHitboxes: manifest.monster_hitboxes || {} };
}

function demoWorld() {
  const structures = [];
  let identifier = 0;
  const add = (kind, horizontal, vertical, lit = false) => structures.push({ id: `demo${identifier++}`, kind, x: horizontal, y: vertical, lit });
  for (let horizontal = -5; horizontal <= 2; horizontal++) {
    for (let vertical = -4; vertical <= 2; vertical++) {
      if (horizontal === -5 || horizontal === 2 || vertical === -4 || vertical === 2) {
        if (!(vertical === 2 && horizontal === -1)) add('wall', horizontal, vertical);
      } else add('floor', horizontal, vertical);
    }
  }
  add('chest', -3, -2);
  add('campfire', 0, 0, true);
  for (let index = 0; index < 70; index++) {
    const horizontal = Math.sin(index * 193.7) * 23;
    const vertical = Math.cos(index * 81.3) * 14;
    if (horizontal > -7 && horizontal < 4 && vertical > -6 && vertical < 5) continue;
    add('tree', Math.round(horizontal), Math.round(vertical));
  }
  return {
    structures, players: [{ id: 'demo-traveler', x: -1, y: 0.8, temperature: 36, hunger: 10 }], monsters: [], ground: [], projectiles: [],
    environment: { hour: 18.5 }, chunks: [], you: { id: 'demo-traveler', x: -1, y: 1, inventory: [], selected: 0 },
  };
}

export class WorldRenderer {
  constructor(canvas, images, animations = {}, effects = {}, catalog = {}, viewport = null, monsterHitboxes = {}) {
    this.canvas = canvas;
    this.context = canvas.getContext('2d', { alpha: false });
    this.images = images;
    this.catalog = catalog;
    this.monsterHitboxes = new MonsterHitboxes(monsterHitboxes);
    this.fixedViewport = viewport;
    this.recordedFrames = false;
    this.animator = new ActorAnimator(animations);
    this.effects = new CombatEffects(effects);
    this.collision = new CollisionMap(catalog);
    this.movement = new ClientMovement(this.collision, catalog.movement?.player_speed ?? 4, catalog.equipped_items);
    this.motion = new SnapshotMotion(this.collision, catalog.movement);
    this.state = null;
    this.demo = demoWorld();
    this.camera = { x: -3, y: 1 };
    this.positions = new Map();
    this.pointer = { x: 0, y: 0, active: false };
    this.selected = 0;
    this.panelOpen = false;
    this.target = null;
    this.fps = 60;
    this.elapsed = 0;
    this.resize();
    new ResizeObserver(() => this.resize()).observe(canvas);
  }

  resize() {
    this.width = this.canvas.clientWidth || 1280;
    this.height = this.canvas.clientHeight || 720;
    const ratio = Math.min(devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(this.width * ratio);
    this.canvas.height = Math.round(this.height * ratio);
    this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.context.imageSmoothingEnabled = false;
    this.scale = this.fixedViewport ? this.width / this.fixedViewport[0] : isMobileDevice ? Math.max(this.width / 28, this.height / 24) : this.width / 32;
    this.pixelRatio = ratio;
    this.snow = null;
    this.projectileGlows = new Map();
    for (const color of ['#ff356d', '#63e7ff', '#ffad43', '#ff493d']) this.projectileGlow(color, 0.8, Math.max(5, this.scale * 0.16));
  }

  setState(state) {
    const first = !this.state;
    if (this.structureSource !== state.structures) {
      this.structureSource = state.structures;
      if (state.terrain_geometry != null && this.terrainGeometry === state.terrain_geometry) {
        const current = new Map(state.structures.map(entity => [entity.id, entity]));
        for (const entity of this.staticEntities) Object.assign(entity, current.get(entity.id));
      } else {
        this.floors = state.structures.filter((entity) => entity.kind === 'floor');
        this.staticEntities = state.structures.filter((entity) => entity.kind !== 'floor').map((entity) => ({ ...entity, category: 'structure' })).sort((first, second) => first.y - second.y);
      }
      this.terrainGeometry = state.terrain_geometry;
    }
    this.state = state;
    this.collision.update(state);
    this.movement.observe(state);
    if (first) {
      this.camera = { x: state.you.x, y: state.you.y };
      this.positions.clear();
      this.animator.reset();
      this.effects.reset(state.event_sequence || 0);
    }
    if (this.motion.observe(state)) {
      this.positions.clear();
      this.animator.reset();
    }
    this.effects.observe(state);
  }

  viewport() {
    return [this.width / this.scale, this.height / this.scale];
  }

  reset() {
    this.state = null;
    this.structureSource = null;
    this.floors = null;
    this.staticEntities = null;
    this.positions.clear();
    this.animator.reset();
    this.effects.reset();
    this.motion.reset();
    this.movement.reset();
    this.camera = { x: -3, y: 1 };
  }

  screenToWorld(clientX, clientY) {
    const bounds = this.canvas.getBoundingClientRect();
    return { x: (clientX - bounds.left - this.width / 2) / this.scale + this.camera.x, y: (clientY - bounds.top - this.height / 2) / this.scale + this.camera.y };
  }

  screenPoint(horizontal, vertical) {
    return { x: (horizontal - this.camera.x) * this.scale + this.width / 2, y: (vertical - this.camera.y) * this.scale + this.height / 2 };
  }

  sprite(name, horizontal, vertical, width = 1, height = width, offset = 0, frame = null) {
    const image = this.images.get(name);
    if (!image) return;
    const point = this.screenPoint(horizontal, vertical);
    const bounds = [Math.round(point.x - width * this.scale / 2), Math.round(point.y - (height / 2 + offset) * this.scale), Math.ceil(width * this.scale), Math.ceil(height * this.scale)];
    if (frame) this.context.drawImage(image, frame.x, frame.y, frame.width, frame.height, ...bounds);
    else this.context.drawImage(image, ...bounds);
  }

  actorSprite(kind, entity, width, height, offset) {
    const pose = this.effects.pose(entity.id);
    const frame = this.animator.frame(kind, entity, entity.renderDistance, pose);
    const anchored = kind.startsWith('monster_');
    this.sprite(frame?.asset || kind, entity.x + (anchored ? 0 : pose.x), entity.y + (anchored ? 0 : pose.y), width, height, offset, frame);
  }

  smooth(entity) {
    const point = this.state && !this.recordedFrames ? (entity.id === this.state.you.id && this.movement.enabled ? this.movement.sample() : this.motion.sample(entity)) : { x: entity.x, y: entity.y };
    const previous = this.positions.get(entity.id) || point;
    const displacement = distance(previous, point);
    this.positions.set(entity.id, point);
    const velocity = entity.id === this.state?.you.id && this.movement.enabled ? { velocity_x: this.movement.velocity.x, velocity_y: this.movement.velocity.y } : {};
    return { ...entity, ...point, ...velocity, renderDistance: displacement > 5 ? 0 : displacement };
  }

  findTarget() {
    if (!this.state || !this.pointer.active) return null;
    const point = this.pointer;
    if (this.catalog.revival_items?.[this.state.you.inventory[this.selected]?.kind]) {
      const player = this.state.players.find((entity) => entity.id !== this.state.you.id && entity.temperature < 5 && distance(this.positions.get(entity.id) || entity, point) <= 0.75);
      if (player) return { ...player, category: 'player' };
    }
    const monster = this.state.monsters.find((entity) => {
      const position = this.positions.get(entity.id) || entity;
      return this.monsterHitboxes.contains({ ...entity, x: position.x, y: position.y }, point, this.motion.time ?? this.state.elapsed);
    });
    if (monster) return { ...monster, category: 'monster' };
    const structure = this.state.structures.find((entity) => entity.x === tileAt(point.x) && entity.y === tileAt(point.y));
    return structure ? { ...structure, category: 'structure' } : null;
  }

  canPlace(tile, item) {
    const state = this.state;
    if (!state || !item || !buildings.has(item.kind) || this.panelOpen) return false;
    if (state.you.downed && item.kind !== 'campfire') return false;
    if (distance(this.movement.enabled ? this.movement.position : state.you, tile) > 3) return false;
    if (!state.chunks.some(([horizontal, vertical]) => Math.abs(tile.x - horizontal * 15) <= 7 && Math.abs(tile.y - vertical * 15) <= 7)) return false;
    if (state.structures.some((entity) => entity.x === tile.x && entity.y === tile.y)) return false;
    if (containers.has(item.kind) && state.structures.some((entity) => containers.has(entity.kind) && Math.max(Math.abs(entity.x - tile.x), Math.abs(entity.y - tile.y)) <= 1)) return false;
    return ![...state.players, ...state.monsters].some((entity) => {
      const point = entity.id === state.you.id && this.movement.enabled ? this.movement.position : this.positions.get(entity.id) || entity;
      return Math.hypot(Math.max(Math.abs(point.x - tile.x) - 0.5, 0), Math.max(Math.abs(point.y - tile.y) - 0.5, 0)) < 0.35;
    });
  }

  draw(delta) {
    this.elapsed += delta;
    this.animator.advance(delta);
    this.effects.advance(delta);
    this.fps += (1 / Math.max(delta, 0.001) - this.fps) * 0.04;
    const state = this.state || this.demo;
    if (!this.recordedFrames) this.motion.advance(delta);
    const monsters = state.monsters.map((entity) => this.smooth(entity));
    const worldTime = state.elapsed + (this.recordedFrames || state.paused ? 0 : Math.max(0, Math.min(0.3, performance.now() / 1000 - this.motion.arrival)));
    this.movement.selected = this.selected;
    if (!this.recordedFrames) this.movement.advance(delta, monsters);
    const players = state.players.map((entity) => this.smooth(entity));
    if (this.state) this.animator.observe({ elapsed: this.recordedFrames ? state.elapsed : this.motion.time ?? state.elapsed, paused: state.paused, players, monsters });
    const local = players.find((entity) => entity.id === state.you.id) || state.you;
    if (this.state) {
      this.camera.x = local.x;
      this.camera.y = local.y;
    } else {
      this.camera.x = -3 + Math.sin(this.elapsed * 0.07) * 0.3;
      this.camera.y = 1 + Math.cos(this.elapsed * 0.08) * 0.2;
    }
    const context = this.context;
    context.fillStyle = '#d7e5e7';
    context.fillRect(0, 0, this.width, this.height);
    const halfWidth = this.width / this.scale / 2;
    const halfHeight = this.height / this.scale / 2;
    const minimumX = Math.floor(this.camera.x - halfWidth - 1);
    const minimumY = Math.floor(this.camera.y - halfHeight - 1);
    this.drawSnow(minimumX, minimumY, halfWidth, halfHeight);
    const visible = (entity) => Math.abs(entity.x - this.camera.x) < halfWidth + 2 && Math.abs(entity.y - this.camera.y) < halfHeight + 3;
    for (const entity of this.floors || state.structures.filter((entity) => entity.kind === 'floor')) if (visible(entity)) this.sprite('floor', entity.x, entity.y, 1.03);
    for (const entity of state.ground) if (visible(entity)) {
      this.sprite(entity.item.kind, entity.x, entity.y + Math.sin(this.elapsed * 3 + entity.x) * 0.045, 0.57);
    }
    const entities = [
      ...(this.staticEntities || state.structures.filter((entity) => entity.kind !== 'floor').map((entity) => ({ ...entity, category: 'structure' }))).filter(visible),
      ...players.map((entity) => ({ ...entity, category: 'player' })),
      ...monsters.map((entity) => ({ ...entity, category: 'monster' })),
    ].filter(visible).sort((first, second) => first.y - second.y);
    this.target = this.findTarget();
    for (const entity of entities) {
      if (entity.category === 'structure') {
        const pose = this.effects.pose(entity.id);
        if (entity.kind === 'tree') this.sprite('tree', entity.x + pose.x, entity.y + pose.y, 2.05, 2.65, 0.62);
        else if (entity.kind === 'mounted_gun') {
          const occupant = players.find(player => player.id === entity.occupant);
          const direction = occupant?.id === state.you.id ? (Math.round(Math.atan2(this.pointer.y - occupant.y, this.pointer.x - occupant.x) / (Math.PI / 4)) + 8) % 8 : occupant?.seat_direction || 0;
          this.sprite(`mounted_gun_${['e', 'se', 's', 'sw', 'w', 'nw', 'n', 'ne'][direction]}`, entity.x, entity.y, 1.3, 1.3, 0.08);
        } else this.sprite(entity.lit ? 'campfire_lit' : entity.kind, entity.x + pose.x, entity.y + pose.y, entity.kind === 'wall' ? 1.15 : 1.05, entity.kind === 'wall' ? 1.6 : 1.05, entity.kind === 'wall' ? 0.27 : 0.06);
        if (entity.monster_demolition) this.label(t('world.demolition'), entity.x, entity.y - 1, '#df715b', 10);
      } else if (entity.category === 'player') {
        const owned = entity.id === state.you.id;
        if (entity.downed) this.sprite('player_downed', entity.x, entity.y, 1.25);
        else {
          const seated = entity.seated && !(owned && Math.hypot(this.movement.input.x, this.movement.input.y) > 0);
          const facing = owned ? this.pointer : { x: entity.x + Math.cos((entity.seat_direction || 0) * Math.PI / 4), y: entity.y + Math.sin((entity.seat_direction || 0) * Math.PI / 4) };
          const horizontal = facing.x - entity.x, vertical = facing.y - entity.y;
          const seatedDirection = Math.abs(horizontal) > Math.abs(vertical) ? horizontal < 0 ? 'left' : 'right' : vertical < 0 ? 'up' : 'down';
          this.actorSprite((owned ? 'player' : 'player_other') + (seated ? '_seated' : ''), { ...entity, seated, seated_direction: seated ? seatedDirection : null }, 1.1, 1.45, 0.25);
        }
        if (this.state) {
          this.label(this.state ? entity.id : t('world.traveler'), entity.x, entity.y - 1.16, owned ? '#f4c886' : '#eff9f7', 11);
          if (!owned) this.bar(entity.x, entity.y - 0.94, entity.temperature / 36, '#8fcede', 0.7);
        }
      } else {
        const profile = this.monsterHitboxes.profile(entity, worldTime);
        const width = profile?.width ?? (entity.big ? 1.6 : 1.1);
        const height = profile?.height ?? (entity.big ? 1.9 : 1.25);
        const offset = profile?.offset ?? (entity.big ? 0.3 : 0.13);
        if (entity.sleeping) {
          this.sprite(monsterSprite(entity, worldTime), entity.x, entity.y, width, height, offset);
          const sleepPhase = this.elapsed / (this.effects.definitions.fx_sleep_zzz?.duration || 2.4) + entity.x * 0.137 + entity.y * 0.173;
          this.effects.frame(this, 'fx_sleep_zzz', entity.x + 0.28, entity.y - (entity.big ? 1.15 : 0.9), entity.big ? 0.95 : 0.8, sleepPhase - Math.floor(sleepPhase));
        } else if (entity.big && entity.rising != null) {
          const duration = this.catalog.monster_activity?.rise_seconds ?? 1;
          const elapsed = this.recordedFrames || state.paused ? 0 : Math.max(0, Math.min(0.3, performance.now() / 1000 - this.motion.arrival));
          this.effects.frame(this, 'monster_big_rise', entity.x, entity.y - offset, width, Math.min(1, entity.rising + elapsed / duration), 0, height);
        } else {
          this.actorSprite(monsterSprite(entity, worldTime), entity, width, height, offset);
        }
        if (worldTime < (entity.burning_until ?? 0)) this.effects.frame(this, 'fx_burning', entity.x, entity.y - 0.35, entity.big ? 1.3 : 0.9, worldTime * 2 % 1);
        this.bar(entity.x, entity.y - (entity.sleeping ? 0.3 : entity.big ? 1.2 : 0.8), entity.hp / (entity.max_hp || (entity.big ? 50 : 10)), '#dc8372', entity.big ? 1 : 0.65);
      }
    }
    const hour = state.environment.hour;
    const night = (1 - Math.cos((hour - 12) / 24 * Math.PI * 2)) / 2;
    context.fillStyle = `rgba(18,39,57,${0.06 + night * 0.4})`;
    context.fillRect(0, 0, this.width, this.height);
    for (const fire of state.structures.filter((entity) => entity.lit && Math.abs(entity.x - this.camera.x) < halfWidth + 4 && Math.abs(entity.y - this.camera.y) < halfHeight + 4)) {
      const point = this.screenPoint(fire.x, fire.y);
      const radius = (3.5 + Math.sin(this.elapsed * 9) * 0.09) * this.scale;
      const gradient = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
      gradient.addColorStop(0, 'rgba(255,181,83,.31)');
      gradient.addColorStop(0.5, 'rgba(255,175,78,.16)');
      gradient.addColorStop(1, 'rgba(255,175,78,0)');
      context.fillStyle = gradient;
      context.fillRect(point.x - radius, point.y - radius, radius * 2, radius * 2);
      this.sprite('spark', fire.x + Math.sin(this.elapsed * 2) * 0.12, fire.y - (this.elapsed * 0.8 % 1) - 0.4, 0.3);
    }
    this.drawProjectiles(state.projectiles.filter((projectile) => !this.catalog.explosive_weapons?.[projectile.kind] && projectile.kind !== 'homing_missile').map((projectile) => this.recordedFrames ? projectile : ({ ...projectile, ...this.motion.sample(projectile) })));
    for (const projectile of state.projectiles) {
      if (projectile.kind === 'homing_missile') {
        const missileTime = this.recordedFrames || this.motion.time == null ? worldTime : this.motion.time + (state.paused ? 0 : this.motion.delay);
        const point = homingPosition(projectile, missileTime, this.catalog.guns.homing_missile, this.positions.get(projectile.target_id));
        if (visible(point)) this.sprite(point.asset, point.x, point.y, 0.8);
        continue;
      }
      if (!this.catalog.explosive_weapons?.[projectile.kind]) continue;
      const phase = Math.max(0, Math.min(1, (worldTime - projectile.spawned_at) / (projectile.detonates_at - projectile.spawned_at)));
      const horizontal = projectile.origin_x + (projectile.target_x - projectile.origin_x) * phase;
      const vertical = projectile.origin_y + (projectile.target_y - projectile.origin_y) * phase - 4 * phase * (1 - phase);
      this.sprite(projectile.kind === 'coin_launcher' ? 'grenade' : projectile.kind, horizontal, vertical, 0.5);
    }
    this.effects.draw(this);
    if (this.state && this.pointer.active && !this.panelOpen) this.drawPointer();
    if (this.state?.interaction.progress > 0) {
      const target = state.structures.find((structure) => `structure:${structure.id}` === state.interaction.target);
      const held = state.you.inventory[this.selected];
      const returning = state.interaction.target?.startsWith('return:');
      const reviving = state.interaction.target?.startsWith('revive:');
      const duration = returning ? this.catalog.return_items?.[held?.kind]?.duration ?? 1.5 : reviving ? this.catalog.revival_items?.[held?.kind]?.duration ?? 1.5 : this.catalog.healing_items?.[held?.kind]?.duration ?? this.catalog.explosive_weapons?.[held?.kind]?.duration ?? this.catalog.harvest_tools?.[held?.kind]?.[target?.kind] ?? (target?.kind === 'wall' || containers.has(target?.kind) ? 1.5 : 0.5);
      if (returning) this.effects.frame(this, 'fx_teleport', local.x, local.y - 0.4, 2.6, (this.elapsed * 0.7) % 1);
      this.bar(local.x, local.y + 0.7, Math.min(1, state.interaction.progress / duration), returning ? '#ac9afa' : '#efbb78', 0.9);
    }
    context.fillStyle = 'rgba(255,255,255,.55)';
    for (let index = 0; index < 65; index++) {
      const horizontal = ((index * 197.3 + this.elapsed * (7 + index % 3)) % (this.width + 20)) - 10;
      const vertical = ((index * 73.7 + this.elapsed * (12 + index % 8)) % (this.height + 20)) - 10;
      context.fillRect(horizontal, vertical, index % 4 === 0 ? 2 : 1, index % 4 === 0 ? 2 : 1);
    }
    const active = new Set([...players, ...monsters].map((entity) => entity.id));
    for (const key of this.positions.keys()) if (!active.has(key)) this.positions.delete(key);
  }

  drawSnow(minimumX, minimumY, halfWidth, halfHeight) {
    if (!this.snow || minimumX < this.snow.left || minimumY < this.snow.top || this.camera.x + halfWidth + 1 > this.snow.right || this.camera.y + halfHeight + 1 > this.snow.bottom) {
      const left = minimumX - 3, top = minimumY - 3;
      const columns = Math.ceil(this.width / this.scale) + 10;
      const rows = Math.ceil(this.height / this.scale) + 10;
      const canvas = document.createElement('canvas');
      canvas.width = Math.ceil(columns * this.scale * this.pixelRatio);
      canvas.height = Math.ceil(rows * this.scale * this.pixelRatio);
      const context = canvas.getContext('2d', { alpha: false });
      context.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
      context.imageSmoothingEnabled = false;
      context.fillStyle = '#d7e5e7';
      context.fillRect(0, 0, columns * this.scale, rows * this.scale);
      for (let horizontal = 0; horizontal < columns; horizontal++) {
        for (let vertical = 0; vertical < rows; vertical++) {
          const variant = Math.abs(((left + horizontal) * 73856093 ^ (top + vertical) * 19349663) % 3);
          const image = this.images.get(`snow_${variant}`);
          if (image) context.drawImage(image, Math.round(horizontal * this.scale), Math.round(vertical * this.scale), Math.ceil(this.scale * 1.01), Math.ceil(this.scale * 1.01));
        }
      }
      this.snow = { canvas, left, top, right: left + columns - 1, bottom: top + rows - 1, width: canvas.width / this.pixelRatio, height: canvas.height / this.pixelRatio };
    }
    const point = this.screenPoint(this.snow.left - 0.5, this.snow.top - 0.5);
    this.context.drawImage(this.snow.canvas, point.x, point.y, this.snow.width, this.snow.height);
  }

  projectileGlow(color, length, width) {
    const key = `${color}:${length}:${width}`;
    let entry = this.projectileGlows.get(key);
    if (entry) return entry;
    const padding = 30 / this.pixelRatio + width;
    const span = length * this.scale;
    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil((span + padding * 2) * this.pixelRatio);
    canvas.height = Math.ceil(padding * 2 * this.pixelRatio);
    const context = canvas.getContext('2d');
    context.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
    context.lineCap = 'round';
    context.lineWidth = width;
    context.strokeStyle = color;
    context.shadowColor = color;
    context.shadowBlur = 10;
    context.beginPath();
    context.moveTo(padding, padding);
    context.lineTo(padding + span, padding);
    context.stroke();
    entry = { canvas, left: -padding - span, top: -padding, width: canvas.width / this.pixelRatio, height: canvas.height / this.pixelRatio };
    if (this.projectileGlows.size >= 64) this.projectileGlows.delete(this.projectileGlows.keys().next().value);
    this.projectileGlows.set(key, entry);
    return entry;
  }

  drawProjectiles(projectiles) {
    const context = this.context;
    context.save();
    context.lineCap = 'round';
    const width = Math.max(5, this.scale * 0.16);
    for (const projectile of projectiles) {
      if (Number.isFinite(projectile.range_radius)) {
        const local = this.state && projectile.range_player === this.state.you.id;
        const center = local ? this.positions.get(this.state.you.id) || this.state.you : { x: projectile.range_x, y: projectile.range_y };
        const radius = local ? Math.hypot(...this.viewport()) / 2 : projectile.range_radius;
        if (Math.hypot(projectile.x - center.x, projectile.y - center.y) > radius + 1e-9) continue;
      }
      const point = this.screenPoint(projectile.x, projectile.y);
      const magnitude = Math.hypot(projectile.velocity_x, projectile.velocity_y) || 1;
      const length = Number.isFinite(projectile.origin_x) && Number.isFinite(projectile.origin_y) ? Math.min(0.8, Math.hypot(projectile.x - projectile.origin_x, projectile.y - projectile.origin_y)) : 0.8;
      const tailX = point.x - projectile.velocity_x / magnitude * this.scale * length;
      const tailY = point.y - projectile.velocity_y / magnitude * this.scale * length;
      const weapon = this.catalog.guns?.[projectile.weapon_kind];
      const color = projectile.hostile ? '#ff356d' : weapon?.freeze_duration ? '#63e7ff' : weapon?.burn_duration ? '#ffad43' : '#ff493d';
      context.beginPath();
      context.moveTo(tailX, tailY);
      context.lineTo(point.x, point.y);
      context.strokeStyle = '#702237';
      context.lineWidth = width + 3;
      context.stroke();
      const glow = this.projectileGlow(color, length, width);
      context.save();
      context.translate(point.x, point.y);
      context.rotate(Math.atan2(projectile.velocity_y, projectile.velocity_x));
      context.imageSmoothingEnabled = true;
      context.drawImage(glow.canvas, glow.left, glow.top, glow.width, glow.height);
      context.restore();
      context.strokeStyle = '#fff1df';
      context.lineWidth = Math.max(2, width * 0.35);
      context.stroke();
      context.fillStyle = color;
      context.beginPath();
      context.arc(point.x, point.y, this.monsterHitboxes.bulletRadius * this.scale, 0, Math.PI * 2);
      context.fill();
    }
    context.restore();
  }

  drawPointer() {
    const item = this.state.you.inventory[this.selected];
    const context = this.context;
    const tile = { x: tileAt(this.pointer.x), y: tileAt(this.pointer.y) };
    const point = this.screenPoint(tile.x, tile.y);
    if (item && buildings.has(item.kind)) {
      const valid = this.canPlace(tile, item);
      context.fillStyle = valid ? 'rgba(105,195,157,.23)' : 'rgba(222,115,100,.22)';
      context.strokeStyle = valid ? '#9ee0b4' : '#f19782';
      context.fillRect(point.x - this.scale / 2, point.y - this.scale / 2, this.scale, this.scale);
      context.lineWidth = 2;
      context.strokeRect(point.x - this.scale / 2, point.y - this.scale / 2, this.scale, this.scale);
      context.globalAlpha = 0.55;
      this.sprite(item.kind, tile.x, tile.y, 1.05);
      context.globalAlpha = 1;
    } else if (this.target?.category === 'structure') {
      context.strokeStyle = distance(this.state.you, this.target) <= (containers.has(this.target.kind) ? 2 : 3) ? '#f4d3a0' : '#afbdc0';
      context.lineWidth = 1.5;
      context.strokeRect(point.x - this.scale / 2 + 1, point.y - this.scale / 2 + 1, this.scale - 2, this.scale - 2);
    }
    const aim = this.screenPoint(this.pointer.x, this.pointer.y);
    context.strokeStyle = 'rgba(30,56,62,.85)';
    context.lineWidth = 1.5;
    context.beginPath();
    context.arc(aim.x, aim.y, 4, 0, Math.PI * 2);
    context.moveTo(aim.x - 8, aim.y); context.lineTo(aim.x - 5, aim.y);
    context.moveTo(aim.x + 5, aim.y); context.lineTo(aim.x + 8, aim.y);
    context.moveTo(aim.x, aim.y - 8); context.lineTo(aim.x, aim.y - 5);
    context.moveTo(aim.x, aim.y + 5); context.lineTo(aim.x, aim.y + 8);
    context.stroke();
  }

  label(text, horizontal, vertical, color, size) {
    const point = this.screenPoint(horizontal, vertical);
    const context = this.context;
    context.font = `600 ${Math.max(9, size * Math.min(1.3, this.scale / 40))}px "Segoe UI", "Microsoft YaHei", sans-serif`;
    context.textAlign = 'center';
    context.lineWidth = 3;
    context.strokeStyle = 'rgba(19,40,46,.7)';
    context.strokeText(text, point.x, point.y);
    context.fillStyle = color;
    context.fillText(text, point.x, point.y);
  }

  bar(horizontal, vertical, fraction, color, width) {
    const point = this.screenPoint(horizontal, vertical);
    const context = this.context;
    const pixels = width * this.scale;
    context.fillStyle = '#263e45';
    context.fillRect(point.x - pixels / 2 - 1, point.y - 1, pixels + 2, 5);
    context.fillStyle = color;
    context.fillRect(point.x - pixels / 2, point.y, Math.max(0, Math.min(1, fraction)) * pixels, 3);
  }
}
