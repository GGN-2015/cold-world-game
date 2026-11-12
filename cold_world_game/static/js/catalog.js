import { hasTranslation, t } from './i18n.js';
import { roomMachineKinds } from './machine-data.js';

export const machines = new Set(['vending_machine', 'match_machine', 'gun_machine', ...roomMachineKinds]);
export const seats = new Set(['park_bench', 'mounted_gun']);
export const buildings = new Set(['landmine', 'wall', 'fence', 'floor', 'chest', 'campfire', 'piggy_bank', ...machines]);
export const containers = new Set(['chest', 'campfire', 'piggy_bank', ...machines]);
export const itemName = (kind) => hasTranslation(`item.${kind}`) ? t(`item.${kind}`) : kind;
export const seasonName = (season) => hasTranslation(`season.${season}`) ? t(`season.${season}`) : season;
export const assetUrl = (kind) => `/static/assets/${kind}.png`;
export const tileAt = (value) => Math.floor(value + 0.5);
export const distance = (first, second) => Math.hypot(first.x - second.x, first.y - second.y);

export function itemDetail(item, catalog) {
  if (!item) return t('slot.empty');
  if (catalog?.expansion_items?.[item.kind]) return item.ammo != null ? t('item.ammo', { name: itemName(item.kind), count: item.ammo }) : item.uses != null ? t('item.uses', { name: itemName(item.kind), count: item.uses }) : itemName(item.kind);
  if (catalog?.equipped_items?.[item.kind]) return t('item.equipped', { name: itemName(item.kind), ...catalog.equipped_items[item.kind] });
  if (catalog?.passive_items?.[item.kind]) return t('item.passive', { name: itemName(item.kind), ...catalog.passive_items[item.kind] });
  if (catalog?.drinks?.[item.kind]) return t('item.drink', { name: itemName(item.kind), ...catalog.drinks[item.kind] });
  if (catalog?.melee_weapons?.[item.kind]?.freeze_duration) return t('item.iceStaffDetail', { name: itemName(item.kind), count: item.uses, ...catalog.melee_weapons[item.kind] });
  if (catalog?.melee_weapons?.[item.kind]?.burn_duration) return t('item.flameStaffDetail', { name: itemName(item.kind), count: item.uses, ...catalog.melee_weapons[item.kind] });
  if (catalog?.explosive_weapons?.[item.kind]) return t(item.kind === 'coin_launcher' ? 'item.coinLauncherDetail' : 'item.grenadeDetail', { name: itemName(item.kind), ...catalog.explosive_weapons[item.kind] });
  if (item.ammo != null) return t('item.ammo', { name: itemName(item.kind), count: item.ammo });
  if (item.uses != null) return t('item.uses', { name: itemName(item.kind), count: item.uses });
  if (catalog?.healing_items?.[item.kind]) return t(item.kind === 'heat_patch' ? 'item.warming' : 'item.healing', { name: itemName(item.kind), ...catalog.healing_items[item.kind] });
  if (catalog?.revival_items?.[item.kind]) return t('item.revival', { name: itemName(item.kind), ...catalog.revival_items[item.kind] });
  if (catalog?.foods?.[item.kind]) return t('item.food', { name: itemName(item.kind), value: catalog.foods[item.kind] });
  return itemName(item.kind);
}

export const errorText = (error) => {
  const key = `error.${error?.code || error?.message}`;
  return t(hasTranslation(key) ? key : 'error.unknown');
};
