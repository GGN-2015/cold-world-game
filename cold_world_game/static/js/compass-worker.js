import { buildingChunk } from './compass-search.js';

let config, legacy, generation = 0;
const cache = new Map();

self.onmessage = async ({ data }) => {
  const current = ++generation;
  if (data.config) {
    config = data.config;
    legacy = new Map(config.legacy.map(([horizontal, vertical, building]) => [`${horizontal},${vertical}`, building]));
    cache.clear();
    return;
  }
  try {
    const { horizontal, vertical, radius } = data;
    const bounds = [horizontal - radius, horizontal + radius, vertical - radius, vertical + radius];
    const buildings = [];
    let started = performance.now();
    for (let tileX = bounds[0]; tileX <= bounds[1]; tileX++) {
      for (let tileY = bounds[2]; tileY <= bounds[3]; tileY++) {
        const identifier = `${tileX},${tileY}`;
        let building = legacy.get(identifier) ?? cache.get(identifier);
        if (building == null) {
          building = buildingChunk(config, tileX, tileY);
          if (cache.size >= 4096) cache.delete(cache.keys().next().value);
          cache.set(identifier, building);
        }
        if (building) buildings.push([tileX, tileY]);
        if (performance.now() - started >= 4) {
          await new Promise(resolve => setTimeout(resolve, 0));
          if (current !== generation) return;
          started = performance.now();
        }
      }
    }
    if (current === generation) self.postMessage({ request: data.request, bounds, buildings });
  } catch (error) {
    self.postMessage({ request: data.request, error: String(error.message) });
  }
};
