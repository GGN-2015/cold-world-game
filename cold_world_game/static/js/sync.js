const collections = ['structures', 'players', 'monsters', 'projectiles', 'ground', 'events', 'structure_states'];
const objects = ['you', 'environment', 'movement', 'interaction', 'container'];

function applyFields(original, patch) {
  const value = { ...original, ...patch.fields };
  for (const [field, changes] of Object.entries(patch.slot_changes || {})) {
    if (!['inventory', 'backpack', 'slots'].includes(field) || !Array.isArray(original[field])) throw new Error('invalid_slot_patch');
    const slots = [...original[field]];
    const changed = new Set();
    for (const [index, item] of changes) {
      if (!Number.isInteger(index) || index < 0 || index >= slots.length || changed.has(index)) throw new Error('invalid_slot_index');
      changed.add(index);
      slots[index] = item;
    }
    value[field] = slots;
  }
  for (const field of patch.unset || []) delete value[field];
  return value;
}

export class StateSync {
  reset(state, revision = 0) {
    this.state = state;
    this.revision = revision;
    this.entities = new Map(collections.map((name) => [name, new Map((state[name] || []).map((entity) => [entity.id, entity]))]));
  }

  apply(message) {
    if (!this.state || message.base !== this.revision || message.revision !== this.revision + 1) throw new Error('state_revision_mismatch');
    const state = { ...this.state, ...message.state };
    for (const [name, patch] of Object.entries(message.objects || {})) {
      if (!objects.includes(name) || !state[name] || typeof state[name] !== 'object') throw new Error('unknown_state_object');
      state[name] = applyFields(state[name], patch);
    }
    const entities = new Map(this.entities);
    for (const [name, delta] of Object.entries(message.entities)) {
      if (!entities.has(name)) throw new Error('unknown_state_collection');
      const records = new Map(entities.get(name));
      for (const identifier of delta.remove) records.delete(identifier);
      for (const entity of delta.add) {
        if (records.has(entity.id)) throw new Error('duplicate_state_entity');
        records.set(entity.id, entity);
      }
      for (const patch of delta.update) {
        if (!records.has(patch.id)) throw new Error('missing_state_entity');
        records.set(patch.id, applyFields(records.get(patch.id), patch));
      }
      entities.set(name, records);
      state[name] = [...records.values()];
    }
    this.entities = entities;
    this.revision = message.revision;
    this.state = state;
    return state;
  }
}
