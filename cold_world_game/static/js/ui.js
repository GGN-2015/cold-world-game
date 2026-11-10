import { assetUrl, containers, distance, errorText, itemDetail, itemName, seasonName } from './catalog.js';
import { t } from './i18n.js';
import { isMobileDevice } from './mobile.js';

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
    this.touchTransfer = false;
    this.touchSelection = null;
    this.closedContainer = null;
    this.demolitionHold = null;
    this.demolitionButton = null;
    if (isMobileDevice) {
      const label = byId('inventory-button').querySelector('[data-i18n]');
      label.dataset.i18n = 'touch.backpack';
      label.textContent = t('touch.backpack');
      byId('world').setAttribute('data-i18n-aria-label', 'touch.worldLabel');
      byId('world').setAttribute('aria-label', t('touch.worldLabel'));
    }
    byId('touch-transfer-button').onclick = () => {
      this.touchTransfer = !this.touchTransfer;
      this.setTouchSelection(null);
    };
    byId('touch-transfer-drop').onclick = () => {
      if (!this.touchSelection || this.busy) return;
      const source = this.touchSelection;
      this.setTouchSelection(null);
      this.controls.dropItem(source);
    };
    byId('inventory-button').onclick = () => this.togglePanel('inventory');
    byId('craft-button').onclick = () => this.togglePanel('inventory');
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
    window.addEventListener('cold-world-languagechange', () => {
      this.panelSignature = '';
      this.hotbarSignature = '';
      if (this.state) this.update(this.state);
      for (const node of byId('toasts').children) node.refresh();
    });
  }

  isOpen() { return Boolean(this.panel || this.helpOpen); }

  toast(text, success = false) {
    const node = element('div', `toast${success ? ' success' : ''}`);
    node.refresh = () => { node.textContent = typeof text === 'function' ? text() : text; };
    node.refresh();
    byId('toasts').append(node);
    while (byId('toasts').children.length > 4) byId('toasts').firstChild.remove();
    setTimeout(() => node.remove(), 4500);
  }

  async action(type, payload = {}, success = '') {
    if (this.busy) return false;
    this.cancelDemolition();
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
      this.toast(() => errorText(error));
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
    this.closedContainer = this.state?.container?.id || this.closedContainer;
    this.panel = null;
    byId('side-panel').hidden = true;
    this.panelSignature = '';
    this.touchTransfer = false;
    this.setTouchSelection(null);
    if (send && this.connection.ready) {
      const closed = this.closedContainer;
      this.connection.command('close').then(() => {
        if (this.closedContainer === closed) this.closedContainer = null;
      }).catch(() => {});
    }
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
    this.cancelDemolition();
    this.state = null;
    this.panel = null;
    this.helpOpen = false;
    this.dragSource = null;
    this.touchTransfer = false;
    this.touchSelection = null;
    this.closedContainer = null;
    this.panelSignature = '';
    this.hotbarSignature = '';
    byId('side-panel').hidden = true;
    byId('help-overlay').hidden = true;
  }

  update(state) {
    this.state = state;
    const you = state.you;
    byId('season-label').textContent = t('world.seasonDay', { year: state.environment.year ?? 1, season: seasonName(state.environment.season), day: state.environment.day });
    const totalMinutes = Math.floor(state.environment.hour * 60) % 1440;
    byId('clock-label').textContent = `${String(Math.floor(totalMinutes / 60)).padStart(2, '0')}:${String(totalMinutes % 60).padStart(2, '0')}`;
    byId('ambient-label').textContent = t('world.ambient', { temperature: you.ambient_temperature.toFixed(0) });
    byId('temperature-label').textContent = `${you.temperature.toFixed(1)}°C`;
    byId('temperature-fill').style.width = `${Math.max(0, you.temperature / 36 * 100)}%`;
    const displayHunger = you.hunger > 10 && you.hunger.toFixed(1) === '10.0' ? '>10' : you.hunger.toFixed(1);
    byId('hunger-label').textContent = `${displayHunger}${you.hunger > 10 ? t('vital.full') : ''}`;
    byId('hunger-label').title = t('vital.hungerHint', { value: you.hunger.toFixed(3) });
    byId('hunger-fill').style.width = `${Math.max(0, Math.min(100, you.hunger * 10))}%`;
    byId('money-label').textContent = String(you.money ?? 0);
    byId('money-balance').title = t('money.balance', { count: you.money ?? 0 });
    byId('coordinate-label').textContent = t('world.coordinates', { x: you.x.toFixed(1), y: you.y.toFixed(1) });
    byId('player-label').textContent = you.id;
    byId('downed-notice').hidden = !you.downed;
    const selected = this.controls.selected();
    byId('equipped-label').textContent = itemDetail(you.inventory[selected], this.catalog);
    if (this.touchSelection) {
      const source = this.touchSelection;
      const endpoint = source.endpoint;
      const current = ['inventory', 'backpack'].includes(endpoint.kind) ? you[endpoint.kind][endpoint.slot]
        : state.container?.id === endpoint.id ? (endpoint.kind === 'igniter' ? state.container.igniter : state.container.slots?.[endpoint.slot]) : null;
      if (current?.id !== source.item.id) this.touchSelection = null;
    }
    const hotbarSignature = JSON.stringify([you.inventory, selected, this.touchTransfer, this.touchSelection]);
    if (hotbarSignature !== this.hotbarSignature && !this.dragSource) {
      this.hotbarSignature = hotbarSignature;
      byId('hotbar').replaceChildren(...you.inventory.map((item, slot) => this.itemSlot(item, { kind: 'inventory', slot }, true)));
    }
    if (!state.container) this.closedContainer = null;
    if (state.container && state.container.id !== this.closedContainer && !this.helpOpen && this.panel !== 'inventory') this.panel = 'container';
    if (!state.container && this.panel === 'container') this.closePanel(false);
    this.refreshPanel();
    this.updateDemolitionButton();
    if (state.fault) {
      byId('connection-banner').hidden = false;
      byId('connection-banner').textContent = t('connection.fault');
    }
  }

  updateHint(target) {
    const hint = byId('context-hint');
    if (!this.state || this.isOpen() || !target) { hint.hidden = true; return; }
    const equipped = this.state.you.inventory[this.controls.selected()];
    let text = '';
    if (target.category === 'structure') {
      const near = distance(this.state.you, target) <= (containers.has(target.kind) ? 2 : 3);
      if (containers.has(target.kind)) text = `${itemName(target.kind)} · ${t(near ? 'hint.open' : 'hint.nearer')}${equipped?.kind === 'axe' && distance(this.state.you, target) <= 3 ? t(target.kind === 'chest' ? 'hint.chestDismantle' : 'hint.dismantle') : ''}`;
      else if (equipped?.kind === 'axe') text = `${itemName(target.kind)} · ${t(target.monster_demolition ? 'hint.busy' : near ? 'hint.gather' : 'hint.nearer')}`;
    } else {
      text = `${t(target.big ? 'hint.bigMonster' : 'hint.smallMonster')} · ${target.hp} HP`;
      if (equipped?.kind === 'axe') text += distance(this.state.you, target) <= this.catalog.axe.range ? t('hint.attack') : t('hint.axeRange', { range: this.catalog.axe.range });
    }
    hint.textContent = text;
    hint.hidden = !text;
  }

  refreshPanel() {
    if (!this.state || !this.panel || this.dragSource) return;
    const container = this.state.container;
    const signature = JSON.stringify([this.panel, this.state.you.inventory, this.state.you.backpack, this.state.you.money, this.controls.selected(), container ? { ...container, burn_remaining: Math.ceil(container.burn_remaining || 0) } : null, this.busy, this.touchTransfer, this.touchSelection]);
    if (signature === this.panelSignature) return;
    this.cancelDemolition();
    this.demolitionButton = null;
    this.panelSignature = signature;
    const body = byId('panel-body');
    body.replaceChildren();
    byId('side-panel').hidden = false;
    byId('touch-transfer-button').setAttribute('aria-pressed', String(this.touchTransfer));
    byId('touch-transfer-drop').disabled = this.busy || !this.touchSelection;
    byId('touch-transfer-status').textContent = this.touchSelection ? t('touch.transferSelected', { item: itemDetail(this.touchSelection.item, this.catalog) }) : t(this.touchTransfer ? 'touch.transferPick' : 'touch.transferOff');
    byId('panel-kicker').textContent = t(this.panel === 'container' ? 'panel.shelter' : 'panel.kit');
    const layout = element('div', 'storage-layout');
    const bag = element('section', 'storage-column backpack-section');
    this.renderBackpack(bag);
    const detail = element('section', 'storage-column detail-section');
    if (this.panel !== 'container') {
      byId('panel-title').textContent = t('panel.inventoryTitle');
      byId('panel-description').textContent = t('panel.inventoryDescription');
      detail.append(element('h3', 'storage-heading', t('button.craft')));
      this.renderCraft(detail);
    } else if (container) {
      byId('panel-title').textContent = itemName(container.kind);
      byId('panel-description').textContent = t(container.kind === 'vending_machine' ? 'vending.description' : 'panel.containerDescription');
      detail.append(element('h3', 'storage-heading', itemName(container.kind)));
      if (container.kind === 'chest') {
        detail.append(element('div', 'container-meta', t('panel.chestSlots', { count: container.slots.filter(Boolean).length })));
        const grid = element('div', 'chest-grid');
        grid.append(...container.slots.map((item, slot) => this.itemSlot(item, { kind: 'chest', id: container.id, slot })));
        detail.append(grid);
        this.renderChestDemolition(detail, container);
      } else if (container.kind === 'vending_machine') this.renderVending(detail, container);
      else this.renderFire(detail, container);
      const structure = this.state.structures.find((entry) => entry.id === container.id);
      if (structure?.monster_demolition) detail.append(element('p', 'panel-warning', t('panel.monsterWarning')));
    }
    layout.append(bag, detail);
    body.append(layout);
    this.updateDemolitionButton();
  }

  cancelDemolition() {
    const hold = this.demolitionHold;
    if (!hold) return;
    this.demolitionHold = null;
    hold.button.classList.remove('holding');
    hold.button.style.setProperty('--demolition-progress', '0%');
    hold.button.setAttribute('aria-pressed', 'false');
    hold.button.textContent = t('chest.dismantle');
    if (hold.pointer != null && hold.button.hasPointerCapture(hold.pointer)) hold.button.releasePointerCapture(hold.pointer);
    if (this.connection.ready) this.connection.send('dismantle_chest', { pressed: false });
  }

  renderChestDemolition(body, container) {
    const button = element('button', 'chest-demolition', t('chest.dismantle'));
    button.type = 'button';
    button.id = 'chest-demolition';
    button.setAttribute('aria-pressed', 'false');
    const hint = element('p', 'container-meta', t('chest.dismantleHint'));
    hint.id = 'chest-demolition-hint';
    button.setAttribute('aria-describedby', hint.id);
    const start = (event, pointer = null) => {
      event.preventDefault();
      event.stopPropagation();
      if (button.disabled || this.demolitionHold || (pointer != null && event.button !== 0)) return;
      this.controls.stop();
      const hold = { button, pointer, container: container.id, epoch: this.state.movement?.epoch };
      this.demolitionHold = hold;
      button.classList.add('holding');
      button.setAttribute('aria-pressed', 'true');
      if (pointer != null) button.setPointerCapture(pointer);
      this.connection.command('dismantle_chest', { id: container.id, pressed: true }).catch((error) => {
        if (this.demolitionHold !== hold) return;
        this.cancelDemolition();
        this.toast(() => errorText(error));
      });
    };
    button.addEventListener('pointerdown', (event) => start(event, event.pointerId));
    for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(name, (event) => {
      if (this.demolitionHold?.pointer === event.pointerId) this.cancelDemolition();
    });
    button.addEventListener('keydown', (event) => {
      if ([' ', 'Enter'].includes(event.key)) {
        event.preventDefault();
        if (!event.repeat) start(event);
      }
    });
    button.addEventListener('keyup', (event) => {
      if ([' ', 'Enter'].includes(event.key)) { event.preventDefault(); this.cancelDemolition(); }
    });
    button.addEventListener('blur', () => this.cancelDemolition());
    button.addEventListener('contextmenu', (event) => event.preventDefault());
    this.demolitionButton = button;
    body.append(button, hint);
  }

  updateDemolitionButton() {
    const button = this.demolitionButton;
    const chest = this.state?.container;
    if (!button || chest?.kind !== 'chest' || this.panel !== 'container') return;
    const item = this.state.you.inventory[this.controls.selected()];
    const locked = this.state.structures.some((structure) => structure.id === chest.id && structure.monster_demolition);
    const empty = !chest.slots.some(Boolean);
    button.disabled = this.busy || !empty || locked || item?.kind !== 'axe' || this.state.you.downed;
    byId('chest-demolition-hint').textContent = t(!empty ? 'chest.emptyFirst' : locked ? 'panel.monsterWarning' : 'chest.dismantleHint');
    if (button.disabled || (this.demolitionHold && this.demolitionHold.epoch !== this.state.movement?.epoch)) this.cancelDemolition();
    if (this.demolitionHold) {
      const progress = this.state.interaction.target === `structure:${chest.id}` ? this.state.interaction.progress : 0;
      const percent = Math.min(100, Math.floor(progress / 1.5 * 100));
      button.style.setProperty('--demolition-progress', `${percent}%`);
      button.textContent = t('chest.dismantling', { percent });
    }
  }

  renderBackpack(body) {
    body.append(element('h3', 'storage-heading', t('bag.title')), element('div', 'container-meta', t('bag.slots', { count: this.state.you.backpack.filter(Boolean).length })));
    body.append(element('div', 'container-meta wallet-summary', t('money.balance', { count: this.state.you.money ?? 0 })));
    const grid = element('div', 'bag-grid');
    grid.append(...this.state.you.backpack.map((item, slot) => this.itemSlot(item, { kind: 'backpack', slot })));
    body.append(grid, element('p', 'bag-description', t(this.state.container?.kind === 'vending_machine' ? 'vending.backpackHint' : 'bag.transferHint')));
    body.append(element('p', 'bag-description', t('bag.pickupHint')));
  }

  playerItems() {
    return ['backpack', 'inventory'].flatMap((kind) => this.state.you[kind].map((item, slot) => ({ item, endpoint: { kind, slot } })));
  }

  setTouchSelection(source) {
    this.touchSelection = source;
    this.hotbarSignature = '';
    this.panelSignature = '';
    if (this.state && this.panel) this.update(this.state);
  }

  touchTransferTo(endpoint, item) {
    if (item) {
      const same = this.touchSelection?.item.id === item.id;
      this.setTouchSelection(same ? null : { endpoint, item });
    } else if (this.touchSelection) {
      const source = this.touchSelection;
      this.setTouchSelection(null);
      this.transfer(source.endpoint, endpoint, source.item);
    }
  }

  itemSlot(item, endpoint, hotbar = false) {
    const selected = endpoint.kind === 'inventory' && endpoint.slot === this.controls.selected();
    const node = element('button', `item-slot${item ? '' : ' empty'}${selected ? ' selected' : ''}${item && this.touchSelection?.item.id === item.id ? ' touch-selected' : ''}`);
    node.type = 'button';
    node.title = itemDetail(item, this.catalog);
    node.setAttribute('aria-label', t('slot.label', { area: t(`slot.${['inventory', 'backpack'].includes(endpoint.kind) ? endpoint.kind : 'container'}`), slot: endpoint.slot == null ? '' : endpoint.slot + 1, item: itemDetail(item, this.catalog) }));
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
      if (item?.kind === 'coin') return this.quickTake(endpoint, item);
      if (isMobileDevice && this.touchTransfer && this.panel) return this.touchTransferTo(endpoint, item);
      if (endpoint.kind === 'inventory') {
        this.controls.select(endpoint.slot);
        if (event.shiftKey && item) {
          if (this.state.container) this.quickDeposit(endpoint, item);
          else this.quickTake(endpoint, item);
        }
      } else if (endpoint.kind === 'backpack' && item) {
        if (event.shiftKey && this.state.container) this.quickDeposit(endpoint, item);
        else {
          const slot = this.state.you.inventory.findIndex((entry) => !entry);
          if (slot < 0) return this.toast(() => t('storage.hotbarFull'));
          this.transfer(endpoint, { kind: 'inventory', slot }, item);
        }
      } else if (item) this.quickTake(endpoint, item);
    };
    node.draggable = Boolean(item) && !isMobileDevice;
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
    if (item.kind === 'coin' && ['inventory', 'backpack'].includes(destination.kind)) destination = { kind: 'wallet' };
    const payload = { from: source, to: destination };
    if (source.kind !== 'fuel') payload.item_id = item.id;
    return this.action('transfer', payload);
  }

  quickTake(endpoint, item) {
    if (item.kind === 'coin') return this.transfer(endpoint, { kind: 'wallet' }, item);
    const slot = this.state.you.backpack.findIndex((entry) => !entry);
    if (slot < 0) return this.toast(() => t('storage.backpackFull'));
    this.transfer(endpoint, { kind: 'backpack', slot }, item);
  }

  quickDeposit(endpoint, item) {
    const container = this.state.container;
    if (!container) return;
    if (container.kind === 'vending_machine') return this.toast(() => t('vending.useOffers'));
    if (container.kind === 'chest') {
      const slot = container.slots.findIndex((entry) => !entry);
      if (slot < 0) return this.toast(() => t('storage.chestFull'));
      this.transfer(endpoint, { kind: 'chest', id: container.id, slot }, item);
    } else if (item.kind === 'wood') this.transfer(endpoint, { kind: 'fuel', id: container.id }, item);
    else if (this.catalog.igniters[item.kind]) this.transfer(endpoint, { kind: 'igniter', id: container.id }, item);
    else this.toast(() => t('storage.fireOnly'));
  }

  renderCraft(body) {
    body.append(element('p', 'craft-description', t('craft.description')));
    const inventory = [...this.state.you.backpack, ...this.state.you.inventory];
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
      copy.append(element('strong', '', identifier === 'recycle_fences' ? t('craft.recycle') : itemName(recipe.output)));
      copy.append(element('span', enough ? '' : 'missing', Object.entries(recipe.inputs).map(([kind, amount]) => `${itemName(kind)} ${counts[kind] || 0}/${amount}`).join(' · ')));
      card.append(icon, copy, element('span', '', '＋'));
      card.onclick = () => this.action('craft', { recipe: identifier }, () => t('craft.success', { count: recipe.count, name: itemName(recipe.output) }));
      list.append(card);
    }
    body.append(list);
  }

  renderVending(body, container) {
    const inventory = this.playerItems().map((entry) => entry.item);
    const counts = {};
    for (const item of inventory.filter(Boolean)) counts[item.kind] = (counts[item.kind] || 0) + 1;
    counts.coin = this.state.you.money ?? 0;
    body.append(element('p', 'craft-description', t('vending.balance', { wood: counts.wood || 0, coin: counts.coin || 0 })));
    const list = element('div', 'recipe-list vending-offers');
    for (const [identifier, offer] of Object.entries(this.catalog.vending_offers || {})) {
      const card = element('button', 'recipe-card');
      card.type = 'button';
      card.dataset.offer = identifier;
      const enough = Object.entries(offer.inputs).every(([kind, amount]) => (counts[kind] || 0) >= amount);
      const free = inventory.filter((item) => !item).length + Object.entries(offer.inputs).reduce((total, [kind, amount]) => total + (kind === 'coin' ? 0 : amount), 0);
      const required = offer.output === 'coin' ? 0 : offer.count;
      card.disabled = this.busy || !enough || free < required;
      const icon = element('span', 'recipe-icon');
      const image = element('img'); image.src = assetUrl(offer.output); image.alt = '';
      icon.append(image, element('small', '', `×${offer.count}`));
      const copy = element('span', 'recipe-copy');
      const cost = Object.entries(offer.inputs).map(([kind, amount]) => `${amount} × ${itemName(kind)}`).join(' + ');
      copy.append(element('strong', '', `${cost} → ${offer.count} × ${itemName(offer.output)}`));
      copy.append(element('span', enough ? '' : 'missing', Object.entries(offer.inputs).map(([kind, amount]) => `${itemName(kind)} ${counts[kind] || 0}/${amount}`).join(' · ')));
      card.title = t(free < required ? 'error.inventory_full' : 'vending.exchange');
      card.append(icon, copy, element('span', '', '→'));
      card.onclick = () => this.action('trade', { id: container.id, offer: identifier }, () => t('vending.success', { count: offer.count, name: itemName(offer.output) }));
      list.append(card);
    }
    body.append(list, element('p', 'bag-description', t('vending.capacity')));
  }

  renderFire(body, container) {
    const structure = this.state.structures.find((entry) => entry.id === container.id);
    const lit = Boolean(structure?.lit);
    const overview = element('div', 'fire-overview');
    const image = element('img'); image.src = assetUrl(lit ? 'campfire_lit' : 'campfire'); image.alt = itemName('campfire');
    const copy = element('div');
    const remaining = Math.ceil(container.burn_remaining || 0);
    copy.append(element('strong', '', t(lit ? 'fire.lit' : 'fire.unlit')), element('p', '', lit ? t('fire.remaining', { time: `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}` }) : t('fire.needs')));
    overview.append(image, copy); body.append(overview);
    const fuel = element('section', 'fire-section');
    fuel.append(element('div', 'fire-section-label', t('fire.fuel', { count: container.fuel })));
    const grid = element('div', 'fuel-grid');
    if (isMobileDevice) {
      grid.setAttribute('role', 'button');
      grid.tabIndex = 0;
      grid.setAttribute('aria-label', t('fire.fuel', { count: container.fuel }));
      grid.onclick = () => { if (this.touchTransfer && !this.busy && this.touchSelection) this.touchTransferTo({ kind: 'fuel', id: container.id }, null); };
      grid.onkeydown = (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); grid.click(); } };
    }
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
    const put = element('button', 'small-button', t('fire.putWood'));
    const wood = this.playerItems().find(({ item }) => item?.kind === 'wood');
    put.disabled = this.busy || !wood || container.fuel >= 16;
    put.dataset.action = 'put-fuel';
    put.onclick = () => this.transfer(wood.endpoint, { kind: 'fuel', id: container.id }, wood.item);
    const take = element('button', 'small-button', t('fire.takeWood'));
    take.disabled = this.busy || container.fuel <= 0;
    take.onclick = () => this.quickTake({ kind: 'fuel', id: container.id }, { kind: 'wood' });
    buttons.append(put, take); fuel.append(grid, buttons); body.append(fuel);
    const igniter = element('section', 'fire-section');
    igniter.append(element('div', 'fire-section-label', t('fire.igniter')));
    const row = element('div', 'igniter-row');
    row.append(this.itemSlot(container.igniter, { kind: 'igniter', id: container.id }));
    const igniterItem = this.playerItems().find(({ item }) => item && this.catalog.igniters[item.kind] && item.uses > 0);
    const insert = element('button', 'small-button', t(container.igniter ? 'fire.takeIgniter' : 'fire.putIgniter'));
    insert.disabled = this.busy || (!container.igniter && !igniterItem);
    insert.dataset.action = 'put-igniter';
    insert.onclick = () => container.igniter ? this.quickTake({ kind: 'igniter', id: container.id }, container.igniter) : this.transfer(igniterItem.endpoint, { kind: 'igniter', id: container.id }, igniterItem.item);
    row.append(insert); igniter.append(row); body.append(igniter);
    const light = element('button', 'primary-button fire-light', t(lit ? 'fire.burning' : 'fire.light'));
    light.disabled = this.busy || lit || !container.fuel || !(container.igniter?.uses > 0);
    light.dataset.action = 'light';
    light.onclick = () => this.action('light', { id: container.id }, () => t('fire.success'));
    body.append(light, element('p', 'bag-description', t('fire.description')));
  }
}
