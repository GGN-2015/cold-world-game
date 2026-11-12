const utf8 = new TextDecoder('utf-8', { fatal: true });

function unpack(buffer) {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  let offset = 0;
  const number = (length, getter) => {
    const value = view[getter](offset);
    offset += length;
    return value;
  };
  const text = (length) => {
    if (offset + length > bytes.length) throw new Error('truncated_wire_string');
    const value = utf8.decode(bytes.subarray(offset, offset + length));
    offset += length;
    return value;
  };
  const array = (length) => {
    if (length > bytes.length - offset) throw new Error('invalid_wire_array');
    const value = new Array(length);
    for (let index = 0; index < length; index++) value[index] = read();
    return value;
  };
  const map = (length) => {
    if (length * 2 > bytes.length - offset) throw new Error('invalid_wire_map');
    const value = new Map();
    for (let index = 0; index < length; index++) {
      const key = read();
      if (value.has(key)) throw new Error('duplicate_wire_field');
      value.set(key, read());
    }
    return value;
  };
  const integer64 = (signed) => {
    const value = number(8, signed ? 'getBigInt64' : 'getBigUint64');
    if (value > BigInt(Number.MAX_SAFE_INTEGER) || value < BigInt(Number.MIN_SAFE_INTEGER)) throw new Error('unsafe_wire_integer');
    return Number(value);
  };
  const read = () => {
    const tag = number(1, 'getUint8');
    if (tag < 0x80) return tag;
    if (tag >= 0xe0) return tag - 256;
    if (tag >= 0xa0 && tag <= 0xbf) return text(tag & 31);
    if (tag >= 0x90 && tag <= 0x9f) return array(tag & 15);
    if (tag >= 0x80 && tag <= 0x8f) return map(tag & 15);
    switch (tag) {
      case 0xc0: return null;
      case 0xc2: return false;
      case 0xc3: return true;
      case 0xca: return number(4, 'getFloat32');
      case 0xcb: return number(8, 'getFloat64');
      case 0xcc: return number(1, 'getUint8');
      case 0xcd: return number(2, 'getUint16');
      case 0xce: return number(4, 'getUint32');
      case 0xcf: return integer64(false);
      case 0xd0: return number(1, 'getInt8');
      case 0xd1: return number(2, 'getInt16');
      case 0xd2: return number(4, 'getInt32');
      case 0xd3: return integer64(true);
      case 0xd9: return text(number(1, 'getUint8'));
      case 0xda: return text(number(2, 'getUint16'));
      case 0xdb: return text(number(4, 'getUint32'));
      case 0xdc: return array(number(2, 'getUint16'));
      case 0xdd: return array(number(4, 'getUint32'));
      case 0xde: return map(number(2, 'getUint16'));
      case 0xdf: return map(number(4, 'getUint32'));
      default: throw new Error('unsupported_wire_tag');
    }
  };
  const result = read();
  if (offset !== bytes.length) throw new Error('trailing_wire_bytes');
  return result;
}

export class WireDecoder {
  constructor(config, roster = null) {
    if (config.version !== 1 || !Array.isArray(config.fields)) throw new Error('unsupported_wire_version');
    this.fields = config.fields;
    this.referenceFields = new Set(config.references);
    this.scales = config.scales;
    this.references = [];
    this.roster = new Map((roster?.players || []).map((player) => [player.id, player]));
    this.rosterRevision = 0;
  }

  decode(buffer) {
    const [version, reset, added, payload] = unpack(buffer);
    if (version !== 1 || !Array.isArray(added) || added.some((value) => typeof value !== 'string')) throw new Error('invalid_wire_dictionary');
    if (reset) this.references = [];
    for (const value of added) this.references.push(value);
    const restore = (value, field = null) => {
      if (value instanceof Map) {
        const result = {};
        for (const [code, entry] of value) {
          const key = typeof code === 'number' ? this.fields[code] : code;
          if (typeof key !== 'string' || ['__proto__', 'constructor', 'prototype'].includes(key)) throw new Error('unknown_wire_field');
          result[key] = restore(entry, key);
        }
        return result;
      }
      if (Array.isArray(value)) return value.map((entry) => restore(entry, field));
      if (typeof value === 'number' && value < 0 && this.referenceFields.has(field)) {
        const identifier = this.references[-value - 1];
        if (identifier == null) throw new Error('missing_wire_reference');
        return identifier;
      }
      if (typeof value === 'number' && this.scales[field]) return value / this.scales[field];
      return value;
    };
    const message = restore(payload);
    if (message.type === 'roster_delta') {
      if (message.base !== this.rosterRevision || message.revision !== this.rosterRevision + 1) throw new Error('roster_revision_mismatch');
      const roster = new Map(this.roster);
      for (const identifier of message.remove) roster.delete(identifier);
      for (const entry of message.entries) roster.set(entry.id, { ...roster.get(entry.id), ...entry.fields });
      const order = message.order || [...roster.keys()];
      if (order.length !== roster.size || new Set(order).size !== order.length || order.some((identifier) => !roster.has(identifier))) throw new Error('invalid_roster_order');
      this.roster = new Map(order.map((identifier) => [identifier, roster.get(identifier)]));
      this.rosterRevision = message.revision;
      return { type: 'roster', server_time: message.server_time, players: [...this.roster.values()] };
    }
    return message;
  }

  view(state) {
    const actors = new Map(state.players.map((player) => [player.id, player]));
    actors.set(state.you.id, state.you);
    const projectiles = state.projectiles.map((projectile) => {
      if (!projectile.trajectory) return projectile;
      const age = Math.max(0, state.elapsed - projectile.flight_at);
      const horizontal = projectile.x + projectile.velocity_x * age;
      const vertical = projectile.y + projectile.velocity_y * age;
      const center = actors.get(projectile.range_player);
      const centerX = center?.x ?? projectile.range_x ?? projectile.origin_x ?? horizontal;
      const centerY = center?.y ?? projectile.range_y ?? projectile.origin_y ?? vertical;
      const radius = projectile.range_radius ?? 32;
      const speed = Math.hypot(projectile.velocity_x, projectile.velocity_y);
      const offsetX = horizontal - centerX, offsetY = vertical - centerY;
      const projection = speed ? (offsetX * projectile.velocity_x + offsetY * projectile.velocity_y) / speed : 0;
      const distanceSquared = offsetX * offsetX + offsetY * offsetY;
      const remaining = distanceSquared > radius * radius ? 0 : Math.max(0, -projection + Math.sqrt(Math.max(0, projection * projection + radius * radius - distanceSquared)));
      return { ...projectile, x: horizontal, y: vertical, remaining, range_x: centerX, range_y: centerY };
    });
    return { ...state, projectiles };
  }
}
