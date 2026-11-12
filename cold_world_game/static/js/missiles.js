const directions = ['e', 'se', 's', 'sw', 'w', 'nw', 'n', 'ne'];

export function homingPosition(projectile, elapsed, settings, target = null) {
  const age = Math.max(0, elapsed - projectile.spawned_at);
  const directionX = projectile.velocity_x / settings.speed;
  const directionY = projectile.velocity_y / settings.speed;
  const reach = settings.launch_distance;
  let horizontal, vertical, tangentX = directionX, tangentY = directionY;
  if (age < settings.launch_duration) {
    const phase = age / settings.launch_duration;
    horizontal = projectile.origin_x + directionX * reach * phase;
    vertical = projectile.origin_y + directionY * reach * phase;
  } else {
    const targetX = target?.x ?? projectile.target_x, targetY = target?.y ?? projectile.target_y;
    const startX = projectile.origin_x + directionX * reach, startY = projectile.origin_y + directionY * reach;
    const bend = Math.min(4, Math.hypot(targetX - startX, targetY - startY) / 2);
    const controlX = startX + directionX * bend, controlY = startY + directionY * bend;
    const phase = Math.min(1, (age - settings.launch_duration) / (projectile.detonates_at - projectile.spawned_at - settings.launch_duration));
    const inverse = 1 - phase;
    horizontal = inverse * inverse * startX + 2 * inverse * phase * controlX + phase * phase * targetX;
    vertical = inverse * inverse * startY + 2 * inverse * phase * controlY + phase * phase * targetY;
    tangentX = inverse * (controlX - startX) + phase * (targetX - controlX);
    tangentY = inverse * (controlY - startY) + phase * (targetY - controlY);
  }
  const index = (Math.round(Math.atan2(tangentY, tangentX) / (Math.PI / 4)) + 8) % 8;
  return { x: horizontal, y: vertical, asset: `missile_${directions[index]}` };
}
