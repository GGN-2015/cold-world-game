import { hasTranslation, t } from './i18n.js';

export const machines = new Set(['vending_machine', 'match_machine']);
export const buildings = new Set(['wall', 'fence', 'floor', 'chest', 'campfire', ...machines]);
export const containers = new Set(['chest', 'campfire', ...machines]);
export const itemName = (kind) => hasTranslation(`item.${kind}`) ? t(`item.${kind}`) : kind;
export const seasonName = (season) => hasTranslation(`season.${season}`) ? t(`season.${season}`) : season;
export const assetUrl = (kind) => `/static/assets/${kind}.png`;
export const tileAt = (value) => Math.floor(value + 0.5);
export const distance = (first, second) => Math.hypot(first.x - second.x, first.y - second.y);

export function itemDetail(item, catalog) {
  if (!item) return t('slot.empty');
  if (item.ammo != null) return t('item.ammo', { name: itemName(item.kind), count: item.ammo });
  if (item.uses != null) return t('item.uses', { name: itemName(item.kind), count: item.uses });
  if (catalog?.foods?.[item.kind]) return t('item.food', { name: itemName(item.kind), value: catalog.foods[item.kind] });
  return itemName(item.kind);
}

export const errorText = (error) => {
  const key = `error.${error?.code || error?.message}`;
  return t(hasTranslation(key) ? key : 'error.unknown');
};
