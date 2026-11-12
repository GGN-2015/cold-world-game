import { assetUrl, containers, distance, errorText, itemDetail, itemName, machines, seats, seasonName } from './catalog.js';
import { getLanguage, t } from './i18n.js';
import { isMobileDevice } from './mobile.js';
import { StoragePrediction } from './storage.js';
import { itemGuide } from './item-guide.js';

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
    this.storageView = null;
    this.inspectedId = null;
    this.guideExpanded = false;
    this.guideHotbarKey = null;
    this.transfers = new StoragePrediction(catalog);
    new ResizeObserver(([entry]) => {
      const height = Math.ceil(entry.borderBoxSize?.[0]?.blockSize ?? entry.contentRect.height);
      if (height) document.documentElement.style.setProperty('--inventory-dock-height', `${height}px`);
    }).observe(document.querySelector('.inventory-dock'));
    connection.addEventListener('command', ({ detail }) => {
      if (detail.type === 'transfer' && this.transfers.enqueue(detail.seq, detail.payload)) this.update(this.state);
    });
    connection.addEventListener('settled', ({ detail }) => {
      if (detail.type === 'error' && this.transfers.reject(detail.seq)) this.update(this.state);
    });
    connection.addEventListener('status', ({ detail }) => {
      if (detail.phase !== 'connected') {
        this.transfers.clear();
        if (this.state) this.update(this.state);
      }
    });
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
    byId('item-guide-toggle').onclick = () => this.toggleItemGuide();
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

  isOpen() { return Boolean(this.panel || this.helpOpen || this.controls.adminOpen?.()); }

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
    if (type === 'drop' && this.state?.you.inventory[payload.slot ?? this.controls.selected()]?.kind === 'axe') {
      this.toast(() => t('error.item_not_droppable'));
      return false;
    }
    this.cancelDemolition();
    this.busy = true;
    this.refreshPanel();
    try {
      await this.connection.command(type, payload);
      if (success) this.toast(success, true);
      return true;
    } catch (error) {
      this.toast(() => type === 'place' && error.code === 'out_of_range' ? t('error.placement_out_of_range') : errorText(error));
      return false;
    } finally {
      this.busy = false;
      this.refreshPanel();
    }
  }

  togglePanel(kind) {
    if (!this.connection.ready) return;
    this.controls.closeAdmin?.();
    this.controls.closeRoster?.();
    if (this.panel === kind) return this.closePanel();
    this.controls.stop();
    this.helpOpen = false;
    byId('help-overlay').hidden = true;
    this.panel = kind;
    this.inspectedId = this.state?.you.inventory[this.controls.selected()]?.id ?? null;
    this.connection.send('ui', { open: true });
    this.refreshPanel();
  }

  closePanel(send = true) {
    this.controls.stop();
    this.closedContainer = this.state?.container?.id || this.closedContainer;
    this.panel = null;
    this.guideExpanded = false;
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
    if (open) this.controls.closeAdmin?.();
    if (open) this.controls.closeRoster?.();
    this.closePanel(false);
    this.helpOpen = open;
    byId('help-overlay').hidden = !open;
    this.connection.send(open ? 'ui' : 'close', open ? { open: true } : {});
    if (open) byId('help-close').focus();
    else this.controls.focus();
  }

  reset() {
    this.cancelDemolition();
    this.transfers.reset();
    this.inspectedId = null;
    this.guideHotbarKey = null;
    this.storageView = null;
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
    if (state !== this.state) this.transfers.observe(state);
    this.state = this.transfers.project();
    state = this.state;
    const you = state.you;
    byId('season-label').textContent = t('world.seasonDay', { year: state.environment.year ?? 1, season: seasonName(state.environment.season), day: state.environment.day });
    const totalMinutes = Math.floor(state.environment.hour * 60) % 1440;
    byId('clock-label').textContent = `${String(Math.floor(totalMinutes / 60)).padStart(2, '0')}:${String(totalMinutes % 60).padStart(2, '0')}`;
    byId('ambient-label').textContent = t('world.ambient', { temperature: you.ambient_temperature.toFixed(0) });
    const excitement = byId('excitement-label');
    excitement.hidden = !(you.excitement_remaining > 0);
    excitement.textContent = you.excitement_remaining > 0 ? t('status.excited', { seconds: Math.ceil(you.excitement_remaining) }) : '';
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
    const guideHotbarKey = `${selected}:${you.inventory[selected]?.id || ''}`;
    if (this.guideHotbarKey !== guideHotbarKey) {
      this.guideHotbarKey = guideHotbarKey;
      this.inspectedId = you.inventory[selected]?.id ?? null;
    }
    byId('equipped-label').textContent = itemDetail(you.inventory[selected], this.catalog);
    if (this.touchSelection) {
      const source = this.touchSelection;
      const endpoint = source.endpoint;
      const current = ['inventory', 'backpack'].includes(endpoint.kind) ? you[endpoint.kind][endpoint.slot]
        : state.container?.id === endpoint.id ? (endpoint.kind === 'igniter' ? state.container.igniter : state.container.slots?.[endpoint.slot]) : null;
      if (current?.id !== source.item.id) this.touchSelection = null;
    }
    const hotbarSignature = JSON.stringify([you.inventory, selected, this.touchTransfer, this.touchSelection, this.panel ? this.inspectedId : null]);
    if (hotbarSignature !== this.hotbarSignature && !this.dragSource) {
      this.hotbarSignature = hotbarSignature;
      this.updateSlots(byId('hotbar'), you.inventory, (slot) => ({ kind: 'inventory', slot }), true);
    }
    if (!state.container) this.closedContainer = null;
    if (state.container && state.container.id !== this.closedContainer && !this.helpOpen && this.panel !== 'inventory') {
      this.panel = 'container';
      this.controls.closeRoster?.();
    }
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
    if (!this.state || this.isOpen()) { hint.hidden = true; return; }
    const equipped = this.state.you.inventory[this.controls.selected()];
    const melee = this.catalog.melee_weapons?.[equipped?.kind] || (equipped?.kind === 'axe' ? this.catalog.axe : null);
    const harvesting = this.catalog.harvest_tools?.[equipped?.kind] || (equipped?.kind === 'axe');
    let text = '';
    const seat = this.state.structures.find(structure => structure.id === this.state.you.seat_id);
    if (this.state.you.seated === 'mounted_gun') {
      text = t(isMobileDevice ? 'hint.turretTouch' : 'hint.turret', { ammo: seat?.ammo ?? 0 });
    } else if (target?.category === 'structure' && seats.has(target.kind)) {
      text = target.occupant && target.occupant !== this.state.you.id ? t('hint.seatOccupied', { name: itemName(target.kind), player: target.occupant }) : t(isMobileDevice ? 'hint.seatTouch' : 'hint.seat', { name: itemName(target.kind) });
    } else if (target?.kind === 'landmine') {
      text = t('hint.landmine');
    } else if (this.catalog.revival_items?.[equipped?.kind]) {
      text = t(target?.category === 'player' ? 'hint.reviveTarget' : 'hint.defibrillator', { name: target?.id || '', ...this.catalog.revival_items[equipped.kind] });
    } else if (this.catalog.explosive_weapons?.[equipped?.kind]) {
      text = t(equipped.kind === 'coin_launcher' ? 'hint.coinLauncher' : 'hint.grenade', { ...this.catalog.explosive_weapons[equipped.kind], money: this.state.you.money ?? 0 });
    } else if (this.catalog.drinks?.[equipped?.kind] && !(target?.category === 'structure' && containers.has(target.kind) && distance(this.state.you, target) <= 2)) {
      text = t('hint.drink', this.catalog.drinks[equipped.kind]);
    } else if (this.catalog.healing_items?.[equipped?.kind] && !(target?.category === 'structure' && containers.has(target.kind) && distance(this.state.you, target) <= 2)) {
      text = itemDetail(equipped, this.catalog);
    } else if (this.catalog.return_items?.[equipped?.kind] && !(target?.category === 'structure' && containers.has(target.kind) && distance(this.state.you, target) <= 2)) {
      text = t('hint.returnStaff', { duration: this.catalog.return_items[equipped.kind].duration, uses: equipped.uses });
    } else if (target?.category === 'structure') {
      const near = distance(this.state.you, target) <= (containers.has(target.kind) ? 2 : 3);
      if (containers.has(target.kind)) text = `${itemName(target.kind)} · ${t(near ? 'hint.open' : 'hint.nearer')}${harvesting && distance(this.state.you, target) <= 3 ? t(target.kind === 'piggy_bank' ? 'hint.bankDismantle' : target.kind === 'chest' ? 'hint.chestDismantle' : machines.has(target.kind) ? 'hint.vendingDismantle' : 'hint.fireDismantle') : ''}`;
      else if (harvesting) text = `${itemName(target.kind)} · ${t(target.monster_demolition ? 'hint.busy' : near ? 'hint.gather' : 'hint.nearer')}`;
    } else if (target) {
      text = `${t(['crawler', 'armored', 'stalker'].includes(target.species) ? `hint.${target.species}Monster` : target.big ? 'hint.bigMonster' : target.fast ? 'hint.fastMonster' : 'hint.smallMonster')} · ${target.hp} HP`;
      if (target.sleeping) text += t('hint.sleeping');
      else if (target.rising != null) text += t('hint.rising');
      else if (this.state.elapsed < (target.frozen_until ?? 0)) text += t('hint.frozen');
      if (this.state.elapsed < (target.burning_until ?? 0)) text += t('hint.burning');
      if (melee) {
        const attackHint = equipped.kind === 'flame_staff' ? 'hint.flameAttack' : equipped.kind === 'ice_staff' ? target.sleeping || target.rising != null ? 'hint.iceRestAttack' : 'hint.iceAttack' : 'hint.attack';
        text += distance(this.state.you, target) <= melee.range ? t(attackHint) : t(equipped.kind === 'chainsaw' ? 'hint.chainsawRange' : equipped.kind === 'flame_staff' ? 'hint.flameRange' : equipped.kind === 'ice_staff' ? 'hint.iceRange' : 'hint.axeRange', { range: melee.range });
      }
    } else if (melee) text = t(equipped.kind === 'chainsaw' ? isMobileDevice ? 'hint.chainsawSweepTouch' : 'hint.chainsawSweep' : equipped.kind === 'flame_staff' ? isMobileDevice ? 'hint.flameSweepTouch' : 'hint.flameSweep' : equipped.kind === 'ice_staff' ? isMobileDevice ? 'hint.iceSweepTouch' : 'hint.iceSweep' : isMobileDevice ? 'hint.axeSweepTouch' : 'hint.axeSweep', { range: melee.range });
    hint.textContent = text;
    hint.hidden = !text;
  }

  refreshPanel() {
    if (!this.state || !this.panel || this.dragSource) return;
    const container = this.state.container;
    const signature = JSON.stringify([this.panel, this.state.you.inventory, this.state.you.backpack, this.state.you.money, this.controls.selected(), container ? { ...container, burn_remaining: Math.ceil(container.burn_remaining || 0) } : null, this.busy, this.touchTransfer, this.touchSelection, this.inspectedId]);
    if (signature === this.panelSignature) return;
    this.panelSignature = signature;
    const body = byId('panel-body');
    byId('side-panel').hidden = false;
    byId('touch-transfer-button').setAttribute('aria-pressed', String(this.touchTransfer));
    byId('touch-transfer-drop').disabled = this.busy || !this.touchSelection || this.touchSelection.item.kind === 'axe';
    byId('touch-transfer-status').textContent = this.touchSelection ? t('touch.transferSelected', { item: itemDetail(this.touchSelection.item, this.catalog) }) : t(this.touchTransfer ? 'touch.transferPick' : 'touch.transferOff');
    byId('panel-kicker').textContent = t(this.panel === 'container' ? 'panel.shelter' : 'panel.kit');
    const key = JSON.stringify([this.panel, container?.id, container?.kind, getLanguage()]);
    if (this.storageView?.key !== key || !body.firstChild) {
      this.cancelDemolition();
      this.demolitionButton = null;
      const layout = element('div', 'storage-layout');
      const bag = element('section', 'storage-column backpack-section');
      const detail = element('section', 'storage-column detail-section');
      this.storageView = { key, detail, backpack: this.renderBackpack(bag) };
      this.storageView.guide = this.renderItemGuide(layout);
      layout.append(bag, detail);
      body.replaceChildren(layout);
      detail.append(element('h3', 'storage-heading', this.panel === 'container' ? itemName(container.kind) : t('button.craft')));
      if (this.panel === 'container' && container.kind === 'chest') {
        this.storageView.chestCount = element('div', 'container-meta');
        this.storageView.chestGrid = element('div', 'chest-grid');
        detail.append(this.storageView.chestCount, this.storageView.chestGrid);
      } else if (this.panel === 'container' && container.kind === 'piggy_bank') {
        this.storageView.bank = this.renderBank(detail, container);
      } else {
        this.storageView.content = element('div');
        detail.append(this.storageView.content);
      }
      if (this.panel === 'container') this.renderContainerDemolition(detail, container);
      this.storageView.warning = element('p', 'panel-warning', t('panel.monsterWarning'));
      detail.append(this.storageView.warning);
    }
    const view = this.storageView;
    this.updateItemGuide(view.guide);
    view.backpack.count.textContent = t('bag.slots', { count: this.state.you.backpack.filter(Boolean).length });
    view.backpack.money.textContent = t('money.balance', { count: this.state.you.money ?? 0 });
    view.backpack.hint.textContent = t(container?.kind === 'piggy_bank' ? 'bank.sharedHint' : container?.kind === 'gun_machine' ? 'gun.backpackHint' : machines.has(container?.kind) ? 'vending.backpackHint' : 'bag.transferHint');
    this.updateSlots(view.backpack.grid, this.state.you.backpack, (slot) => ({ kind: 'backpack', slot }));
    if (this.panel !== 'container') {
      byId('panel-title').textContent = t('panel.inventoryTitle');
      byId('panel-description').textContent = t('panel.inventoryDescription');
      view.content.replaceChildren();
      this.renderCraft(view.content);
    } else if (container) {
      byId('panel-title').textContent = itemName(container.kind);
      byId('panel-description').textContent = t(this.catalog.room_machines?.[container.kind] ? 'machine.description' : container.kind === 'piggy_bank' ? 'bank.description' : container.kind === 'gun_machine' ? 'gun.description' : machines.has(container.kind) ? 'vending.description' : 'panel.containerDescription');
      if (container.kind === 'chest') {
        view.chestCount.textContent = t('panel.chestSlots', { count: container.slots.filter(Boolean).length, capacity: container.slots.length });
        this.updateSlots(view.chestGrid, container.slots, (slot) => ({ kind: 'chest', id: container.id, slot }));
      } else if (container.kind === 'piggy_bank') {
        this.updateBank(view.bank, container);
      } else {
        view.content.replaceChildren();
        if (machines.has(container.kind)) {
          this.renderVending(view.content, container);
        } else this.renderFire(view.content, container);
      }
    }
    view.warning.hidden = this.panel !== 'container' || !this.state.structures.some((entry) => entry.id === container?.id && entry.monster_demolition);
    this.updateDemolitionButton();
  }

  inspectItem(item) {
    if (!this.panel) return;
    this.inspectedId = item?.id ?? null;
    this.panelSignature = '';
    this.hotbarSignature = '';
    this.update(this.state);
  }

  toggleItemGuide(open = !this.guideExpanded) {
    this.guideExpanded = open;
    byId('side-panel').classList.toggle('guide-expanded', open);
    byId('item-guide-toggle').setAttribute('aria-expanded', String(open));
  }

  renderItemGuide(body) {
    const card = element('aside', 'item-guide');
    card.id = 'item-guide';
    card.hidden = true;
    card.setAttribute('aria-live', 'polite');
    const header = element('div', 'item-guide-heading');
    const close = element('button', 'close-button item-guide-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', t('guide.hide'));
    close.onclick = () => { this.toggleItemGuide(false); byId('item-guide-toggle').focus(); };
    const icon = element('img');
    icon.alt = '';
    const heading = element('div');
    const category = element('span', 'eyebrow');
    const title = element('h4');
    title.id = 'item-guide-title';
    card.setAttribute('aria-labelledby', title.id);
    heading.append(category, title);
    header.append(icon, heading);
    const effect = element('p', 'item-guide-effect');
    const use = element('p', 'item-guide-use');
    const detail = element('p', 'item-guide-detail');
    const move = element('button', 'small-button item-guide-move');
    move.type = 'button';
    move.onclick = () => {
      const entry = this.playerItems().find(entry => entry.item?.id === this.inspectedId);
      if (entry) this.movePersonalItem(entry.endpoint, entry.item);
    };
    card.append(close, header, effect, use, detail, move);
    body.append(card);
    return { card, icon, category, title, effect, use, detail, move };
  }

  updateItemGuide(view) {
    const entry = this.playerItems().find(entry => entry.item?.id === this.inspectedId);
    view.card.hidden = !entry;
    byId('item-guide-toggle').disabled = !entry;
    this.toggleItemGuide(Boolean(entry) && this.guideExpanded);
    if (!entry) return;
    const guide = itemGuide(entry.item, this.catalog);
    view.card.dataset.itemId = entry.item.id;
    view.icon.src = assetUrl(entry.item.kind);
    view.category.textContent = guide.category;
    view.title.textContent = itemName(entry.item.kind);
    view.effect.textContent = guide.effect;
    view.use.textContent = guide.use;
    view.detail.textContent = guide.detail;
    const destination = entry.endpoint.kind === 'backpack' ? 'inventory' : 'backpack';
    view.move.textContent = t(destination === 'inventory' ? 'guide.toHotbar' : 'guide.toBackpack');
    view.move.disabled = this.busy || !this.state.you[destination].some(item => !item);
  }

  movePersonalItem(endpoint, item) {
    if (this.busy) return;
    const destination = endpoint.kind === 'backpack' ? 'inventory' : 'backpack';
    const slot = this.state.you[destination].findIndex(entry => !entry);
    if (slot < 0) return this.toast(() => t(destination === 'inventory' ? 'storage.hotbarFull' : 'storage.backpackFull'));
    return this.transfer(endpoint, { kind: destination, slot }, item);
  }

  cancelDemolition() {
    const hold = this.demolitionHold;
    if (!hold) return;
    this.demolitionHold = null;
    hold.button.classList.remove('holding');
    hold.button.style.setProperty('--demolition-progress', '0%');
    hold.button.setAttribute('aria-pressed', 'false');
    hold.button.textContent = t(hold.label);
    if (hold.pointer != null && hold.button.hasPointerCapture(hold.pointer)) hold.button.releasePointerCapture(hold.pointer);
    if (this.connection.ready) this.connection.send('dismantle_container', { pressed: false });
  }

  renderContainerDemolition(body, container) {
    const kind = this.catalog.room_machines?.[container.kind] ? 'machine' : container.kind === 'piggy_bank' ? 'bank' : container.kind === 'chest' ? 'chest' : container.kind === 'campfire' ? 'fire' : container.kind === 'match_machine' ? 'match' : container.kind === 'gun_machine' ? 'gun' : 'vending';
    const label = `${kind}.dismantle`;
    const button = element('button', 'chest-demolition', t(label));
    button.type = 'button';
    button.id = `${kind}-demolition`;
    button.setAttribute('aria-pressed', 'false');
    const hint = element('p', 'container-meta', t(`${kind}.dismantleHint`));
    hint.id = `${kind}-demolition-hint`;
    button.setAttribute('aria-describedby', hint.id);
    const start = (event, pointer = null) => {
      event.preventDefault();
      event.stopPropagation();
      if (button.disabled || this.demolitionHold || (pointer != null && event.button !== 0)) return;
      this.controls.stop();
      const slot = this.controls.selected();
      const hold = { button, pointer, container: container.id, label, epoch: this.state.movement?.epoch, slot, item: this.state.you.inventory[slot]?.id };
      this.demolitionHold = hold;
      button.classList.add('holding');
      button.setAttribute('aria-pressed', 'true');
      if (pointer != null) button.setPointerCapture(pointer);
      this.connection.command('dismantle_container', { id: container.id, pressed: true }).catch((error) => {
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
    const container = this.state?.container;
    if (!button || !containers.has(container?.kind) || this.panel !== 'container') return;
    const item = this.state.you.inventory[this.controls.selected()];
    const locked = this.state.structures.some((structure) => structure.id === container.id && structure.monster_demolition);
    const empty = !(container.slots || []).some(Boolean) && !(container.fuel > 0) && !container.igniter && !(container.balance > 0);
    button.disabled = this.busy || !empty || locked || !(this.catalog.harvest_tools?.[item?.kind] || item?.kind === 'axe') || (item?.uses != null && item.uses <= 0) || this.state.you.downed;
    const kind = this.catalog.room_machines?.[container.kind] ? 'machine' : container.kind === 'piggy_bank' ? 'bank' : container.kind === 'chest' ? 'chest' : container.kind === 'campfire' ? 'fire' : container.kind === 'match_machine' ? 'match' : container.kind === 'gun_machine' ? 'gun' : 'vending';
    byId(button.getAttribute('aria-describedby')).textContent = t(!empty ? `${kind}.emptyFirst` : locked ? 'panel.monsterWarning' : `${kind}.dismantleHint`);
    const hold = this.demolitionHold;
    if (button.disabled || (hold && (hold.epoch !== this.state.movement?.epoch || hold.slot !== this.controls.selected() || hold.item !== item?.id))) this.cancelDemolition();
    if (this.demolitionHold) {
      const progress = this.state.interaction.target === `structure:${container.id}` ? this.state.interaction.progress : 0;
      const percent = Math.min(100, Math.floor(progress / 1.5 * 100));
      button.style.setProperty('--demolition-progress', `${percent}%`);
      button.textContent = t('chest.dismantling', { percent });
    }
  }

  renderBank(body, container) {
    const card = element('div', 'bank-card');
    const icon = element('img', 'bank-icon');
    icon.src = assetUrl('piggy_bank');
    icon.alt = '';
    const balance = element('div', 'bank-balance');
    balance.id = 'bank-balance';
    balance.setAttribute('aria-live', 'polite');
    const wallet = element('div', 'container-meta');
    wallet.id = 'bank-wallet';
    const label = element('label', 'bank-amount-label', t('bank.amount'));
    const amount = element('input', 'bank-amount');
    amount.id = 'bank-amount';
    amount.type = 'number';
    amount.inputMode = 'numeric';
    amount.min = '1';
    amount.max = String(this.catalog.currency?.max_coins ?? Number.MAX_SAFE_INTEGER);
    amount.step = '1';
    amount.value = '1';
    label.htmlFor = amount.id;
    const buttons = element('div', 'bank-actions');
    const deposit = element('button', '', t('bank.deposit'));
    const withdraw = element('button', '', t('bank.withdraw'));
    deposit.id = 'bank-deposit';
    withdraw.id = 'bank-withdraw';
    const status = element('p', 'bank-status');
    status.setAttribute('role', 'status');
    const view = { balance, wallet, amount, deposit, withdraw, status };
    amount.addEventListener('input', () => this.updateBank(view, this.state.container));
    for (const [button, operation] of [[deposit, 'deposit'], [withdraw, 'withdraw']]) {
      button.type = 'button';
      button.onclick = () => this.action('bank', { id: container.id, operation, amount: Number(amount.value) });
    }
    buttons.append(deposit, withdraw);
    card.append(icon, balance, wallet, label, amount, buttons, status, element('p', 'bag-description', t('bank.sharedHint')));
    body.append(card);
    return view;
  }

  updateBank(view, container) {
    if (!container || container.kind !== 'piggy_bank') return;
    const balance = container.balance ?? 0;
    const money = this.state.you.money ?? 0;
    const amount = Number(view.amount.value);
    const maximum = this.catalog.currency?.max_coins ?? Number.MAX_SAFE_INTEGER;
    const valid = Number.isSafeInteger(amount) && amount > 0 && amount <= maximum;
    view.balance.textContent = t('bank.balance', { count: balance });
    view.wallet.textContent = t('money.balance', { count: money });
    view.amount.setAttribute('aria-invalid', String(!valid));
    view.deposit.disabled = this.busy || !valid || amount > money || balance > maximum - amount;
    view.withdraw.disabled = this.busy || !valid || amount > balance || money > maximum - amount;
    view.status.textContent = this.busy ? t('bank.pending') : !valid ? t('bank.invalidAmount') : '';
  }

  renderBackpack(body) {
    const count = element('div', 'container-meta');
    const money = element('div', 'container-meta wallet-summary');
    body.append(element('h3', 'storage-heading', t('bag.title')), count, money);
    const grid = element('div', 'bag-grid');
    const hint = element('p', 'bag-description');
    body.append(grid, hint);
    body.append(element('p', 'bag-description', t('bag.pickupHint')));
    return { count, money, grid, hint };
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

  updateSlots(grid, items, endpoint, hotbar = false) {
    items.forEach((item, slot) => {
      const node = this.itemSlot(item, endpoint(slot), hotbar, grid.children[slot]);
      if (!node.parentNode) grid.append(node);
    });
    while (grid.children.length > items.length) grid.lastChild.remove();
  }

  itemSlot(item, endpoint, hotbar = false, node = null) {
    if (!node) {
      node = element('button');
      node.type = 'button';
      if (hotbar) node.append(element('span', 'slot-key', String((endpoint.slot + 1) % 10)));
      node.addEventListener('pointerdown', (event) => { event.stopPropagation(); this.controls.stop(); });
      node.addEventListener('focus', () => {
        const { item, endpoint } = node.slotState;
        if (['inventory', 'backpack'].includes(endpoint.kind)) this.inspectItem(item, false);
      });
      node.addEventListener('dblclick', (event) => {
        const { item, endpoint } = node.slotState;
        if (!isMobileDevice && this.panel && item && !event.shiftKey && ['inventory', 'backpack'].includes(endpoint.kind)) this.movePersonalItem(endpoint, item);
      });
      node.onclick = (event) => {
        const { item, endpoint } = node.slotState;
        if (['inventory', 'backpack'].includes(endpoint.kind)) this.inspectItem(item);
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
          else if (event.shiftKey) this.movePersonalItem(endpoint, item);
        } else if (item) this.quickTake(endpoint, item);
      };
      node.addEventListener('dragstart', (event) => {
        const { item, endpoint } = node.slotState;
        if (!item || this.busy || !this.connection.ready) { event.preventDefault(); return; }
        this.controls.stop();
        this.dragSource = { endpoint, item };
        node.classList.add('dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', item.id);
        if (!this.isOpen()) this.connection.send('ui', { open: true });
      });
      node.addEventListener('dragover', (event) => {
        if (!this.dragSource || node.slotState.item || this.busy) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        node.classList.add('drop-target');
      });
      node.addEventListener('dragleave', () => node.classList.remove('drop-target'));
      node.addEventListener('drop', (event) => {
        event.preventDefault();
        node.classList.remove('drop-target');
        if (this.dragSource && !node.slotState.item) this.transfer(this.dragSource.endpoint, node.slotState.endpoint, this.dragSource.item);
      });
    }
    node.slotState = { item, endpoint };
    const selected = endpoint.kind === 'inventory' && endpoint.slot === this.controls.selected();
    const inspected = Boolean(this.panel && item && item.id === this.inspectedId);
    const signature = JSON.stringify([item, endpoint, selected, this.touchSelection?.item.id, inspected, getLanguage()]);
    if (node.slotSignature === signature) return node;
    node.slotSignature = signature;
    node.className = `item-slot${item ? '' : ' empty'}${selected ? ' selected' : ''}${inspected ? ' inspected' : ''}${item && this.touchSelection?.item.id === item.id ? ' touch-selected' : ''}`;
    node.title = itemDetail(item, this.catalog);
    node.setAttribute('aria-label', t('slot.label', { area: t(`slot.${['inventory', 'backpack'].includes(endpoint.kind) ? endpoint.kind : 'container'}`), slot: endpoint.slot == null ? '' : endpoint.slot + 1, item: itemDetail(item, this.catalog) }));
    node.dataset.kind = endpoint.kind;
    if (endpoint.slot != null) node.dataset.slot = endpoint.slot;
    node.draggable = Boolean(item) && !isMobileDevice;
    let image = node.querySelector('img');
    if (item) {
      if (!image) { image = element('img'); image.draggable = false; node.append(image); }
      if (image.getAttribute('src') !== assetUrl(item.kind)) image.src = assetUrl(item.kind);
      image.alt = itemName(item.kind);
    } else image?.remove();
    let count = node.querySelector('.item-count');
    const value = item?.ammo ?? item?.uses;
    if (value != null) {
      if (!count) { count = element('span', 'item-count'); node.append(count); }
      count.textContent = String(value);
    } else count?.remove();
    return node;
  }

  transfer(source, destination, item) {
    if (this.busy || !this.connection.ready) return Promise.resolve(false);
    if (destination.kind === 'ground' && item.kind === 'axe') {
      this.toast(() => t('error.item_not_droppable'));
      return Promise.resolve(false);
    }
    this.cancelDemolition();
    this.dragSource = null;
    if (item.kind === 'coin' && ['inventory', 'backpack'].includes(destination.kind)) destination = { kind: 'wallet' };
    const payload = { from: source, to: destination };
    if (source.kind !== 'fuel') payload.item_id = item.id;
    return this.connection.command('transfer', payload).then(() => true).catch((error) => {
      this.toast(() => errorText(error));
      return false;
    });
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
    if (machines.has(container.kind)) return this.toast(() => t('vending.useOffers'));
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
    const offers = this.catalog.machine_offers?.[container.kind] || (container.kind === 'vending_machine' ? this.catalog.vending_offers : {}) || {};
    if (this.catalog.room_machines?.[container.kind]) body.append(element('p', 'craft-description', t(`guide.effect.${container.kind}`)));
    for (const [identifier, offer] of Object.entries(offers)) {
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
    body.append(list, element('p', 'bag-description', t(this.catalog.room_machines?.[container.kind] ? 'machine.capacity' : container.kind === 'gun_machine' ? 'gun.capacity' : 'vending.capacity', { item: itemName(container.kind === 'match_machine' ? 'matches' : 'cola') })));
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
