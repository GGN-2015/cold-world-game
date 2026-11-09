import { assetUrl, distance, errorText, itemDetail, itemName, seasons } from './catalog.js';

const element = (tag, className = '', text = '') => {
  const node = document.createElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
};
const byId = (identifier) => document.getElementById(identifier);

export class GameUI {
  constructor(connection, catalog, controls) {
    this.connection = connection;
    this.catalog = catalog;
    this.controls = controls;
    this.state = null;
    this.panel = null;
    this.helpOpen = false;
    this.busy = false;
    this.dragSource = null;
    this.panelSignature = '';
    this.hotbarSignature = '';
    byId('inventory-button').onclick = () => this.togglePanel('inventory');
    byId('craft-button').onclick = () => this.togglePanel('craft');
    byId('panel-close').onclick = () => this.closePanel();
    byId('help-button').onclick = () => this.toggleHelp();
    byId('help-close').onclick = () => this.toggleHelp(false);
    byId('help-overlay').onclick = (event) => { if (event.target === byId('help-overlay')) this.toggleHelp(false); };
    byId('leave-button').onclick = () => controls.leave();
    byId('side-panel').addEventListener('pointerdown', () => controls.stop());
    document.addEventListener('dragend', () => {
      this.dragSource = null;
      document.querySelectorAll('.dragging,.drop-target').forEach((node) => node.classList.remove('dragging', 'drop-target'));
      if (!this.isOpen()) connection.send('ui', { open: false });
      this.panelSignature = '';
      if (this.state) this.update(this.state);
    });
  }

  isOpen() { return Boolean(this.panel || this.helpOpen); }

  toast(text, success = false) {
    const node = element('div', `toast${success ? ' success' : ''}`, text);
    byId('toasts').append(node);
    while (byId('toasts').children.length > 4) byId('toasts').firstChild.remove();
    setTimeout(() => node.remove(), 4500);
  }

  async action(type, payload = {}, success = '') {
    if (this.busy) return false;
    this.busy = true;
    this.refreshPanel();
    try {
      await this.connection.command(type, payload);
      await new Promise((resolve) => {
        const finish = () => {
          clearTimeout(timer);
          this.connection.removeEventListener('state', finish);
          resolve();
        };
        const timer = setTimeout(finish, 1000);
        this.connection.addEventListener('state', finish);
      });
      if (success) this.toast(success, true);
      return true;
    } catch (error) {
      this.toast(errorText(error));
      return false;
    } finally {
      this.busy = false;
      this.refreshPanel();
    }
  }

  togglePanel(kind) {
    if (!this.connection.ready) return;
    if (this.panel === kind) return this.closePanel();
    this.controls.stop();
    this.helpOpen = false;
    byId('help-overlay').hidden = true;
    this.panel = kind;
    this.connection.send('ui', { open: true });
    this.refreshPanel();
  }

  closePanel(send = true) {
    this.controls.stop();
    this.panel = null;
    byId('side-panel').hidden = true;
    this.panelSignature = '';
    if (send) this.connection.send('close');
  }

  toggleHelp(open = !this.helpOpen) {
    if (!this.state) return;
    this.closePanel(false);
    this.helpOpen = open;
    byId('help-overlay').hidden = !open;
    this.connection.send(open ? 'ui' : 'close', open ? { open: true } : {});
    if (open) byId('help-close').focus();
    else this.controls.focus();
  }

  reset() {
    this.state = null;
    this.panel = null;
    this.helpOpen = false;
    this.dragSource = null;
    this.panelSignature = '';
    this.hotbarSignature = '';
    byId('side-panel').hidden = true;
    byId('help-overlay').hidden = true;
  }

  update(state) {
    this.state = state;
    const you = state.you;
    byId('season-label').textContent = `${seasons[state.environment.season]} · 第 ${state.environment.day} 天`;
    const totalMinutes = Math.floor(state.environment.hour * 60) % 1440;
    byId('clock-label').textContent = `${String(Math.floor(totalMinutes / 60)).padStart(2, '0')}:${String(totalMinutes % 60).padStart(2, '0')}`;
    byId('ambient-label').textContent = `体感 ${you.ambient_temperature.toFixed(0)}°C`;
    byId('temperature-label').textContent = `${you.temperature.toFixed(1)}°C`;
    byId('temperature-fill').style.width = `${Math.max(0, you.temperature / 36 * 100)}%`;
    const displayHunger = you.hunger > 10 && you.hunger.toFixed(1) === '10.0' ? '>10' : you.hunger.toFixed(1);
    byId('hunger-label').textContent = `${displayHunger}${you.hunger > 10 ? ' · 已饱' : ''}`;
    byId('hunger-label').title = `当前饥饿值 ${you.hunger.toFixed(3)}；大于 10 时不能继续进食。`;
    byId('hunger-fill').style.width = `${Math.max(0, Math.min(100, you.hunger * 10))}%`;
    byId('coordinate-label').textContent = `坐标 ${you.x.toFixed(1)}, ${you.y.toFixed(1)}`;
    byId('player-label').textContent = you.id;
    byId('downed-notice').hidden = !you.downed;
    const selected = this.controls.selected();
    byId('equipped-label').textContent = itemDetail(you.inventory[selected], this.catalog);
    const hotbarSignature = JSON.stringify([you.inventory, selected]);
    if (hotbarSignature !== this.hotbarSignature && !this.dragSource) {
      this.hotbarSignature = hotbarSignature;
      byId('hotbar').replaceChildren(...you.inventory.map((item, slot) => this.itemSlot(item, { kind: 'inventory', slot }, true)));
    }
    if (state.container && !this.helpOpen && !['craft', 'inventory'].includes(this.panel)) this.panel = 'container';
    if (!state.container && this.panel === 'container') this.closePanel(false);
    this.refreshPanel();
    if (state.fault) {
      byId('connection-banner').hidden = false;
      byId('connection-banner').textContent = '服务器存档异常，世界已暂停。请检查服务端终端。';
    }
  }

  updateHint(target) {
    const hint = byId('context-hint');
    if (!this.state || this.isOpen() || !target) { hint.hidden = true; return; }
    const equipped = this.state.you.inventory[this.controls.selected()];
    let text = '';
    if (target.category === 'structure') {
      const near = distance(this.state.you, target) <= (['chest', 'campfire'].includes(target.kind) ? 2 : 3);
      if (['chest', 'campfire'].includes(target.kind)) text = `${itemName(target.kind)} · ${near ? '左键打开' : '再靠近一点'}${equipped?.kind === 'axe' && distance(this.state.you, target) <= 3 ? ' · Shift + 长按左键拆除' : ''}`;
      else if (equipped?.kind === 'axe') text = `${itemName(target.kind)} · ${target.monster_demolition ? '怪物正在拆除，无法同时拆除' : near ? '长按左键收集' : '再靠近一点'}`;
    } else {
      text = `${target.big ? '大怪' : '小怪'} · ${target.hp} HP`;
      if (equipped?.kind === 'axe') text += distance(this.state.you, target) <= this.catalog.axe.range ? ' · 单击左键攻击' : ` · 超出斧头 ${this.catalog.axe.range} 格范围`;
    }
    hint.textContent = text;
    hint.hidden = !text;
  }

  refreshPanel() {
    if (!this.state || !this.panel || this.dragSource) return;
    const container = this.state.container;
    const signature = JSON.stringify([this.panel, this.state.you.inventory, this.controls.selected(), container ? { ...container, burn_remaining: Math.ceil(container.burn_remaining || 0) } : null, this.busy]);
    if (signature === this.panelSignature) return;
    this.panelSignature = signature;
    const body = byId('panel-body');
    body.replaceChildren();
    byId('side-panel').hidden = false;
    byId('panel-kicker').textContent = this.panel === 'craft' ? 'MADE BY YOU' : this.panel === 'container' ? 'A LITTLE SHELTER' : 'SURVIVAL KIT';
    if (this.panel === 'craft') this.renderCraft(body);
    else if (this.panel === 'inventory') {
      byId('panel-title').textContent = '随身背包';
      byId('panel-description').textContent = '每格一件物品。拖到空格整理，选中后按 Q 丢弃。';
      const grid = element('div', 'bag-grid');
      grid.append(...this.state.you.inventory.map((item, slot) => this.itemSlot(item, { kind: 'inventory', slot })));
      body.append(grid, element('p', 'bag-description', '枪械弹药和火种次数显示在物品右下角。靠近地面物品会自动拾取；新丢下的物品有一秒拾取冷却。'));
      const drop = element('button', 'small-button wide', '丢弃当前选中物品');
      drop.disabled = this.busy || !this.state.you.inventory[this.controls.selected()];
      drop.onclick = () => this.action('drop', { slot: this.controls.selected() });
      body.append(drop);
    } else if (container) {
      byId('panel-title').textContent = itemName(container.kind);
      byId('panel-description').textContent = '拖动背包物品到空格存入。点击容器物品取出，Shift 点击背包物品快速存入。';
      if (container.kind === 'chest') {
        body.append(element('div', 'container-meta', `${container.slots.filter(Boolean).length} / 30 格 · 物品不堆叠`));
        const grid = element('div', 'chest-grid');
        grid.append(...container.slots.map((item, slot) => this.itemSlot(item, { kind: 'chest', id: container.id, slot })));
        body.append(grid);
      } else this.renderFire(body, container);
      const structure = this.state.structures.find((entry) => entry.id === container.id);
      if (structure?.monster_demolition) body.append(element('p', 'panel-warning', '怪物正在拆除这个建筑，你不能同时拆除它。'));
    }
  }

  itemSlot(item, endpoint, hotbar = false) {
    const selected = endpoint.kind === 'inventory' && endpoint.slot === this.controls.selected();
    const node = element('button', `item-slot${item ? '' : ' empty'}${selected ? ' selected' : ''}`);
    node.type = 'button';
    node.title = itemDetail(item, this.catalog);
    node.setAttribute('aria-label', `${endpoint.kind === 'inventory' ? '背包' : '容器'}格 ${endpoint.slot == null ? '' : endpoint.slot + 1}：${itemDetail(item, this.catalog)}`);
    node.dataset.kind = endpoint.kind;
    if (endpoint.slot != null) node.dataset.slot = endpoint.slot;
    if (hotbar) node.append(element('span', 'slot-key', String((endpoint.slot + 1) % 10)));
    if (item) {
      const image = element('img');
      image.src = assetUrl(item.kind);
      image.alt = itemName(item.kind);
      image.draggable = false;
      node.append(image);
      const count = item.ammo ?? item.uses;
      if (count != null) node.append(element('span', 'item-count', String(count)));
    }
    node.addEventListener('pointerdown', (event) => { event.stopPropagation(); this.controls.stop(); });
    node.onclick = (event) => {
      if (this.busy) return;
      if (endpoint.kind === 'inventory') {
        this.controls.select(endpoint.slot);
        if (event.shiftKey && item && this.state.container) this.quickDeposit(endpoint, item);
      } else if (item) this.quickTake(endpoint, item);
    };
    node.draggable = Boolean(item);
    node.addEventListener('dragstart', (event) => {
      if (!item || this.busy || !this.connection.ready) { event.preventDefault(); return; }
      this.controls.stop();
      this.dragSource = { endpoint, item };
      node.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', item.id);
      if (!this.isOpen()) this.connection.send('ui', { open: true });
    });
    node.addEventListener('dragover', (event) => {
      if (!this.dragSource || item || this.busy) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      node.classList.add('drop-target');
    });
    node.addEventListener('dragleave', () => node.classList.remove('drop-target'));
    node.addEventListener('drop', (event) => {
      event.preventDefault();
      node.classList.remove('drop-target');
      if (this.dragSource && !item) this.transfer(this.dragSource.endpoint, endpoint, this.dragSource.item);
    });
    return node;
  }

  transfer(source, destination, item) {
    const payload = { from: source, to: destination };
    if (source.kind !== 'fuel') payload.item_id = item.id;
    return this.action('transfer', payload);
  }

  quickTake(endpoint, item) {
    const slot = this.state.you.inventory.findIndex((entry) => !entry);
    if (slot < 0) return this.toast('背包已满，请先腾出空格。');
    this.transfer(endpoint, { kind: 'inventory', slot }, item);
  }

  quickDeposit(endpoint, item) {
    const container = this.state.container;
    if (!container) return;
    if (container.kind === 'chest') {
      const slot = container.slots.findIndex((entry) => !entry);
      if (slot < 0) return this.toast('箱子已满。');
      this.transfer(endpoint, { kind: 'chest', id: container.id, slot }, item);
    } else if (item.kind === 'wood') this.transfer(endpoint, { kind: 'fuel', id: container.id }, item);
    else if (this.catalog.igniters[item.kind]) this.transfer(endpoint, { kind: 'igniter', id: container.id }, item);
    else this.toast('篝火只接受木材和火种。');
  }

  renderCraft(body) {
    byId('panel-title').textContent = '用双手，留住温暖';
    byId('panel-description').textContent = '制作立即完成。材料消耗与产物一起保存，背包需要有足够空格。';
    const inventory = this.state.you.inventory;
    const counts = {};
    for (const item of inventory.filter(Boolean)) counts[item.kind] = (counts[item.kind] || 0) + 1;
    const list = element('div', 'recipe-list');
    for (const [identifier, recipe] of Object.entries(this.catalog.recipes)) {
      const card = element('button', 'recipe-card');
      card.type = 'button';
      card.dataset.recipe = identifier;
      const enough = Object.entries(recipe.inputs).every(([kind, amount]) => (counts[kind] || 0) >= amount);
      const free = inventory.filter((item) => !item).length + Object.values(recipe.inputs).reduce((total, amount) => total + amount, 0);
      card.disabled = this.busy || !enough || free < recipe.count;
      const icon = element('span', 'recipe-icon');
      const image = element('img'); image.src = assetUrl(recipe.output); image.alt = '';
      icon.append(image, element('small', '', `×${recipe.count}`));
      const copy = element('span', 'recipe-copy');
      copy.append(element('strong', '', identifier === 'recycle_fences' ? '回收木栅栏 → 木材' : itemName(recipe.output)));
      copy.append(element('span', enough ? '' : 'missing', Object.entries(recipe.inputs).map(([kind, amount]) => `${itemName(kind)} ${counts[kind] || 0}/${amount}`).join(' · ')));
      card.append(icon, copy, element('span', '', '＋'));
      card.onclick = () => this.action('craft', { recipe: identifier }, `制作了 ${recipe.count} 个${itemName(recipe.output)}`);
      list.append(card);
    }
    body.append(list);
  }

  renderFire(body, container) {
    const structure = this.state.structures.find((entry) => entry.id === container.id);
    const lit = Boolean(structure?.lit);
    const overview = element('div', 'fire-overview');
    const image = element('img'); image.src = assetUrl(lit ? 'campfire_lit' : 'campfire'); image.alt = '篝火';
    const copy = element('div');
    const remaining = Math.ceil(container.burn_remaining || 0);
    copy.append(element('strong', '', lit ? '火还亮着' : '生一堆火吧'), element('p', '', lit ? `本段燃烧剩余 ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}` : '放入木材与火种后点燃'));
    overview.append(image, copy); body.append(overview);
    const fuel = element('section', 'fire-section');
    fuel.append(element('div', 'fire-section-label', `储备木材 · ${container.fuel} / 16`));
    const grid = element('div', 'fuel-grid');
    for (let index = 0; index < 16; index++) grid.append(element('span', `fuel-unit${index < container.fuel ? ' filled' : ''}`));
    grid.addEventListener('dragover', (event) => {
      if (this.dragSource?.item.kind === 'wood') { event.preventDefault(); grid.classList.add('drop-target'); }
    });
    grid.addEventListener('dragleave', () => grid.classList.remove('drop-target'));
    grid.addEventListener('drop', (event) => {
      event.preventDefault();
      grid.classList.remove('drop-target');
      if (this.dragSource) this.transfer(this.dragSource.endpoint, { kind: 'fuel', id: container.id }, this.dragSource.item);
    });
    const buttons = element('div', 'fire-buttons');
    const put = element('button', 'small-button', '存入 1 木材');
    const woodSlot = this.state.you.inventory.findIndex((item) => item?.kind === 'wood');
    put.disabled = this.busy || woodSlot < 0 || container.fuel >= 16;
    put.dataset.action = 'put-fuel';
    put.onclick = () => this.transfer({ kind: 'inventory', slot: woodSlot }, { kind: 'fuel', id: container.id }, this.state.you.inventory[woodSlot]);
    const take = element('button', 'small-button', '取回 1 木材');
    take.disabled = this.busy || container.fuel <= 0;
    take.onclick = () => this.quickTake({ kind: 'fuel', id: container.id }, { kind: 'wood' });
    buttons.append(put, take); fuel.append(grid, buttons); body.append(fuel);
    const igniter = element('section', 'fire-section');
    igniter.append(element('div', 'fire-section-label', '火种 · 点燃时消耗 1 次'));
    const row = element('div', 'igniter-row');
    row.append(this.itemSlot(container.igniter, { kind: 'igniter', id: container.id }));
    const igniterSlot = this.state.you.inventory.findIndex((item) => item && this.catalog.igniters[item.kind] && item.uses > 0);
    const insert = element('button', 'small-button', container.igniter ? '取回火种' : '从背包放入火种');
    insert.disabled = this.busy || (!container.igniter && igniterSlot < 0);
    insert.dataset.action = 'put-igniter';
    insert.onclick = () => container.igniter ? this.quickTake({ kind: 'igniter', id: container.id }, container.igniter) : this.transfer({ kind: 'inventory', slot: igniterSlot }, { kind: 'igniter', id: container.id }, this.state.you.inventory[igniterSlot]);
    row.append(insert); igniter.append(row); body.append(igniter);
    const light = element('button', 'primary-button fire-light', lit ? '正在燃烧' : '点燃篝火');
    light.disabled = this.busy || lit || !container.fuel || !(container.igniter?.uses > 0);
    light.dataset.action = 'light';
    light.onclick = () => this.action('light', { id: container.id }, '篝火已点燃，靠近一点取暖吧。');
    body.append(light, element('p', 'bag-description', '每个木材燃烧现实 6 分钟，储备木材会自动续燃。1–2 格恢复体温，3 格保温；距离按曼哈顿距离计算。'));
  }
}
