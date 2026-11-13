import { t } from './i18n.js';
import { itemGuide } from './item-guide.js';

const normalize = value => value.normalize('NFKC').toLocaleLowerCase().replace(/[_\-]+/g, ' ').trim();

export function createSearchIndex(items, catalog) {
  return items.map(item => {
    const names = ['zh', 'en'].map(locale => t(`item.${item.kind}`, {}, locale));
    const guides = ['zh', 'en'].map(locale => itemGuide(item, catalog, locale));
    const gun = catalog.guns?.[item.kind];
    const keywords = gun && (gun.automatic || item.kind === 'rifle') ? ['自动 连射 速射', 'automatic rapid fire'] : [];
    const weapon = gun ?? catalog.melee_weapons?.[item.kind];
    if (weapon?.freeze_duration) keywords.push('冰冻 冻结 减速', 'freeze frozen freezing slow');
    if (weapon?.burn_duration) keywords.push('燃烧 火焰', 'burn burning fire flame');
    return { ...item, names, searchNames: [...names, item.kind].map(normalize), keywords,
      descriptions: guides.map(guide => normalize(`${guide.category} ${guide.effect} ${guide.use}`)) };
  });
}

export function searchItems(index, query) {
  const text = normalize(query);
  if (!text) return [...index].sort((first, second) => Number(first.support === 'unused') - Number(second.support === 'unused') || first.kind.localeCompare(second.kind));
  const tokens = text.split(/\s+/).filter(Boolean);
  const contains = (value, token) => /[\u3400-\u9fff]/u.test(token) ? value.includes(token) : value.split(/[^\p{L}\p{N}]+/u).includes(token);
  const score = item => {
    let value = item.searchNames.some(name => name === text) ? 200 : item.searchNames.some(name => name.startsWith(text)) ? 100 : item.searchNames.some(name => name.includes(text)) ? 70 : 0;
    for (const token of tokens) {
      if (item.searchNames.some(name => name.includes(token))) value += 35;
      else if (item.keywords.some(keywords => contains(keywords, token))) value += 25;
      else if (item.descriptions.some(description => contains(description, token))) value += 12;
      else {
        if (!/[\u3400-\u9fff]/u.test(token)) return 0;
        const fragments = [...token].slice(1).map((character, position) => [...token][position] + character);
        const matches = fragments.filter(fragment => item.searchNames.some(name => name.includes(fragment)) || item.descriptions.some(description => description.includes(fragment))).length;
        if (fragments.length && matches / fragments.length >= 0.5) value += 4 * matches / fragments.length;
        else return 0;
      }
    }
    return value + (item.support === 'weapon' ? 3 : 0);
  };
  return index.map(item => ({ item, score: score(item) })).filter(entry => entry.score > 0)
    .sort((first, second) => second.score - first.score || first.item.kind.localeCompare(second.item.kind)).map(entry => entry.item);
}
