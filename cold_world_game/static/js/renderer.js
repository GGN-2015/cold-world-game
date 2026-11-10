import { buildings, containers, distance, tileAt } from './catalog.js';
import { t } from './i18n.js';
import { ActorAnimator } from './animation.js';
import { isMobileDevice } from './mobile.js';
import { CombatEffects } from './effects.js';
import { SnapshotMotion } from './motion.js';

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
  return { images, animations: manifest.animations || {}, effects: manifest.effects || {} };
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
  constructor(canvas, images, animations = {}, effects = {}) {
    this.canvas = canvas;
    this.context = canvas.getContext('2d', { alpha: false });
    this.images = images;
    this.animator = new ActorAnimator(animations);
    this.effects = new CombatEffects(effects);
    this.motion = new SnapshotMotion();
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
    this.scale = isMobileDevice ? Math.max(this.width / 28, this.height / 24) : this.width / 32;
    this.pixelRatio = ratio;
    this.snow = null;
  }

  setState(state) {
    const first = !this.state;
    this.state = state;
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

  reset() {
    this.state = null;
    this.positions.clear();
    this.animator.reset();
    this.effects.reset();
    this.motion.reset();
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
    this.sprite(frame?.asset || kind, entity.x + pose.x, entity.y + pose.y, width, height, offset, frame);
  }

  smooth(entity) {
    const point = this.state ? this.motion.sample(entity) : { x: entity.x, y: entity.y };
    const previous = this.positions.get(entity.id) || point;
    const displacement = distance(previous, point);
    this.positions.set(entity.id, point);
    return { ...entity, ...point, renderDistance: displacement > 5 ? 0 : displacement };
  }

  findTarget() {
    if (!this.state || !this.pointer.active) return null;
    const point = this.pointer;
    const monster = this.state.monsters.find((entity) => distance(this.positions.get(entity.id) || entity, point) < (entity.big ? 0.65 : 0.5));
    if (monster) return { ...monster, category: 'monster' };
    const structure = this.state.structures.find((entity) => entity.x === tileAt(point.x) && entity.y === tileAt(point.y));
    return structure ? { ...structure, category: 'structure' } : null;
  }

  canPlace(tile, item) {
    const state = this.state;
    if (!state || !item || !buildings.has(item.kind) || this.panelOpen) return false;
    if (state.you.downed && item.kind !== 'campfire') return false;
    if (distance(state.you, tile) > 3) return false;
    if (!state.chunks.some(([horizontal, vertical]) => Math.abs(tile.x - horizontal * 15) <= 7 && Math.abs(tile.y - vertical * 15) <= 7)) return false;
    if (state.structures.some((entity) => entity.x === tile.x && entity.y === tile.y)) return false;
    if (['chest', 'campfire'].includes(item.kind) && state.structures.some((entity) => ['chest', 'campfire'].includes(entity.kind) && Math.max(Math.abs(entity.x - tile.x), Math.abs(entity.y - tile.y)) <= 1)) return false;
    return ![...state.players, ...state.monsters].some((entity) => Math.hypot(Math.max(Math.abs(entity.x - tile.x) - 0.5, 0), Math.max(Math.abs(entity.y - tile.y) - 0.5, 0)) < 0.35);
  }

  draw(delta) {
    this.elapsed += delta;
    this.animator.advance(delta);
    this.effects.advance(delta);
    this.fps += (1 / Math.max(delta, 0.001) - this.fps) * 0.04;
    const state = this.state || this.demo;
    this.motion.advance(delta);
    const players = state.players.map((entity) => this.smooth(entity));
    const monsters = state.monsters.map((entity) => this.smooth(entity));
    if (this.state) this.animator.observe({ elapsed: this.motion.time ?? state.elapsed, paused: state.paused, players, monsters });
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
    for (const entity of state.structures) if (entity.kind === 'floor' && visible(entity)) this.sprite('floor', entity.x, entity.y, 1.03);
    for (const entity of state.ground) if (visible(entity)) {
      this.sprite(entity.item.kind, entity.x, entity.y + Math.sin(this.elapsed * 3 + entity.x) * 0.045, 0.57);
    }
    const entities = [
      ...state.structures.filter((entity) => entity.kind !== 'floor').map((entity) => ({ ...entity, category: 'structure' })),
      ...players.map((entity) => ({ ...entity, category: 'player' })),
      ...monsters.map((entity) => ({ ...entity, category: 'monster' })),
    ].filter(visible).sort((first, second) => first.y - second.y);
    this.target = this.findTarget();
    for (const entity of entities) {
      if (entity.category === 'structure') {
        const pose = this.effects.pose(entity.id);
        if (entity.kind === 'tree') this.sprite('tree', entity.x + pose.x, entity.y + pose.y, 2.05, 2.65, 0.62);
        else this.sprite(entity.lit ? 'campfire_lit' : entity.kind, entity.x + pose.x, entity.y + pose.y, entity.kind === 'wall' ? 1.15 : 1.05, entity.kind === 'wall' ? 1.6 : 1.05, entity.kind === 'wall' ? 0.27 : 0.06);
        if (entity.monster_demolition) this.label(t('world.demolition'), entity.x, entity.y - 1, '#df715b', 10);
      } else if (entity.category === 'player') {
        const owned = entity.id === state.you.id;
        if (entity.downed) this.sprite('player_downed', entity.x, entity.y, 1.25);
        else this.actorSprite(owned ? 'player' : 'player_other', entity, 1.1, 1.45, 0.25);
        if (this.state) {
          this.label(this.state ? entity.id : t('world.traveler'), entity.x, entity.y - 1.16, owned ? '#f4c886' : '#eff9f7', 11);
          if (!owned) this.bar(entity.x, entity.y - 0.94, entity.temperature / 36, '#8fcede', 0.7);
        }
      } else {
        this.actorSprite(entity.big ? 'monster_big' : 'monster_small', entity, entity.big ? 1.6 : 1.1, entity.big ? 1.9 : 1.25, entity.big ? 0.3 : 0.13);
        this.bar(entity.x, entity.y - (entity.big ? 1.2 : 0.8), entity.hp / (entity.big ? 50 : 10), '#dc8372', entity.big ? 1 : 0.65);
      }
    }
    const hour = state.environment.hour;
    const night = (1 - Math.cos((hour - 12) / 24 * Math.PI * 2)) / 2;
    context.fillStyle = `rgba(18,39,57,${0.06 + night * 0.4})`;
    context.fillRect(0, 0, this.width, this.height);
    for (const fire of state.structures.filter((entity) => entity.lit && visible(entity))) {
      const point = this.screenPoint(fire.x, fire.y);
      const radius = (2.7 + Math.sin(this.elapsed * 9) * 0.09) * this.scale;
      const gradient = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
      gradient.addColorStop(0, 'rgba(255,181,83,.31)');
      gradient.addColorStop(0.4, 'rgba(255,175,78,.13)');
      gradient.addColorStop(1, 'rgba(255,175,78,0)');
      context.fillStyle = gradient;
      context.fillRect(point.x - radius, point.y - radius, radius * 2, radius * 2);
      this.sprite('spark', fire.x + Math.sin(this.elapsed * 2) * 0.12, fire.y - (this.elapsed * 0.8 % 1) - 0.4, 0.3);
    }
    this.drawProjectiles(state.projectiles.map((projectile) => ({ ...projectile, ...this.motion.sample(projectile) })));
    this.effects.draw(this);
    if (this.state && this.pointer.active && !this.panelOpen) this.drawPointer();
    if (this.state?.interaction.progress > 0) this.bar(local.x, local.y + 0.7, Math.min(1, this.state.interaction.progress / (['wall', 'chest', 'vending_machine'].includes(this.target?.kind) ? 1.5 : 0.5)), '#efbb78', 0.9);
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

  drawProjectiles(projectiles) {
    const context = this.context;
    context.save();
    context.lineCap = 'round';
    const width = Math.max(5, this.scale * 0.16);
    for (const projectile of projectiles) {
      const point = this.screenPoint(projectile.x, projectile.y);
      const magnitude = Math.hypot(projectile.velocity_x, projectile.velocity_y) || 1;
      const tailX = point.x - projectile.velocity_x / magnitude * this.scale * 0.8;
      const tailY = point.y - projectile.velocity_y / magnitude * this.scale * 0.8;
      const color = projectile.hostile ? '#ff356d' : '#ff493d';
      context.beginPath();
      context.moveTo(tailX, tailY);
      context.lineTo(point.x, point.y);
      context.strokeStyle = '#702237';
      context.lineWidth = width + 3;
      context.stroke();
      context.strokeStyle = color;
      context.lineWidth = width;
      context.shadowColor = color;
      context.shadowBlur = 10;
      context.stroke();
      context.shadowBlur = 0;
      context.strokeStyle = '#fff1df';
      context.lineWidth = Math.max(2, width * 0.35);
      context.stroke();
      context.fillStyle = color;
      context.beginPath();
      context.arc(point.x, point.y, width * 0.65, 0, Math.PI * 2);
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
