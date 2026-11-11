const personal = new Set(['inventory', 'backpack']);
const destinations = new Set(['inventory', 'backpack', 'chest', 'fuel', 'igniter', 'wallet']);
const sources = new Set(['inventory', 'backpack', 'chest', 'igniter']);

function readSlot(state, endpoint) {
  if (personal.has(endpoint.kind)) return state.you[endpoint.kind]?.[endpoint.slot];
  if (state.container?.id !== endpoint.id) return undefined;
  if (endpoint.kind === 'chest' && state.container.kind === 'chest') return state.container.slots?.[endpoint.slot];
  if (endpoint.kind === 'igniter' && state.container.kind === 'campfire') return state.container.igniter;
  return undefined;
}

function validSlot(state, endpoint) {
  if (personal.has(endpoint.kind)) return Number.isInteger(endpoint.slot) && endpoint.slot >= 0 && endpoint.slot < state.you[endpoint.kind].length;
  if (state.container?.id !== endpoint.id) return false;
  if (endpoint.kind === 'chest') return state.container.kind === 'chest' && Number.isInteger(endpoint.slot) && endpoint.slot >= 0 && endpoint.slot < state.container.slots.length;
  return state.container.kind === 'campfire' && ['igniter', 'fuel'].includes(endpoint.kind);
}

function writeSlot(state, endpoint, item) {
  if (personal.has(endpoint.kind)) state.you[endpoint.kind][endpoint.slot] = item;
  else if (endpoint.kind === 'chest') state.container.slots[endpoint.slot] = item;
  else if (endpoint.kind === 'igniter') state.container.igniter = item;
  else if (endpoint.kind === 'fuel') state.container.fuel++;
  else if (endpoint.kind === 'wallet') state.you.money = (state.you.money ?? 0) + 1;
}

export class StoragePrediction {
  constructor(catalog = {}) {
    this.catalog = catalog;
    this.reset();
  }

  reset() {
    this.state = null;
    this.pending = new Map();
  }

  observe(state) {
    this.state = state;
    for (const sequence of this.pending.keys()) {
      if (sequence <= (state.command_sequence ?? -1)) this.pending.delete(sequence);
    }
  }

  enqueue(sequence, payload) {
    if (!Number.isSafeInteger(this.state?.command_sequence) || !sources.has(payload.from?.kind) || !destinations.has(payload.to?.kind)) return false;
    this.pending.set(sequence, { from: { ...payload.from }, to: { ...payload.to }, item_id: payload.item_id });
    return true;
  }

  reject(sequence) {
    return this.pending.delete(sequence);
  }

  clear() {
    this.pending.clear();
  }

  project() {
    if (!this.state || !this.pending.size) return this.state;
    const view = {
      ...this.state,
      you: { ...this.state.you, inventory: [...this.state.you.inventory], backpack: [...this.state.you.backpack] },
      container: this.state.container ? { ...this.state.container, slots: [...(this.state.container.slots || [])] } : null,
    };
    for (const payload of this.pending.values()) {
      if (!validSlot(view, payload.from)) continue;
      const item = readSlot(view, payload.from);
      if (!item || item.id !== payload.item_id) continue;
      const destination = item.kind === 'coin' && personal.has(payload.to.kind) ? { kind: 'wallet' } : payload.to;
      if (destination.kind === 'wallet') {
        if (item.kind !== 'coin') continue;
      } else {
        if (!validSlot(view, destination)) continue;
        if (destination.kind === 'fuel') {
          if (item.kind !== 'wood' || view.container.fuel >= 16) continue;
        } else if (destination.kind === 'igniter') {
          if (!this.catalog.igniters?.[item.kind] || !item.uses || readSlot(view, destination)) continue;
        } else if (readSlot(view, destination) !== null) continue;
      }
      writeSlot(view, payload.from, null);
      writeSlot(view, destination, item);
    }
    return view;
  }
}
