def offer(inputs, output, count=1):
    return {"inputs": inputs, "output": output, "count": count}


ROOM_MACHINES = {
    "ration_dispenser": {
        "name": ["自动口粮机", "Ration dispenser"], "chance": .018, "art": "ration", "color": "#c39551",
        "description": ["出售小份即食巧克力、节省格子的坚果和需要篝火的燕麦粥，不免费供餐。", "Sells ready-to-eat chocolate, compact nuts and fire-required oatmeal. Meals are never free."],
        "offers": {"chocolate": offer({"coin": 1}, "chocolate_bar"), "oatmeal": offer({"coin": 1}, "oatmeal"), "nuts": offer({"coin": 2}, "mixed_nuts")},
    },
    "food_dehydrator": {
        "name": ["自助食品脱水机", "Food dehydrator"], "chance": .015, "art": "dehydrator", "color": "#c47959",
        "description": ["每份鲜牛肉或沙丁鱼加1木材，分别加工成牛肉干或小鱼干；牺牲部分饱腹量，换取不用篝火的即食食品。", "Process beef or sardines with 1 wood into jerky or dried fish. Sacrifice hunger value for food that needs no fire."],
        "offers": {"jerky": offer({"beef": 1, "wood": 1}, "beef_jerky"), "dried_fish": offer({"sardines": 1, "wood": 1}, "dried_fish")},
    },
    "medical_dispenser": {
        "name": ["自动医疗柜", "Medical dispenser"], "chance": .008, "art": "medical", "color": "#8ba893",
        "description": ["4金币买暖宝宝贴，8金币买急救包，2金币买葡萄糖补给；产物仍需自己长按使用，不会在开柜时自动治疗。", "Buy a heat patch for 4 coins, first aid kit for 8, or glucose for 2. Purchases still need held use; opening the cabinet never heals."],
        "offers": {"heat_patch": offer({"coin": 4}, "heat_patch"), "first_aid": offer({"coin": 8}, "first_aid_kit"), "glucose": offer({"coin": 2}, "glucose_vial")},
    },
    "rescue_dispenser": {
        "name": ["队友救援补给机", "Rescue supply station"], "chance": .005, "art": "rescue", "color": "#bb6879",
        "description": ["8金币买一次性复苏针，12金币买一次性除颤器；需要亲自靠近倒地队友施救，不提供远程复活。", "Buy a single-use revival syringe for 8 coins or defibrillator for 12. Reach and rescue a downed teammate in person; no remote revival."],
        "offers": {"syringe": offer({"coin": 8}, "revival_syringe"), "defibrillator": offer({"coin": 12}, "defibrillator")},
    },
    "fuel_packer": {
        "name": ["木材压缩打包机", "Wood packing press"], "chance": .012, "art": "packing", "color": "#b2936e",
        "description": ["每次收1金币，将5或10木材打包成1或2份燃料补给包。只是压缩携带体积，拆包木材总量不增加。", "Pay 1 coin to pack 5 or 10 wood into 1 or 2 fuel packs. Saves carrying space, never creates extra wood."],
        "offers": {"pack_one": offer({"wood": 5, "coin": 1}, "fuel_pack"), "pack_two": offer({"wood": 10, "coin": 1}, "fuel_pack", 2)},
    },
    "ignition_dispenser": {
        "name": ["自助火种补给机", "Ignition supply station"], "chance": .015, "art": "ignition", "color": "#ba8546",
        "description": ["3金币买3次引火棒，8金币买8次火绒盒；每次点火价格与火柴相同，优势只是多次火种只占一格。", "Buy a 3-use firestarter for 3 coins or an 8-use tinder box for 8. Same cost per ignition as matches, but compact."],
        "offers": {"firestarter": offer({"coin": 3}, "firestarter"), "tinder": offer({"coin": 8}, "tinder_box")},
    },
    "building_supply_machine": {
        "name": ["营地建材售货机", "Camp construction depot"], "chance": .014, "art": "construction", "color": "#9b8962",
        "description": ["每1金币可买6木墙、6地板、3空箱子或4熄灭篝火；不如买木材自行制作划算，换取少格位、即买即放的便利。", "Spend 1 coin on 6 walls, 6 floors, 3 empty chests or 4 unlit fires. Less economical than raw wood; convenient ready-to-place supplies."],
        "offers": {"walls": offer({"coin": 1}, "wall", 6), "floors": offer({"coin": 1}, "floor", 6), "chests": offer({"coin": 1}, "chest", 3), "fires": offer({"coin": 1}, "campfire", 4)},
    },
    "salvage_machine": {
        "name": ["废材拆解回收机", "Salvage recycler"], "chance": .010, "art": "salvage", "color": "#728b80",
        "description": ["有损回收随身建材与旧枪换木材；手枪/霰弹枪/步枪分别只换3/5/10木材，剩余弹药一并报废，不退金币。", "Lossily recycle carried building items or guns into wood. Handgun/shotgun/rifle yield only 3/5/10 wood; remaining ammo is destroyed. No coin refunds."],
        "offers": {"walls": offer({"wall": 2}, "wood"), "floors": offer({"floor": 2}, "wood"), "chest": offer({"chest": 1}, "wood"), "handgun": offer({"handgun": 1}, "wood", 3), "shotgun": offer({"shotgun": 1}, "wood", 5), "rifle": offer({"rifle": 1}, "wood", 10)},
    },
    "outfitter_machine": {
        "name": ["防寒装备裁缝机", "Winter outfitter"], "chance": .006, "art": "outfitter", "color": "#8e7caa",
        "description": ["4金币加2木材买羊毛围巾，8金币加4木材买羽绒服，5金币加3木材买雪地靴；原有不叠加、选中才加速等限制不变。", "Buy a scarf for 4 coins + 2 wood, down coat for 8 + 4, or snow boots for 5 + 3. Existing non-stacking and selected-only speed rules remain."],
        "offers": {"scarf": offer({"coin": 4, "wood": 2}, "wool_scarf"), "coat": offer({"coin": 8, "wood": 4}, "down_coat"), "boots": offer({"coin": 5, "wood": 3}, "snow_boots")},
    },
    "expedition_machine": {
        "name": ["远行应急补给站", "Expedition supply station"], "chance": .002, "art": "expedition", "color": "#627fa2",
        "description": ["4金币加2木材买一次救援信标，10金币加3木材买3次裂纹回城石；必须长按使用，不提供免费传送或无限充能。", "Buy a single-use rescue beacon for 4 coins + 2 wood, or a 3-use return stone for 10 + 3. Held use required; no free teleport or recharge."],
        "offers": {"beacon": offer({"coin": 4, "wood": 2}, "rescue_beacon"), "stone": offer({"coin": 10, "wood": 3}, "return_stone")},
    },
}
