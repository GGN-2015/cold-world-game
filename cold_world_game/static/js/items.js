export const PERSONAL_STORAGE_KINDS = Object.freeze(['inventory', 'backpack']);
export const NORMAL_STORAGE_KINDS = Object.freeze(['inventory', 'backpack', 'chest']);
export const isPersonalStorage = (kind) => PERSONAL_STORAGE_KINDS.includes(kind);
export const itemCount = (item) => item ? item.count ?? 1 : 0;
export const stackLimit = (catalog, item, kind) => NORMAL_STORAGE_KINDS.includes(kind) ? catalog.stack_limits?.[item.kind] ?? 1 : 1;
export const mergeable = (catalog, first, second, kind) => Boolean(first && second && first.kind === second.kind && (first.ammo ?? null) === (second.ammo ?? null) && (first.uses ?? null) === (second.uses ?? null) && stackLimit(catalog, first, kind) > itemCount(first));

export function destinationSlot(player, kind, item, catalog) {
  const storage = player[kind];
  const partial = storage.findIndex(existing => mergeable(catalog, existing, item, kind));
  return partial < 0 ? storage.findIndex(existing => !existing) : partial;
}

export function recipeFits(player, recipe, catalog) {
  const storages = ['backpack', 'inventory'].map(kind => ({kind, items:player[kind].map(item => item ? {...item} : null)}));
  if ((player.money ?? 0) < (recipe.inputs.coin ?? 0)) return false;
  for (const [kind, required] of Object.entries(recipe.inputs)) {
    if (kind === 'coin') continue;
    let remaining = required;
    for (const storage of storages) for (let slot = 0; slot < storage.items.length; slot++) {
      const item = storage.items[slot];
      if (!item || item.kind !== kind || !remaining) continue;
      const amount = Math.min(remaining, itemCount(item));
      remaining -= amount;
      if (amount === itemCount(item)) storage.items[slot] = null;
      else item.count = itemCount(item) - amount;
    }
    if (remaining) return false;
  }
  if (recipe.output === 'coin') return true;
  let remaining = recipe.count;
  const output = {kind:recipe.output, ammo:null, uses:null};
  for (const storage of storages) {
    const limit = stackLimit(catalog, output, storage.kind);
    for (const item of storage.items) {
      if (!item) remaining -= limit;
      else if (mergeable(catalog, item, output, storage.kind)) remaining -= limit - itemCount(item);
      if (remaining <= 0) return true;
    }
  }
  return false;
}
