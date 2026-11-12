import { StateSync } from './sync.js';
import { TerrainCache } from './terrain-cache.js';
import { WireDecoder } from './wire.js';

export class GameConnection extends EventTarget {
  constructor() {
    super();
    this.socket = null;
    this.credentials = null;
    this.sequence = 0;
    this.pending = new Map();
    this.attempt = 0;
    this.ready = false;
    this.manual = true;
    this.everJoined = false;
    this.retryTimer = null;
    this.sync = new StateSync();
    this.inputBaseline = new Map();
    this.inputRefresh = 0;
    this.presentationEvents = new Map();
  }

  emit(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }

  connect(credentials) {
    this.disconnect();
    this.credentials = { ...credentials };
    this.procedural = typeof Worker !== 'undefined';
    this.compact = true;
    this.manual = false;
    this.everJoined = false;
    this.attempt = 0;
    this.open();
  }

  open() {
    if (this.manual) return;
    this.emit('status', { phase: this.everJoined ? 'reconnecting' : 'connecting' });
    const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`);
    socket.binaryType = 'arraybuffer';
    this.socket = socket;
    let joined = false;
    const handshakeTimer = setTimeout(() => socket.close(), 12000);
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({ type: 'join', ...this.credentials, quiet_inputs: true, client_movement: true, player_roster: true, state_deltas: true, procedural_terrain: this.procedural ? 1 : 0, compact_state: this.compact ? 1 : 0 }));
    });
    let incoming = Promise.resolve();
    socket.addEventListener('message', (event) => {
      incoming = incoming.then(async () => {
        if (socket !== this.socket) return;
        let message;
        try {
          message = typeof event.data === 'string' ? JSON.parse(event.data) : this.wire.decode(event.data);
        } catch {
          this.compact = false;
          socket.close(1002, 'State decoding failed');
          return;
        }
        if (message.type === 'welcome') {
          clearTimeout(handshakeTimer);
          joined = true;
          this.everJoined = true;
          this.attempt = 0;
          this.wire = message.wire_config ? new WireDecoder(message.wire_config, message.roster) : null;
          this.inputBaseline.clear();
          this.inputRefresh = 0;
          this.terrain?.close();
          this.terrain = null;
          if (message.terrain_config) {
            this.terrain = new TerrainCache(message.terrain_config);
            await this.terrain.update(message.terrain);
            this.terrain.addEventListener('change', () => {
              if (socket === this.socket && this.ready) this.present(this.sync.state);
            });
          }
          if (socket !== this.socket) return;
          this.ready = true;
          this.sync.reset(message.state, message.state_revision ?? 0);
          if (this.wire) message.state = this.wire.view(message.state);
          if (this.terrain) message.state = this.terrain.decorate(message.state);
          this.emit('welcome', message);
          this.present(this.sync.state);
          if (message.roster) this.emit('roster', message.roster);
          this.emit('status', { phase: 'connected' });
        } else if (message.type === 'state') {
          this.sync.reset(message.state);
          this.present(message.state);
        } else if (message.type === 'delta') {
          let state;
          try {
            state = this.sync.apply(message);
          } catch {
            socket.close(1002, 'State resync required');
            return;
          }
          if (message.terrain && this.terrain) this.terrain.update(message.terrain).catch(() => { if (socket === this.socket) { this.procedural = false; socket.close(); } });
          this.present(state);
        } else if (message.type === 'roster') {
          this.emit('roster', message);
        } else if (message.type === 'ack' || message.type === 'error') {
          const pending = this.pending.get(message.seq);
          if (pending) {
            clearTimeout(pending.timer);
            this.pending.delete(message.seq);
            this.emit('settled', message);
            if (message.type === 'ack') pending.resolve(message.result);
            else pending.reject(message);
          } else if (message.type === 'error') {
            if (!joined && (message.code !== 'id_in_use' || !this.everJoined)) {
              this.manual = true;
              this.emit('loginerror', message);
            } else if (joined) this.emit('commanderror', message);
            if (message.seq == null) socket.close(1000);
          }
        }
      }).catch(() => { if (socket === this.socket) { this.compact = false; this.procedural = false; socket.close(); } });
    });
    socket.addEventListener('close', () => {
      clearTimeout(handshakeTimer);
      if (socket !== this.socket) return;
      this.ready = false;
      this.clearPresentation();
      this.rejectPending();
      if (this.manual) return;
      const delay = Math.min(10000, 800 * 2 ** this.attempt++);
      this.emit('status', { phase: 'reconnecting', delay });
      this.retryTimer = setTimeout(() => this.open(), delay);
    });
    socket.addEventListener('error', () => {});
  }

  present(state) {
    this.presentationState = state;
    for (const event of state.events || []) this.presentationEvents.set(event.id, event);
    while (this.presentationEvents.size > 256) this.presentationEvents.delete(this.presentationEvents.keys().next().value);
    if (this.presentationFrame != null) return;
    this.presentationFrame = requestAnimationFrame(() => {
      this.presentationFrame = null;
      if (!this.ready || !this.presentationState) return;
      let state = this.presentationState;
      const events = [...this.presentationEvents.values()].filter((event) => state.elapsed - event.time <= 1.5);
      this.presentationEvents.clear();
      this.presentationState = null;
      if (this.wire) state = this.wire.view(state);
      if (this.terrain) state = this.terrain.decorate(state);
      this.emit('state', { ...state, events });
    });
  }

  clearPresentation() {
    if (this.presentationFrame != null) cancelAnimationFrame(this.presentationFrame);
    this.presentationFrame = null;
    this.presentationState = null;
    this.presentationEvents.clear();
  }

  send(type, payload = {}) {
    if (!this.ready || this.socket?.readyState !== WebSocket.OPEN) return false;
    if (this.socket.bufferedAmount > 65536) {
      this.socket.close();
      return false;
    }
    if (type === 'input' && this.wire) {
      const now = performance.now();
      const refresh = now - this.inputRefresh >= 250;
      const changes = {};
      for (const [field, value] of Object.entries(payload)) {
        const signature = JSON.stringify(value);
        if (refresh || this.inputBaseline.get(field) !== signature) changes[field] = value;
        this.inputBaseline.set(field, signature);
      }
      if (['position', 'velocity', 'movement_epoch'].some((field) => field in changes) && 'position' in payload) {
        changes.position = payload.position;
        changes.velocity = payload.velocity;
        changes.movement_epoch = payload.movement_epoch;
      }
      if (!refresh && !Object.keys(changes).length) return true;
      if (refresh) this.inputRefresh = now;
      this.socket.send(JSON.stringify({ type, ...changes }));
    } else {
      this.inputBaseline.clear();
      this.socket.send(JSON.stringify({ type, ...payload }));
    }
    return true;
  }

  command(type, payload = {}) {
    if (!this.ready) return Promise.reject({ code: 'disconnected' });
    const sequence = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(sequence);
        this.emit('settled', { type: 'error', seq: sequence, code: 'timeout' });
        reject({ code: 'timeout' });
        this.socket?.close();
      }, 8000);
      this.pending.set(sequence, { resolve, reject, timer });
      if (!this.send(type, { ...payload, seq: sequence })) {
        clearTimeout(timer);
        this.pending.delete(sequence);
        reject({ code: 'disconnected' });
      } else {
        this.emit('command', { type, payload, seq: sequence });
      }
    });
  }

  rejectPending() {
    for (const [sequence, pending] of this.pending) {
      clearTimeout(pending.timer);
      this.emit('settled', { type: 'error', seq: sequence, code: 'disconnected' });
      pending.reject({ code: 'disconnected' });
    }
    this.pending.clear();
  }

  disconnect() {
    this.manual = true;
    this.ready = false;
    this.clearPresentation();
    this.terrain?.close();
    this.terrain = null;
    clearTimeout(this.retryTimer);
    this.rejectPending();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
