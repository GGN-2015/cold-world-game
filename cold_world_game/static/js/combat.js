import { containers, tileAt } from './catalog.js';

export class LocalCombat {
  constructor(renderer, audio, catalog) {
    this.renderer = renderer;
    this.audio = audio;
    this.catalog = catalog;
    this.session = Math.random().toString(36).slice(2, 10);
    this.sequence = 0;
    this.predictions = new Map();
    this.cooldownUntil = 0;
  }

  begin(state, selected, aim, now = performance.now() / 1000) {
    const item = state?.you.inventory[selected];
    const settings = this.catalog.melee_weapons?.[item?.kind] || (item?.kind === 'axe' ? this.catalog.axe : null);
    if (!settings || state.paused || state.fault || state.you.downed || state.you.temperature < 5 || (item.uses != null && item.uses <= 0) || now < this.cooldownUntil) return null;
    const origin = this.renderer.movement.enabled ? this.renderer.movement.sample() : state.you;
    const horizontal = aim.x - origin.x, vertical = aim.y - origin.y;
    const magnitude = Math.hypot(horizontal, vertical);
    if (magnitude < 1e-9) return null;
    const structure = state.structures.find((entity) => entity.x === tileAt(aim.x) && entity.y === tileAt(aim.y));
    if (structure && (containers.has(structure.kind) || this.renderer.findTarget()?.category !== 'monster')) return null;
    const attackId = `${this.session}:${++this.sequence}`;
    const event = { type: 'melee', actor: state.you.id, kind: item.kind, x: origin.x, y: origin.y, direction: [horizontal / magnitude, vertical / magnitude], range: settings.range, arc_degrees: settings.arc_degrees, attack_id: attackId, predicted: true };
    this.cooldownUntil = now + settings.interval;
    this.renderer.effects.predict(event);
    this.predictions.set(attackId, { created: now, source: this.audio.play(item.kind === 'chainsaw' ? 'chainsaw' : 'axe', 1) });
    return attackId;
  }

  reconcile(state, now = performance.now() / 1000) {
    for (const [identifier, prediction] of this.predictions) if (now - prediction.created > 10) this.predictions.delete(identifier);
    while (this.predictions.size > 128) this.predictions.delete(this.predictions.keys().next().value);
    if (!this.predictions.size) return state;
    const events = state.events.filter((event) => !(event.type === 'melee' && event.actor === state.you.id && this.predictions.has(event.attack_id)));
    return events.length === state.events.length ? state : { ...state, events };
  }

  reject(identifier) {
    const prediction = this.predictions.get(identifier);
    this.renderer.effects.cancelPrediction(identifier);
    try { prediction?.source?.stop(); } catch {}
  }

  reset() {
    for (const identifier of this.predictions.keys()) this.reject(identifier);
    this.predictions.clear();
    this.cooldownUntil = 0;
  }
}
