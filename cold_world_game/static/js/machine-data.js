export const roomMachineKinds = [
  "ration_dispenser",
  "food_dehydrator",
  "medical_dispenser",
  "rescue_dispenser",
  "fuel_packer",
  "ignition_dispenser",
  "building_supply_machine",
  "salvage_machine",
  "outfitter_machine",
  "expedition_machine"
];

export const roomMachineMessages = {
  "machine.dismantle": [
    "长按拆除机器 · 1.5 秒",
    "Hold to dismantle machine · 1.5 s"
  ],
  "machine.dismantleHint": [
    "选中斧头并在此持续按住1.5秒；松开取消。成功掉落同一种机器，可搬走重新放置，不能退回曾经支付的材料。",
    "Equip an axe and hold here for 1.5 s; release to cancel. Drops the same machine for relocation, never refunds past payments."
  ],
  "machine.description": [
    "有偿兑换与加工，不自动生成物资、不产生利息。每次都重新支付全部材料，产物保留原本的使用限制。",
    "Paid exchanges and processing only: no passive production or interest. Every exchange consumes its full cost; normal item-use restrictions remain."
  ],
  "machine.capacity": [
    "产物先入背包，再入物品栏；本次消耗的材料格可用于接收产物。必须装得下全部产物，空间不足或结算失败整次回退，不扣款、不吞材料；后台提交完整快照。回收会销毁整件输入物品及其剩余弹药。",
    "Results fill backpack then hotbar; consumed ingredient slots may hold outputs. All results must fit. Insufficient space or operation failure rolls back payment and materials in full; complete snapshots are saved in the background. Recycling destroys the entire input and its remaining ammo."
  ],
  "item.ration_dispenser": [
    "自动口粮机",
    "Ration dispenser"
  ],
  "guide.effect.ration_dispenser": [
    "出售小份即食巧克力、节省格子的坚果和需要篝火的燕麦粥，不免费供餐。",
    "Sells ready-to-eat chocolate, compact nuts and fire-required oatmeal. Meals are never free."
  ],
  "item.food_dehydrator": [
    "自助食品脱水机",
    "Food dehydrator"
  ],
  "guide.effect.food_dehydrator": [
    "每份鲜牛肉或沙丁鱼加1木材，分别加工成牛肉干或小鱼干；牺牲部分饱腹量，换取不用篝火的即食食品。",
    "Process beef or sardines with 1 wood into jerky or dried fish. Sacrifice hunger value for food that needs no fire."
  ],
  "item.medical_dispenser": [
    "自动医疗柜",
    "Medical dispenser"
  ],
  "guide.effect.medical_dispenser": [
    "4金币买暖宝宝贴，8金币买急救包，2金币买葡萄糖补给；产物仍需自己长按使用，不会在开柜时自动治疗。",
    "Buy a heat patch for 4 coins, first aid kit for 8, or glucose for 2. Purchases still need held use; opening the cabinet never heals."
  ],
  "item.rescue_dispenser": [
    "队友救援补给机",
    "Rescue supply station"
  ],
  "guide.effect.rescue_dispenser": [
    "8金币买一次性复苏针，12金币买一次性除颤器；需要亲自靠近倒地队友施救，不提供远程复活。",
    "Buy a single-use revival syringe for 8 coins or defibrillator for 12. Reach and rescue a downed teammate in person; no remote revival."
  ],
  "item.fuel_packer": [
    "木材压缩打包机",
    "Wood packing press"
  ],
  "guide.effect.fuel_packer": [
    "每次收1金币，将5或10木材打包成1或2份燃料补给包。只是压缩携带体积，拆包木材总量不增加。",
    "Pay 1 coin to pack 5 or 10 wood into 1 or 2 fuel packs. Saves carrying space, never creates extra wood."
  ],
  "item.ignition_dispenser": [
    "自助火种补给机",
    "Ignition supply station"
  ],
  "guide.effect.ignition_dispenser": [
    "3金币买3次引火棒，8金币买8次火绒盒；每次点火价格与火柴相同，优势只是多次火种只占一格。",
    "Buy a 3-use firestarter for 3 coins or an 8-use tinder box for 8. Same cost per ignition as matches, but compact."
  ],
  "item.building_supply_machine": [
    "营地建材售货机",
    "Camp construction depot"
  ],
  "guide.effect.building_supply_machine": [
    "每1金币可买6木墙、6地板、3空箱子或4熄灭篝火；不如买木材自行制作划算，换取少格位、即买即放的便利。",
    "Spend 1 coin on 6 walls, 6 floors, 3 empty chests or 4 unlit fires. Less economical than raw wood; convenient ready-to-place supplies."
  ],
  "item.salvage_machine": [
    "废材拆解回收机",
    "Salvage recycler"
  ],
  "guide.effect.salvage_machine": [
    "有损回收随身建材与旧枪换木材；手枪/霰弹枪/步枪分别只换3/5/10木材，剩余弹药一并报废，不退金币。",
    "Lossily recycle carried building items or guns into wood. Handgun/shotgun/rifle yield only 3/5/10 wood; remaining ammo is destroyed. No coin refunds."
  ],
  "item.outfitter_machine": [
    "防寒装备裁缝机",
    "Winter outfitter"
  ],
  "guide.effect.outfitter_machine": [
    "4金币加2木材买羊毛围巾，8金币加4木材买羽绒服，5金币加3木材买雪地靴；原有不叠加、选中才加速等限制不变。",
    "Buy a scarf for 4 coins + 2 wood, down coat for 8 + 4, or snow boots for 5 + 3. Existing non-stacking and selected-only speed rules remain."
  ],
  "item.expedition_machine": [
    "远行应急补给站",
    "Expedition supply station"
  ],
  "guide.effect.expedition_machine": [
    "4金币加2木材买一次救援信标，10金币加3木材买3次裂纹回城石；必须长按使用，不提供免费传送或无限充能。",
    "Buy a single-use rescue beacon for 4 coins + 2 wood, or a 3-use return stone for 10 + 3. Held use required; no free teleport or recharge."
  ]
};
