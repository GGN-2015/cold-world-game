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
  }

  emit(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }

  connect(credentials) {
    this.disconnect();
    this.credentials = { ...credentials };
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
      socket.send(JSON.stringify({ type: 'join', ...this.credentials, quiet_inputs: true, client_movement: true, player_roster: true }));
    });
    socket.addEventListener('message', (event) => {
      if (socket !== this.socket) return;
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (message.type === 'welcome') {
        clearTimeout(handshakeTimer);
        joined = true;
        this.ready = true;
        this.everJoined = true;
        this.attempt = 0;
        this.emit('welcome', message);
        this.emit('state', message.state);
        if (message.roster) this.emit('roster', message.roster);
        this.emit('status', { phase: 'connected' });
      } else if (message.type === 'state') {
        this.emit('state', message.state);
      } else if (message.type === 'roster') {
        this.emit('roster', message);
      } else if (message.type === 'ack' || message.type === 'error') {
        const pending = this.pending.get(message.seq);
        if (pending) {
          clearTimeout(pending.timer);
          this.pending.delete(message.seq);
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
        reject({ code: 'timeout' });
        this.socket?.close();
      }, 8000);
      this.pending.set(sequence, { resolve, reject, timer });
      if (!this.send(type, { ...payload, seq: sequence })) {
        clearTimeout(timer);
        this.pending.delete(sequence);
        reject({ code: 'disconnected' });
      }
    });
  }

  rejectPending() {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject({ code: 'disconnected' });
    }
    this.pending.clear();
  }

  disconnect() {
    this.manual = true;
    this.ready = false;
    clearTimeout(this.retryTimer);
    this.rejectPending();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
