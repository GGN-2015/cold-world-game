export const isMobileDevice = Boolean(navigator.userAgentData?.mobile
  || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
  || (navigator.maxTouchPoints > 0 && matchMedia('(pointer: coarse)').matches));

document.documentElement.classList.toggle('mobile-device', isMobileDevice);

export class MobileControls {
  constructor(canvas, controls) {
    this.controls = controls;
    this.pointers = new Map();
    this.enabled = false;
    if (!isMobileDevice) return;
    this.root = document.getElementById('touch-controls');
    this.bindStick(document.getElementById('touch-move'), controls.move);
    this.bindStick(document.getElementById('touch-aim'), controls.aim);
    this.bindHold(document.getElementById('touch-use'), false);
    this.bindHold(document.getElementById('touch-dismantle'), true);
    for (const [identifier, action] of [['touch-place', controls.place], ['touch-drop', controls.drop]]) {
      const button = document.getElementById(identifier);
      button.onclick = () => { if (controls.canPlay()) action(); };
    }
    let canvasPressed = false;
    this.bindPointer(canvas, (event) => {
      controls.aimPoint(event.clientX, event.clientY);
      if (!canvasPressed && !this.holdOwner && controls.useAtPoint?.()) {
        this.holdOwner = canvas;
        canvasPressed = true;
        controls.use(true, false);
      }
    }, () => {
      if (canvasPressed) {
        this.holdOwner = null;
        canvasPressed = false;
        controls.use(false, false);
      }
    });
    this.root.addEventListener('contextmenu', (event) => event.preventDefault());
    const resize = () => this.resize();
    window.addEventListener('resize', resize);
    window.visualViewport?.addEventListener('resize', resize);
    window.addEventListener('orientationchange', () => { controls.cancel(); requestAnimationFrame(resize); });
    new ResizeObserver(() => {
      const bounds = document.querySelector('.game-header').getBoundingClientRect();
      document.documentElement.style.setProperty('--mobile-header-bottom', `${bounds.bottom + 6}px`);
    }).observe(document.querySelector('.game-header'));
    new ResizeObserver(() => {
      const height = document.querySelector('.inventory-dock').getBoundingClientRect().height;
      if (height) document.documentElement.style.setProperty('--touch-dock-height', `${Math.ceil(height) + 14}px`);
    }).observe(document.querySelector('.inventory-dock'));
    this.resize();
    this.sync();
  }

  resize() {
    const height = Math.round(window.visualViewport?.height || innerHeight);
    const size = `${innerWidth}:${height}`;
    if (this.size && size !== this.size) this.controls.cancel();
    this.size = size;
    document.documentElement.style.setProperty('--mobile-viewport-height', `${height}px`);
  }

  sync() {
    if (!isMobileDevice) return;
    const enabled = this.controls.canPlay();
    if (this.enabled && !enabled) this.controls.cancel();
    this.enabled = enabled;
    this.root.hidden = !enabled;
  }

  reset() {
    const active = [...this.pointers];
    this.pointers.clear();
    for (const [identifier, entry] of active) {
      entry.finish();
      if (entry.node.hasPointerCapture(identifier)) entry.node.releasePointerCapture(identifier);
    }
  }

  bindPointer(node, update, finish) {
    let pointer = null;
    const release = (event) => {
      if (pointer !== event.pointerId) return;
      const entry = this.pointers.get(pointer);
      this.pointers.delete(pointer);
      pointer = null;
      entry?.finish();
      if (node.hasPointerCapture(event.pointerId)) node.releasePointerCapture(event.pointerId);
    };
    node.addEventListener('pointerdown', (event) => {
      if (!this.controls.canPlay() || pointer !== null || event.button !== 0) return;
      event.preventDefault();
      pointer = event.pointerId;
      this.pointers.set(pointer, { node, finish: () => { pointer = null; node.classList.remove('active'); finish(); } });
      node.setPointerCapture(pointer);
      node.classList.add('active');
      update(event);
    });
    node.addEventListener('pointermove', (event) => {
      if (pointer !== event.pointerId) return;
      event.preventDefault();
      update(event);
    });
    for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) node.addEventListener(name, release);
  }

  bindStick(node, action) {
    const thumb = node.querySelector('.touch-thumb');
    this.bindPointer(node, (event) => {
      const bounds = node.getBoundingClientRect();
      const radius = bounds.width * 0.34;
      const horizontal = (event.clientX - bounds.left - bounds.width / 2) / radius;
      const vertical = (event.clientY - bounds.top - bounds.height / 2) / radius;
      const magnitude = Math.hypot(horizontal, vertical);
      const divisor = Math.max(1, magnitude);
      thumb.style.transform = `translate(${horizontal / divisor * radius}px, ${vertical / divisor * radius}px)`;
      if (magnitude < 0.12) action({ x: 0, y: 0 });
      else action({ x: horizontal / divisor, y: vertical / divisor });
    }, () => {
      thumb.style.transform = '';
      if (node.id === 'touch-move') action({ x: 0, y: 0 });
    });
  }

  bindHold(node, shift) {
    let pressed = false;
    this.bindPointer(node, () => {
      if (!pressed && !this.holdOwner) { this.holdOwner = node; pressed = true; this.controls.use(true, shift); }
    }, () => {
      if (pressed) { this.holdOwner = null; pressed = false; this.controls.use(false, shift); }
    });
  }
}
