const categories = {
  weapon: { title: '武器与弹药', icon: 'axe', description: '近战、枪械、投掷与装填' },
  tool: { title: '工具与道具', icon: 'lantern', description: '消耗、手持生效、背包生效和制作维修' },
  food: { title: '食品', icon: 'canned_beans', description: '即食、需烹煮和饮料' },
  facility: { title: '建筑与设施', icon: 'campfire', description: '材料、配方、取暖与交易设施' },
  monster: { title: '怪物', icon: 'monster_big', description: '血量、攻击方式、弱点与掉落' },
};
const subtypes = {
  weapon: { melee: '近战类', gun: '枪类', throwable: '投掷类', ammo: '弹药' },
  tool: { consumable: '消耗品', held: '手持生效', carried: '背包生效', material: '制作与维修', test: '管理员测试物品' },
  food: { ready: '即食', cook: '需烹煮', drink: '饮料' },
  facility: { building: '建材与防御', utility: '储物与生存', trade: '交易与加工', outdoor: '户外固定设施', crossing: '群系设施' },
  monster: { roaming: '游荡怪', biome: '群系怪' },
};
const chestPage = 'wiki/ordinary-chest-draft.md';
const rolesPage = 'wiki/roles.md';

const main = document.getElementById('main');
const nav = document.getElementById('wiki-nav');
const search = document.getElementById('search');
const query = document.getElementById('query');
const suggestions = document.getElementById('suggestions');
const guideSearch = {
  [chestPage]: ['chest', '一区 普通箱 掉率 掉落 消耗品 装备'],
  [rolesPage]: ['lantern', '一区 道具 定位 用途 对策 食品 建筑 怪物'],
  'wiki/items.md': ['chest', '武器 击倒次数 伤害 耐久 弹量 掉率'],
  'items/weapons.md': ['rifle', '武器 弹夹 弹匣 装填 掩体 灼烧 冰冻 投掷'],
  'wiki/monsters.md': ['monster_big', '怪物 血量 生成概率 掉落 刷怪机制 刷怪率 间隔 半径 上限'],
  'world/survival.md': ['heat_patch', '房间 地板 覆盖率 体感 温度 饥饿 供暖'],
  'world/world.md': ['ring_wall', '地图 群系 密林 冰湖 迷雾 普通箱'],
  'world/combat.md': ['monster_fast', '战斗 索敌 生成 休眠 怪物'],
  'guide/arena.md': ['axe', '武器试验场 竞技场 AI 测试 历史 回放 HTML'],
  'building/building.md': ['wall', '木材 配方 合成 建造 墙 门 地板'],
  'building/outdoor-facilities.md': ['service_gun', '固定机枪 维修设备 设施'],
};
let data;
let articles;

const escapeHtml = (text) => String(text).replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]));
const asset = (name) => `/static/assets/${encodeURIComponent(name)}.png`;
const page = (path, heading = '') => `#/page/${encodeURIComponent(path)}${heading ? '/' + encodeURIComponent(heading) : ''}`;
const category = (kind) => `#/category/${kind}`;
const item = (record) => record.url ?? `#/${record.group === 'monster' ? 'monster' : 'item'}/${record.id}`;
const groupTitle = (record) => categories[record.group]?.title ?? '规则与速查';
const subtypeTitle = (record) => subtypes[record.group]?.[record.subtype] ?? '';
const tierTitle = (tier) => `${['', '一', '二', '三', '四'][tier] ?? tier}区强度`;

function navLink(href, label, icon, active) {
  return `<a href="${href}"${active ? ' aria-current="page"' : ''}>
    <img src="${asset(icon)}" alt="" width="24" height="24"><span>${label}</span></a>`;
}

function sidebar(route) {
  const [type, key] = route;
  const group = type === 'category' ? key : articles.get(key)?.group;
  nav.innerHTML = [
    navLink('#/', '百科首页', 'snowflake', !type),
    '<h2>图鉴</h2>',
    ...Object.entries(categories).map(([id, entry]) => navLink(category(id), entry.title, entry.icon, group === id)),
    '<h2>数值与规则</h2>',
    navLink(page(rolesPage), '条目定位', 'lantern', key === rolesPage),
    navLink(page(chestPage), '普通箱掉率', 'chest', key === chestPage),
    navLink(page('wiki/items.md'), '物品与武器速查', 'axe', key === 'wiki/items.md'),
    navLink(page('wiki/monsters.md'), '怪物与刷怪', 'monster_stalker', key === 'wiki/monsters.md'),
    navLink(page('guide/arena.md'), '武器试验场与回放', 'axe', key === 'guide/arena.md'),
    navLink(page('world/survival.md'), '体温与生存', 'heat_patch', key === 'world/survival.md'),
    navLink(page('world/world.md'), '地图与群系', 'ring_wall', key === 'world/world.md'),
  ].join('');
}

function titleBlock(title, trail = [], description = '') {
  return `<div class="page-title">
    <nav class="breadcrumbs" aria-label="所在位置"><a href="#/">百科首页</a>
      ${trail.map(([label, href]) => `<span aria-hidden="true">›</span><a href="${href}">${escapeHtml(label)}</a>`).join('')}
    </nav>
    <h1>${escapeHtml(title)}</h1>
    ${description ? `<p>${escapeHtml(description)}</p>` : ''}
  </div>`;
}

function itemCard(record) {
  return `<a class="item-card" href="${item(record)}">
    <span class="item-icon"><img src="${asset(record.image)}" alt="" loading="lazy" width="48" height="48"></span>
    <span class="item-copy"><strong>${escapeHtml(record.name)}</strong>
    <span>${escapeHtml(record.english)}</span></span><span class="item-arrow" aria-hidden="true">›</span>
  </a>`;
}

function categoryCard(kind, entry) {
  const count = data.entries.filter((record) => record.group === kind).length;
  return `<a class="category-card" href="${category(kind)}">
    <span class="category-icon"><img src="${asset(entry.icon)}" alt="" width="46" height="46"></span>
    <span class="category-copy"><strong>${entry.title}</strong><span>${entry.description}</span></span>
    <span class="count">${count}</span>
  </a>`;
}

function home() {
  const featured = ['axe', 'building_wand', 'light_ammo', 'lantern', 'tree_spirit', 'fast'].map((id) => articles.get(id)).filter(Boolean);
  return `<section class="hero">
    <div class="hero-content">
      <h1>寒境 Wiki</h1>
      <p class="hero-description">查武器数值、普通箱掉率、怪物弱点和建造规则。</p>
      <div class="hero-actions">
        <a class="button button-bright" href="${page('wiki/items.md')}">查看掉率与数值 <span aria-hidden="true">→</span></a>
        <a class="button button-outline" href="${category('weapon')}">浏览武器</a>
      </div>
    </div>
    <div class="hero-art" aria-hidden="true">
      <div class="moon"></div>
      <img class="hero-tree" src="${asset('tree')}" alt="">
      <img class="hero-monster" src="${asset('monster_big')}" alt="">
      <img class="hero-fire" src="${asset('campfire_lit')}" alt="">
    </div>
  </section>
  <section class="wide-section" aria-labelledby="categories-heading">
    <div class="section-heading"><h2 id="categories-heading">分类浏览</h2>
      <span>${data.itemCount} 种物品 · ${data.monsterCount} 种怪物</span></div>
    <div class="category-grid">
      ${Object.entries(categories).map(([kind, entry]) => categoryCard(kind, entry)).join('')}
      <a class="category-card" href="${page('world/world.md')}">
        <span class="category-icon"><img src="${asset('ring_wall')}" alt="" width="46" height="46"></span>
        <span class="category-copy"><strong>世界规则</strong><span>区块、群系、掉落和生存机制</span></span>
        <span class="count" aria-hidden="true">›</span>
      </a>
    </div>
  </section>
  <section class="wide-section" aria-labelledby="featured-heading">
    <div class="section-heading"><h2 id="featured-heading">常查条目</h2></div>
    <div class="item-grid">${featured.map(itemCard).join('')}</div>
  </section>`;
}

function categoryPage(kind) {
  const info = categories[kind];
  const records = data.entries.filter((entry) => entry.group === kind);
  const types = Object.entries(subtypes[kind]);
  const sections = types.map(([type, label]) => {
    const entries = records.filter((record) => record.subtype === type);
    const tiers = [...new Set(entries.map((record) => record.tier))].sort((first, second) => first - second);
    return `<section class="wide-section" aria-labelledby="${type}">
      <div class="section-heading"><h2 id="${type}">${label}</h2><span>${entries.length} 种</span></div>
      ${tiers.map((tier) => `${tier ? `<h3 class="catalog-tier" id="${type}-${tier}">${tierTitle(tier)}</h3>` : ''}
        <div class="item-grid">${entries.filter((record) => record.tier === tier).map(itemCard).join('')}</div>`).join('')}
    </section>`;
  });
  const compare = kind === 'monster' ? 'wiki/monsters.md' : 'wiki/items.md';
  return `${titleBlock(info.title, [], info.description)}
    <div class="catalog-links">
      <a class="button" href="${page(rolesPage, info.title)}">查看用途 <span aria-hidden="true">→</span></a>
      <a href="${page(compare)}">数值与掉率</a>
    </div>
    <nav class="catalog-links" aria-label="${info.title}分类">
      ${types.map(([type, label]) => `<a href="${category(kind)}/${type}">${label}</a>`).join('')}
    </nav>${sections.join('')}`;
}

function detail(record) {
  const related = record.group === 'monster' ? page('wiki/monsters.md') : page('wiki/items.md');
  const trail = [[categories[record.group].title, category(record.group)]];
  trail.push([subtypeTitle(record), `${category(record.group)}/${record.subtype}`]);
  if (record.tier) trail.push([tierTitle(record.tier), `${category(record.group)}/${record.subtype}-${record.tier}`]);
  return `${titleBlock(record.name, trail, record.english)}
    <div class="article-layout">
      <article class="prose"><h2>用途</h2><p>${escapeHtml(record.role)}</p>${record.article}
        <p><a href="${related}">查看数值速查</a></p></article>
      <aside class="infobox" aria-label="条目数据">
        <div class="infobox-image"><img src="${asset(record.image)}" alt="${escapeHtml(record.name)}"></div>
        <h2>${escapeHtml(record.name)}</h2>
        <dl><div><dt>游戏 ID</dt><dd><code>${escapeHtml(record.id)}</code></dd></div>
        ${record.summary.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`).join('')}</dl>
      </aside>
    </div>`;
}

function documentPage(path, record) {
  const outline = record.headings.map(([id, label]) => `<a href="${page(path, id)}">${escapeHtml(label)}</a>`).join('');
  return `${titleBlock(record.title)}<div class="article-layout document-layout">
    <article class="prose">${record.article}</article>
    ${outline ? `<aside class="outline" aria-label="本页目录"><h2>本页目录</h2>${outline}</aside>` : ''}
  </div>`;
}

function matches(value) {
  const key = value.trim().toLowerCase();
  if (!key) return [];
  const guides = Object.entries(guideSearch).map(([path, [image, keywords]]) => ({
    id: path, image, name: data.pages[path].title, english: '', group: 'page', keywords, url: page(path),
  }));
  return [...data.entries, ...guides].map((entry) => {
    const fields = [entry.name.toLowerCase(), entry.english.toLowerCase(), entry.id, groupTitle(entry), subtypeTitle(entry), entry.role ?? '', entry.keywords ?? ''];
    const score = fields.reduce((best, field) => Math.max(best, field === key ? 3 : field.startsWith(key) ? 2 : field.includes(key) ? 1 : 0), 0);
    return { entry, score };
  }).filter(({ score }) => score > 0).sort((a, b) => b.score - a.score).map(({ entry }) => entry);
}

function showSuggestions() {
  const records = matches(query.value).slice(0, 7);
  suggestions.hidden = !records.length;
  suggestions.innerHTML = records.map((record) => `<a href="${item(record)}">
    <span class="suggestion-icon"><img src="${asset(record.image)}" alt="" width="30" height="30"></span>
    <span>${escapeHtml(record.name)}<small>${escapeHtml(record.english)}</small></span>
    <span class="suggestion-category">${groupTitle(record)}</span></a>`).join('');
}

function searchPage(value) {
  const records = matches(value);
  return `${titleBlock('搜索结果', [], value ? `“${value}” · ${records.length} 个条目` : '输入名称、英文名或物品 ID。')}
    ${records.length ? `<div class="item-grid">${records.map(itemCard).join('')}</div>` : '<p class="status">没有找到匹配条目。</p>'}`;
}

function showRoute() {
  let route;
  try {
    route = location.hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent);
  } catch {
    route = ['unknown'];
  }
  const [type, key, anchor] = route;
  let content, title;
  if (!type) {
    content = home();
  } else if (type === 'category' && Object.hasOwn(categories, key)) {
    title = categories[key].title;
    content = categoryPage(key);
  } else if ((type === 'item' || type === 'monster') && articles.has(key)) {
    const record = articles.get(key);
    title = record.name;
    content = detail(record);
  } else if (type === 'page' && Object.hasOwn(data.pages, key)) {
    title = data.pages[key].title;
    content = documentPage(key, data.pages[key]);
  } else if (type === 'search') {
    title = '搜索结果';
    content = searchPage(key || '');
  } else if (type === 'main') {
    main.focus();
    return;
  } else {
    content = `${titleBlock('没有找到此条目')}<p><a href="#/">返回百科首页</a>，或在搜索框中查找。</p>`;
  }
  suggestions.hidden = true;
  main.innerHTML = content;
  document.title = title ? `${title} · 寒境 Wiki` : '寒境 Wiki';
  sidebar(route);
  const target = anchor && document.getElementById(anchor);
  if (target) target.scrollIntoView();
  else window.scrollTo(0, 0);
}

search.addEventListener('submit', (event) => {
  event.preventDefault();
  if (!data) return;
  const value = query.value.trim();
  location.hash = value ? '/search/' + encodeURIComponent(value) : '/';
  suggestions.hidden = true;
});
query.addEventListener('input', () => { if (data) showSuggestions(); });
query.addEventListener('focus', () => { if (data) showSuggestions(); });
suggestions.addEventListener('click', () => { suggestions.hidden = true; });
document.querySelector('.skip').addEventListener('click', (event) => {
  event.preventDefault();
  main.focus();
});
document.addEventListener('pointerdown', (event) => {
  if (!search.contains(event.target)) suggestions.hidden = true;
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') suggestions.hidden = true;
  if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !search.contains(document.activeElement)) {
    event.preventDefault();
    query.focus();
  }
});

try {
  const response = await fetch('/static/wiki/data.json');
  if (!response.ok) throw new Error(`Wiki data HTTP ${response.status}`);
  data = await response.json();
  articles = new Map(data.entries.map((entry) => [entry.id, entry]));
  document.getElementById('terrain-version').textContent = `地形版本 ${data.version}`;
  window.addEventListener('hashchange', showRoute);
  showRoute();
} catch (error) {
  console.error(error);
  main.textContent = '百科资料暂时无法读取。请刷新页面。';
}
