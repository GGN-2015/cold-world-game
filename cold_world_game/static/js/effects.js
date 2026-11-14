import { expansionSweeps, expansionBlasts } from './expansion-data.js';

const lifetimes = { shot: 0.15, melee: 0.28, chop: 0.28, break: 0.5, hit: 0.3, hurt: 0.3, death: 0.65, heal: 0.9, eat: 0.6, unpack: 0.6, teleport_out: 1, teleport_in: 1, explosion: 0.65 };
const neutralPose = Object.freeze({ x: 0, y: 0, reacting: false, direction: null });
const sweepEffects = { ...expansionSweeps, axe: 'fx_axe_sweep', chainsaw: 'fx_chainsaw_sweep', ice_staff: 'fx_ice_sweep', flame_staff: 'fx_flame_sweep', durian_peel: 'fx_durian_sweep' };

function poseFor(poses, identifier) {
  if (!poses.has(identifier)) poses.set(identifier, { ...neutralPose });
  return poses.get(identifier);
}

function heading(event) {
  const horizontal = event.direction?.[0] ?? (event.target_x ?? event.x + 1) - event.x;
  const vertical = event.direction?.[1] ?? (event.target_y ?? event.y) - event.y;
  const magnitude = Math.hypot(horizontal, vertical) || 1;
  return { x: horizontal / magnitude, y: vertical / magnitude, angle: Math.atan2(vertical, horizontal) };
}

export class CombatEffects {
  constructor(definitions = {}) {
    this.definitions = definitions;
    this.reset();
  }

  reset(sequence = null) {
    this.sequence = sequence;
    this.active = [];
    this.poses = null;
  }

  clear() { this.active = []; this.poses = null; }

  append(event) {
    const duration = event.type === 'melee' && sweepEffects[event.kind] ? this.definitions[sweepEffects[event.kind]]?.duration || lifetimes.melee : event.type.startsWith('teleport_') ? this.definitions.fx_teleport?.duration || lifetimes[event.type] : event.type === 'heal' ? this.definitions.fx_heal?.duration || lifetimes.heal : event.type === 'death' ? this.definitions[`${event.kind === 'monster' ? 'monster_small' : event.kind}_death`]?.duration || lifetimes.death : lifetimes[event.type];
    const direction = heading(event);
    this.active.push({ event, age: 0, duration, direction, directionIndex: (Math.round(direction.angle / (Math.PI / 4)) + 8) % 8 });
    this.poses = null;
  }

  predict(event) { this.append(event); }

  restore(state) {
    this.reset(state.event_sequence || 0);
    for (const event of state.events || []) {
      if (!lifetimes[event.type] || event.time > state.elapsed) continue;
      if (event.type === 'death') this.active = this.active.filter(effect => effect.event.actor !== event.actor || !['shot', 'melee', 'chop'].includes(effect.event.type));
      this.append(event);
      this.active[this.active.length - 1].age = state.elapsed - event.time;
    }
    this.active = this.active.filter(effect => effect.age < effect.duration).slice(-96);
  }

  cancelPrediction(identifier) {
    this.active = this.active.filter((effect) => !effect.event.predicted || effect.event.attack_id !== identifier);
    this.poses = null;
  }

  observe(state) {
    this.poses = null;
    const previous = this.sequence;
    this.sequence = Math.max(previous ?? 0, state.event_sequence || 0);
    if (previous == null || state.paused || globalThis.document?.hidden) { this.clear(); return; }
    for (const event of state.events || []) {
      if (event.id <= previous || !lifetimes[event.type] || state.elapsed - event.time > 0.6) continue;
      if (event.type === 'death') this.active = this.active.filter((effect) => effect.event.actor !== event.actor || !['shot', 'melee', 'chop'].includes(effect.event.type));
      this.append(event);
    }
    if (this.active.length > 96) {
      let excess = this.active.length - 96;
      this.active = this.active.filter((effect) => {
        if (excess > 0 && effect.event.type === 'hit') { excess--; return false; }
        return true;
      });
      if (excess > 0) this.active.splice(0, excess);
    }
  }

  advance(seconds) {
    this.poses = null;
    for (const effect of this.active) effect.age += seconds;
    this.active = this.active.filter((effect) => effect.age < effect.duration);
  }

  pose(identifier) {
    if (!this.poses) {
      this.poses = new Map();
      for (const { event, age, duration, direction } of this.active) {
        const phase = age / duration;
        if (event.type === 'hit' || event.type === 'hurt') {
          const pose = poseFor(this.poses, event.target || event.actor);
          pose.x += Math.sin(phase * Math.PI * 6) * 0.055 * (1 - phase);
          pose.reacting = true;
        } else if (event.type === 'chop') {
          poseFor(this.poses, event.target).x += Math.sin(phase * Math.PI * 5) * 0.045 * (1 - phase);
        }
        if (!['shot', 'melee', 'chop'].includes(event.type)) continue;
        const pose = poseFor(this.poses, event.actor);
        const displacement = Math.sin(phase * Math.PI) * (event.type === 'shot' ? -0.06 : 0.16);
        pose.x += direction.x * displacement;
        pose.y += direction.y * displacement;
        pose.direction = Math.abs(direction.x) > Math.abs(direction.y) ? (direction.x < 0 ? 'left' : 'right') : (direction.y < 0 ? 'up' : 'down');
        pose.reacting = event.type !== 'shot' || pose.reacting;
      }
    }
    return this.poses.get(identifier) || neutralPose;
  }

  frame(renderer, name, horizontal, vertical, size, phase, angle = 0, height = size, flipped = false) {
    const definition = this.definitions[name];
    const image = renderer.images.get(definition?.asset || name);
    if (!image) return;
    const width = definition?.frame_width || image.height;
    const frameHeight = definition?.frame_height || image.height;
    const frames = definition?.frames || Math.round(image.width / width);
    const column = Math.min(frames - 1, Math.floor(Math.max(0, phase) * frames));
    const point = renderer.screenPoint(horizontal, vertical);
    const context = renderer.context;
    if (!angle && !flipped) {
      context.drawImage(image, column * width, 0, width, frameHeight, point.x - size * renderer.scale / 2, point.y - height * renderer.scale / 2, size * renderer.scale, height * renderer.scale);
      return;
    }
    context.save();
    context.translate(point.x, point.y);
    context.rotate(angle);
    if (flipped) context.scale(-1, 1);
    context.drawImage(image, column * width, 0, width, frameHeight, -size * renderer.scale / 2, -height * renderer.scale / 2, size * renderer.scale, height * renderer.scale);
    context.restore();
  }

  draw(renderer) {
    let injury = 0;
    for (const effect of this.active) {
      const { event, age, duration, direction } = effect;
      const phase = age / duration;
      const actor = renderer.positions.get(event.actor) || event;
      if (event.type === 'shot') {
        this.frame(renderer, 'fx_muzzle', actor.x, actor.y, 0.85, phase, direction.angle);
      } else if (event.type === 'melee' || event.type === 'chop') {
        const monster = event.kind.startsWith('monster');
        const sweeping = event.type === 'melee' && Boolean(sweepEffects[event.kind]);
        const baked = sweeping && this.directionalAxe(renderer, effect, phase);
        if (!baked) this.frame(renderer, sweeping ? sweepEffects[event.kind] : monster ? 'fx_claw' : 'fx_slash', sweeping ? event.x : actor.x, sweeping ? event.y : actor.y - 0.28, sweeping ? (event.range ?? renderer.catalog?.axe?.range ?? 3) * 32 / 15 : monster ? 1.8 : 2.1, phase, direction.angle);
        if (!monster && !baked) {
          const axe = renderer.images.get(sweepEffects[event.kind] ? event.kind : event.weapon || 'axe');
          if (axe) {
            const swing = direction.angle - (sweeping ? Math.PI / 2 : 1) + phase * (sweeping ? Math.PI : 2);
            const point = renderer.screenPoint(actor.x + Math.cos(swing) * 0.55, actor.y - 0.28 + Math.sin(swing) * 0.55);
            const context = renderer.context;
            context.save();
            context.translate(point.x, point.y);
            context.rotate(swing + Math.PI / 4);
            context.drawImage(axe, -renderer.scale * 0.4, -renderer.scale * 0.4, renderer.scale * 0.8, renderer.scale * 0.8);
            context.restore();
          }
        }
        if (event.type === 'chop') this.frame(renderer, 'fx_debris', event.target_x, event.target_y - 0.2, 1.1, phase);
      } else if (event.type === 'break') {
        this.frame(renderer, 'fx_debris', event.x, event.y - 0.15, 2.2, phase);
      } else if (event.type === 'hit' || event.type === 'hurt') {
        const target = renderer.positions.get(event.target || event.actor) || event;
        this.frame(renderer, 'fx_impact', target.x, target.y - 0.4, 1.35, phase, direction.angle);
        if (event.type === 'hurt' && event.actor === renderer.state?.you.id) injury = Math.max(injury, 1 - phase);
      } else if (event.type === 'eat' || event.type === 'unpack') {
        this.frame(renderer, event.type === 'eat' ? 'fx_food_bite' : 'fx_supply_unpack', actor.x, actor.y - 0.45, 1.4, phase);
      } else if (event.type === 'heal') {
        this.frame(renderer, 'fx_heal', actor.x, actor.y - 0.45, event.kind === 'heat_patch' ? 1.4 : 2.4, phase);
      } else if (event.type === 'explosion') {
        this.frame(renderer, event.kind === 'homing_missile' ? 'fx_missile_explosion' : expansionBlasts[event.kind] || 'fx_explosion', event.x, event.y, (event.radius ?? 3) * 2, phase);
      } else if (event.type.startsWith('teleport_')) {
        this.frame(renderer, 'fx_teleport', event.x, event.y - 0.4, 3, event.type === 'teleport_out' ? 1 - phase : phase);
      } else if (event.type === 'death') {
        const big = event.kind === 'monster_big';
        const travel = Math.min(1, phase * 2);
        const horizontal = event.x + (event.knockback?.[0] || 0) * travel;
        const vertical = event.y + (event.knockback?.[1] || 0) * travel;
        this.frame(renderer, `${event.kind === 'monster' ? 'monster_small' : event.kind}_death`, horizontal, vertical - (big ? 0.3 : 0.13), big ? 1.6 : 1.1, phase, 0, big ? 1.9 : 1.25, direction.x < 0);
        if (this.active.length <= 32) this.frame(renderer, 'fx_debris', horizontal, vertical, big ? 1.4 : 1, phase);
      }
    }
    if (injury > 0) {
      const context = renderer.context;
      context.save();
      context.strokeStyle = `rgba(215,77,67,${injury * 0.4})`;
      context.lineWidth = Math.max(8, Math.min(renderer.width, renderer.height) * 0.025);
      context.strokeRect(0, 0, renderer.width, renderer.height);
      context.restore();
    }
  }

  directionalAxe(renderer, effect, phase) {
    const definition = this.definitions[sweepEffects[effect.event.kind]];
    const image = renderer.images.get(definition?.directions?.[effect.directionIndex]);
    if (!image) return false;
    const width = definition.direction_frame_width;
    const height = definition.direction_frame_height;
    const column = Math.min(definition.frames - 1, Math.floor(Math.max(0, phase) * definition.frames));
    const point = renderer.screenPoint(effect.event.x, effect.event.y);
    const size = (effect.event.range ?? renderer.catalog?.axe?.range ?? 3) / definition.radius_ratio * renderer.scale;
    renderer.context.drawImage(image, column * width, 0, width, height, point.x - size / 2, point.y - size / 2, size, size);
    return true;
  }
}
