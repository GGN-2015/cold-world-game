import { nearestBuilding } from './compass-search.js';

export class GameCompass {
  constructor() {
    this.sequence = 0;
    this.root = document.documentElement;
  }

  reset() {
    clearTimeout(this.timer);
    this.worker?.terminate();
    this.worker = null;
    this.pending = null;
    this.region = null;
    this.config = null;
    this.lastUpdate = -Infinity;
    this.retryAt = 0;
    this.ready = false;
    this.root.classList.remove('compass-ready');
    this.root.style.removeProperty('--compass-angle');
  }

  configure(config) {
    this.reset();
    if (!config) return;
    this.config = config;
  }

  fail() {
    const config = this.config;
    this.reset();
    this.config = config;
    this.retryAt = performance.now() + 5000;
  }

  start() {
    try {
      this.worker = new Worker(new URL('./compass-worker.js', import.meta.url), { type: 'module' });
      this.worker.onmessage = ({ data }) => {
        if (data.request !== this.pending?.request) return;
        clearTimeout(this.timer);
        this.pending = null;
        if (data.error) { this.fail(); return; }
        this.region = data;
        this.lastUpdate = -Infinity;
      };
      this.worker.onerror = event => { event.preventDefault(); this.fail(); };
      this.worker.onmessageerror = () => this.fail();
      this.worker.postMessage({ config: this.config });
    } catch { this.fail(); }
  }

  update(now, active, player, camera, viewport) {
    if (!active || !this.config || document.hidden) {
      if (this.ready) this.root.classList.remove('compass-ready');
      this.ready = false;
      return;
    }
    if (now < this.retryAt || now - this.lastUpdate < 100) return;
    this.lastUpdate = now;
    if (!this.worker) this.start();
    if (!this.worker) return;
    const size = this.config.size;
    const target = this.region && nearestBuilding(this.region, player, camera, viewport, size);
    if (target) {
      const angle = Math.atan2(target.y - player.y, target.x - player.x) + Math.PI / 2;
      if (this.ready) this.angle += Math.atan2(Math.sin(angle - this.angle), Math.cos(angle - this.angle));
      else this.angle = angle;
      this.root.style.setProperty('--compass-angle', `${this.angle}rad`);
      this.root.classList.add('compass-ready');
      this.ready = true;
      return;
    }
    this.root.classList.remove('compass-ready');
    this.ready = false;
    if (this.pending) return;
    const horizontal = Math.floor((player.x + size / 2) / size), vertical = Math.floor((player.y + size / 2) / size);
    let radius = Math.max(4, Math.ceil(Math.max(...viewport) / (2 * size)) + 2);
    if (this.region) {
      const [left, right, top, bottom] = this.region.bounds;
      if (horizontal === (left + right) / 2 && vertical === (top + bottom) / 2) radius = Math.max(radius, right - left);
    }
    this.pending = { request: ++this.sequence, horizontal, vertical, radius };
    this.worker.postMessage(this.pending);
    this.timer = setTimeout(() => this.fail(), 10000);
  }
}
