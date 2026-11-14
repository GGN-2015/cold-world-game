import { NORMAL_STORAGE_KINDS, isPersonalStorage, itemCount, mergeable, stackLimit } from './items.js';
const destinations = new Set(['inventory', 'backpack', 'chest', 'fuel', 'igniter', 'wallet']);
const sources = new Set(['inventory', 'backpack', 'chest', 'igniter', 'fuel']);

function readSlot(state, endpoint) {
  if (isPersonalStorage(endpoint.kind)) return state.you[endpoint.kind]?.[endpoint.slot];
  if (state.container?.id !== endpoint.id) return undefined;
  if (endpoint.kind === 'chest' && state.container.kind === 'chest') return state.container.slots?.[endpoint.slot];
  if (endpoint.kind === 'igniter' && state.container.kind === 'campfire') return state.container.igniter;
  if (endpoint.kind === 'fuel' && state.container.kind === 'campfire') return state.container.fuel ? {kind:'wood', id:`fuel:${endpoint.id}`, ammo:null, uses:null} : null;
  return undefined;
}

function validSlot(state, endpoint) {
  if (isPersonalStorage(endpoint.kind)) return Number.isInteger(endpoint.slot) && endpoint.slot >= 0 && endpoint.slot < state.you[endpoint.kind].length;
  if (state.container?.id !== endpoint.id) return false;
  if (endpoint.kind === 'chest') return state.container.kind === 'chest' && Number.isInteger(endpoint.slot) && endpoint.slot >= 0 && endpoint.slot < state.container.slots.length;
  return state.container.kind === 'campfire' && ['igniter', 'fuel'].includes(endpoint.kind);
}

function writeSlot(state, endpoint, item) {
  if (isPersonalStorage(endpoint.kind)) state.you[endpoint.kind][endpoint.slot] = item;
  else if (endpoint.kind === 'chest') state.container.slots[endpoint.slot] = item;
  else if (endpoint.kind === 'igniter') state.container.igniter = item;
  else if (endpoint.kind === 'fuel') state.container.fuel += item ? itemCount(item) : -1;
  else if (endpoint.kind === 'wallet') state.you.money = (state.you.money ?? 0) + itemCount(item);
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
    this.pending.set(sequence, { from: { ...payload.from }, to: { ...payload.to }, item_id: payload.item_id, item_kind: payload.item_kind });
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
      you: { ...this.state.you, inventory: this.state.you.inventory.map(item => item ? {...item} : null), backpack: this.state.you.backpack.map(item => item ? {...item} : null) },
      container: this.state.container ? { ...this.state.container, slots: (this.state.container.slots || []).map(item => item ? {...item} : null), igniter: this.state.container.igniter ? {...this.state.container.igniter} : null } : null,
    };
    for (const [sequence, payload] of this.pending) {
      if (!validSlot(view, payload.from)) continue;
      if (payload.from.kind === payload.to.kind && payload.from.slot === payload.to.slot && payload.from.id === payload.to.id) continue;
      const item = readSlot(view, payload.from);
      if (!item || payload.item_id != null && item.id !== payload.item_id || payload.item_kind != null && item.kind !== payload.item_kind) continue;
      const destination = item.kind === 'coin' && isPersonalStorage(payload.to.kind) ? { kind: 'wallet' } : payload.to;
      let amount = itemCount(item);
      if (destination.kind === 'wallet') {
        if (item.kind !== 'coin') continue;
      } else {
        if (!validSlot(view, destination)) continue;
        if (destination.kind === 'fuel') {
          if (item.kind !== 'wood' || view.container.fuel >= 16) continue;
          amount = Math.min(amount, 16 - view.container.fuel);
        } else if (destination.kind === 'igniter') {
          if (!this.catalog.igniters?.[item.kind] || !item.uses || readSlot(view, destination)) continue;
        } else {
          const existing = readSlot(view, destination);
          if (existing && !mergeable(this.catalog, existing, item, destination.kind)) continue;
          amount = Math.min(amount, stackLimit(this.catalog, item, destination.kind) - itemCount(existing));
        }
      }
      const moved = {...item, count:amount};
      if (amount < itemCount(item)) {
        item.count = itemCount(item) - amount;
        moved.id = `pending:${sequence}`;
      } else writeSlot(view, payload.from, null);
      const existing = readSlot(view, destination);
      if (existing && NORMAL_STORAGE_KINDS.includes(destination.kind)) existing.count = itemCount(existing) + amount;
      else writeSlot(view, destination, moved);
    }
    return view;
  }
}
