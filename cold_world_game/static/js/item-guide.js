import { buildings, containers, itemDetail } from './catalog.js';
import { t } from './i18n.js';

export function itemGuide(item, catalog) {
  if (!item) return null;
  const kind = item.kind;
  let category, effect, use;
  if (catalog.expansion_items?.[kind]) {
    category = catalog.expansion_items[kind].category;
    effect = t(`guide.effect.${kind}`);
    use = t(`guide.use.${kind}`);
  } else if (kind === 'durian' || kind === 'durian_peel') {
    category = kind === 'durian' ? 'food' : 'explosive';
    effect = t(`guide.effect.${kind}`);
    use = t(`guide.use.${kind}`);
  } else if (catalog.equipped_items?.[kind]) {
    category = 'equipment';
    effect = t(`guide.effect.${kind}`, catalog.equipped_items[kind]);
    use = t('guide.use.equipment');
  } else if (catalog.passive_items?.[kind]) {
    category = 'passive';
    effect = t(`guide.effect.${kind}`, catalog.passive_items[kind]);
    use = t('guide.use.passive');
  } else if (catalog.drinks?.[kind]) {
    category = 'drink';
    const drink = catalog.drinks[kind];
    const recoveryRate = (catalog.body_temperature_rates || [[30, 20], [20, 15]]).find(([minimum]) => drink.felt_temperature >= minimum)?.[1] ?? 0;
    effect = t(`guide.effect.${kind}`, { ...drink, recovery_rate: recoveryRate });
    use = t('guide.use.drink', catalog.drinks[kind]);
  } else if (Object.hasOwn(catalog.foods || {}, kind)) {
    category = 'food';
    effect = t('guide.effect.food', { value: catalog.foods[kind] });
    const ready = (catalog.ready_to_eat_foods || ['cola', 'oreos', 'compressed_biscuits']).includes(kind);
    use = t(ready ? 'guide.use.readyFood' : 'guide.use.cookedFood');
  } else if (catalog.guns?.[kind]) {
    category = 'gun';
    effect = t(kind === 'homing_missile' ? 'guide.effect.homing_missile' : kind === 'shotgun' ? 'guide.effect.shotgun' : 'guide.effect.gun', catalog.guns[kind]);
    use = t(kind === 'homing_missile' ? 'guide.use.homing_missile' : kind === 'rifle' ? 'guide.use.rifle' : 'guide.use.gun');
  } else if (catalog.melee_weapons?.[kind]) {
    category = 'melee';
    effect = t(`guide.effect.${kind}`, catalog.melee_weapons[kind]);
    use = t(kind === 'axe' ? 'guide.use.axe' : 'guide.use.staff');
  } else if (catalog.explosive_weapons?.[kind]) {
    category = 'explosive';
    effect = t(`guide.effect.${kind}`, catalog.explosive_weapons[kind]);
    use = t('guide.use.explosive', catalog.explosive_weapons[kind]);
  } else if (catalog.healing_items?.[kind]) {
    category = 'medical';
    effect = t(`guide.effect.${kind}`, catalog.healing_items[kind]);
    use = t('guide.use.medical', catalog.healing_items[kind]);
  } else if (catalog.revival_items?.[kind]) {
    category = 'medical';
    effect = t(`guide.effect.${kind}`, catalog.revival_items[kind]);
    use = t('guide.use.revival', catalog.revival_items[kind]);
  } else if (catalog.return_items?.[kind]) {
    category = 'return';
    effect = t(`guide.effect.${kind}`);
    use = t('guide.use.return', catalog.return_items[kind]);
  } else if (catalog.igniters?.[kind]) {
    category = 'igniter';
    effect = t('guide.effect.igniter');
    use = t('guide.use.igniter');
  } else if (buildings.has(kind)) {
    category = 'building';
    effect = t(`guide.effect.${kind}`);
    use = `${t('guide.use.place')} ${t(containers.has(kind) ? 'guide.use.container' : 'guide.use.structure')}`;
    if (containers.has(kind)) use += ` ${t('guide.use.spacing')}`;
  } else if (kind === 'wood') {
    category = 'material';
    effect = t('guide.effect.wood');
    use = t('guide.use.wood');
  } else if (kind === 'coin') {
    category = 'currency';
    effect = t('guide.effect.coin');
    use = t('guide.use.coin');
  } else {
    category = 'other';
    effect = t('guide.effect.other');
    use = t('guide.use.other');
  }
  return { category: t(`guide.category.${category}`), effect, use, detail: itemDetail(item, catalog), known: category !== 'other' };
}
