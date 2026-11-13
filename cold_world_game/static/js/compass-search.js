import { chunkSeed, RandomStream } from './procedural.js';

export function buildingChunk(config, horizontal, vertical) {
  if (config.algorithm !== 1) throw new Error('unsupported_navigation_algorithm');
  return (horizontal === 0 && vertical === 0) || new RandomStream(chunkSeed(config.seed, horizontal, vertical)).random() >= 0.9;
}

export function nearestBuilding(region, player, camera, viewport, size) {
  const halfWidth = viewport[0] / 2 + size / 2;
  const halfHeight = viewport[1] / 2 + size / 2;
  let target = null;
  let best = Infinity;
  for (const [horizontal, vertical] of region.buildings) {
    const positionX = horizontal * size, positionY = vertical * size;
    if (Math.abs(positionX - camera.x) <= halfWidth && Math.abs(positionY - camera.y) <= halfHeight) continue;
    const offsetX = positionX - player.x, offsetY = positionY - player.y;
    if (offsetX * player.x + offsetY * player.y < 0) continue;
    const squared = offsetX * offsetX + offsetY * offsetY;
    if (squared < best || (squared === best && (horizontal < target[0] || (horizontal === target[0] && vertical < target[1])))) {
      target = [horizontal, vertical];
      best = squared;
    }
  }
  const [left, right, top, bottom] = region.bounds;
  if (player.x < left * size || player.x > right * size || player.y < top * size || player.y > bottom * size) return null;
  const outside = Math.min(player.x - (left - 1) * size, (right + 1) * size - player.x, player.y - (top - 1) * size, (bottom + 1) * size - player.y);
  return target && best < outside * outside ? { x: target[0] * size, y: target[1] * size } : null;
}
