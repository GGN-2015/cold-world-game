export const names = {
  wood: '木材', axe: '斧头', wall: '木墙', fence: '木栅栏', floor: '木地板',
  chest: '箱子', campfire: '篝火', tree: '松树', handgun: '手枪', shotgun: '霰弹枪',
  rifle: '步枪', lighter: '打火机', matches: '火柴', gasoline: '汽油', diesel: '柴油',
  kerosene: '煤油', instant_noodles: '方便面', dumplings: '速冻饺子', wontons: '速冻馄饨',
  pork_trotters: '冷冻猪蹄', beef: '冷冻牛肉', lamb: '冷冻羊肉', sardines: '沙丁鱼罐头',
  tuna: '金枪鱼罐头', beef_balls: '撒尿牛丸', hotpot_vegetables: '速冻火锅涮菜',
  oreos: '奥利奥', compressed_biscuits: '压缩饼干',
};

export const buildings = new Set(['wall', 'fence', 'floor', 'chest', 'campfire']);
export const seasons = { spring: '春', summer: '夏', autumn: '秋', winter: '冬' };
export const itemName = (kind) => names[kind] || kind;
export const assetUrl = (kind) => `/static/assets/${kind}.png`;
export const tileAt = (value) => Math.floor(value + 0.5);
export const distance = (first, second) => Math.hypot(first.x - second.x, first.y - second.y);

export function itemDetail(item, catalog) {
  if (!item) return '空格';
  if (item.ammo != null) return `${itemName(item.kind)} · ${item.ammo} 发`;
  if (item.uses != null) return `${itemName(item.kind)} · ${item.uses} 次`;
  if (catalog?.foods?.[item.kind]) return `${itemName(item.kind)} · 饥饿 +${catalog.foods[item.kind]}`;
  return itemName(item.kind);
}

const errorMessages = {
  unauthorized: '服务器口令不正确，请检查后重试。', id_in_use: '这个名字已经在线，请换一个名字或关闭原来的窗口。',
  invalid_id: '名字应为 1–64 个字符，不能包含控制字符。', invalid_player_id: '请使用有效的玩家名字。',
  inventory_full: '背包已满，请先腾出空格。', materials_missing: '制作材料不足。',
  invalid_item: '选中建筑物品，并关闭面板后再右键放置。', downed: '失温倒地时只能放置篝火。',
  out_of_range: '距离太远，或者中间有树木、墙壁遮挡。', occupied: '这个位置已经被占用。',
  blocked: '中间有障碍物，无法放置。', adjacent_container: '箱子和篝火之间必须空出一格，包括对角线。',
  spawn_blocked: '这里需要保留出生区的通行空间。', invalid_container: '这个容器已经不存在，或尚未打开。',
  container_closed: '请先打开这个容器。', same_endpoint: '请移到另一个空格。', empty_slot: '这个格子已经空了。',
  stale_item: '物品已经变化，已同步最新背包，请重新操作。', occupied_slot: '目标格有物品，请先移走。',
  invalid_fuel: '燃料格只接受木材，最多 16 个。', invalid_igniter: '请放入仍有次数的火种，并确保火种格为空。',
  cannot_light: '点火需要木材和可用的火种，已燃烧的篝火不用再次点火。',
  pickup_cooldown: '刚丢下的物品需要等一秒才能捡回。', rate_limited: '操作过于频繁，正在重新连接。',
  world_fault: '服务器存档出现问题，世界已暂停，请检查服务端终端。',
  disconnected: '连接已断开。未确认的操作不会自动重放，请重连后查看背包。',
  timeout: '尚未收到操作确认，请以重连后的存档为准，不要重复操作。',
};

export const errorText = (error) => errorMessages[error.code] || error.message || '操作失败，请稍后重试。';
