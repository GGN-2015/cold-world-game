import { StateSync } from './sync.js';
import { TerrainCache } from './terrain-cache.js';

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
  }

  emit(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }

  connect(credentials) {
    this.disconnect();
    this.credentials = { ...credentials };
    this.procedural = typeof Worker !== 'undefined';
    this.manual = false;
    this.everJoined = false;
    this.attempt = 0;
    this.open();
  }

  open() {
    if (this.manual) return;
    this.emit('status', { phase: this.everJoined ? 'reconnecting' : 'connecting' });
    const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`);
    this.socket = socket;
    let joined = false;
    const handshakeTimer = setTimeout(() => socket.close(), 12000);
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({ type: 'join', ...this.credentials, quiet_inputs: true, client_movement: true, player_roster: true, state_deltas: true, procedural_terrain: this.procedural ? 1 : 0 }));
    });
    let incoming = Promise.resolve();
    socket.addEventListener('message', (event) => {
      incoming = incoming.then(async () => {
        if (socket !== this.socket) return;
        let message;
        try { message = JSON.parse(event.data); } catch { return; }
        if (message.type === 'welcome') {
          clearTimeout(handshakeTimer);
          joined = true;
          this.everJoined = true;
          this.attempt = 0;
          this.terrain?.close();
          this.terrain = null;
          if (message.terrain_config) {
            this.terrain = new TerrainCache(message.terrain_config);
            await this.terrain.update(message.terrain);
            this.terrain.addEventListener('change', () => {
              if (socket === this.socket && this.ready) this.emit('state', this.terrain.decorate(this.sync.state));
            });
          }
          if (socket !== this.socket) return;
          this.ready = true;
          this.sync.reset(message.state, message.state_revision ?? 0);
          if (this.terrain) message.state = this.terrain.decorate(message.state);
          this.emit('welcome', message);
          this.emit('state', message.state);
          if (message.roster) this.emit('roster', message.roster);
          this.emit('status', { phase: 'connected' });
        } else if (message.type === 'state') {
          this.sync.reset(message.state);
          this.emit('state', message.state);
        } else if (message.type === 'delta') {
          let state;
          try {
            state = this.sync.apply(message);
          } catch {
            socket.close(1002, 'State resync required');
            return;
          }
          if (message.terrain && this.terrain) this.terrain.update(message.terrain).catch(() => { if (socket === this.socket) { this.procedural = false; socket.close(); } });
          this.emit('state', this.terrain ? this.terrain.decorate(state) : state);
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
      }).catch(() => { if (socket === this.socket) { this.procedural = false; socket.close(); } });
    });
    socket.addEventListener('close', () => {
      clearTimeout(handshakeTimer);
      if (socket !== this.socket) return;
      this.ready = false;
      this.rejectPending();
      if (this.manual) return;
      const delay = Math.min(10000, 800 * 2 ** this.attempt++);
      this.emit('status', { phase: 'reconnecting', delay });
      this.retryTimer = setTimeout(() => this.open(), delay);
    });
    socket.addEventListener('error', () => {});
  }

  send(type, payload = {}) {
    if (!this.ready || this.socket?.readyState !== WebSocket.OPEN) return false;
    if (this.socket.bufferedAmount > 65536) {
      this.socket.close();
      return false;
    }
    this.socket.send(JSON.stringify({ type, ...payload }));
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
