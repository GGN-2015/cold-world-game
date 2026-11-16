"""Independent drops for new ordinary natural chests."""

# A row is (item, per-chest probability, possible quantities on success).
CHEST_LOOT = {
    "weapon": (
        ("handgun", .14, (1,)), ("rust_revolver", .01, (1,)),
        ("shotgun", .04, (1,)), ("rifle", .02, (1,)), ("hunting_rifle", .026, (1,)),
        ("crowbar", .037, (1,)), ("machete", .031, (1,)), ("snow_shovel", .015, (1,)),
        ("frost_spear", .024, (1,)), ("ice_staff", .039, (1,)), ("flame_staff", .039, (1,)),
        ("chain_chainsaw", .075, (1,)), ("flamethrower", .075, (1,)),
        ("grenade", .02, (1,)), ("cluster_charge", .004, (1,)), ("frost_bomb", .006, (1,)),
        ("fireball_scroll", .075, (1,)), ("freeze_scroll", .075, (1,)),
        ("fire_bottle", .008, (1,)), ("flare_bomb", .01, (1,)),
    ),
    "consumable": (
        ("light_ammo", .16, (1,)), ("rifle_ammo", .09, (1,)), ("shotgun_ammo", .09, (1,)),
        ("wood", .50, (1, 2, 3, 4, 5)), ("spare_part", .35, (1, 2, 3)),
        ("papyrus", .30625, (1,) * 18 + (2,) * 38 + (3,) * 41 + (4,) * 3),
        ("lighter", .04, (1,)), ("matches", .04, (1,)), ("gasoline", .12, (1,)),
        ("tinder_box", .036, (1,)), ("oreos", .10, (1,)), ("cola", .08, (1,)),
        ("chocolate_bar", .05, (1,)), ("compressed_biscuits", .08, (1,)),
        ("mixed_nuts", .06, (1,)), ("durian", .03, (1,)), ("vodka", .02, (1,)),
        ("sardines", .10, (1,)), ("instant_noodles", .10, (1,)),
        ("dumplings", .12, (1,)), ("beef", .12, (1,)), ("festival_dumpling", .01, (1,)),
        ("heat_patch", .029, (1,)), ("first_aid_kit", .039, (1,)), ("pocket_stove", .045, (1,)),
        ("field_supply", .006, (1,)), ("fuel_pack", .012, (1,)), ("rescue_beacon", .022, (1,)),
        ("defibrillator", .02, (1,)), ("revival_syringe", .004, (1,)), ("landmine", .02, (1,)),
    ),
    "equipment": (
        ("lantern", .075, (1,)), ("quill", .075, (1,)), ("chain_charm", .03, (1,)),
        ("repair_wrench", .025, (1,)), ("compass", .02, (1,)),
        ("axe_handle", .02, (1,)), ("building_wand", .02, (1,)), ("floor_wand", .02, (1,)),
        ("wool_scarf", .048, (1,)), ("snow_boots", .037, (1,)),
        ("armor_plate", .024, (1,)), ("safety_helmet", .01, (1,)), ("insulated_lunchbox", .026, (1,)),
    ),
}

# Balance tiers describe an item's role. Only the explicit probabilities above are rolled.
LOOT_TIERS = {
    "常用补给": ("常用弹药与即用物资参考 6–16%，基础材料参考 30–50%。",
        ("handgun", "light_ammo", "rifle_ammo", "shotgun_ammo", "wood", "spare_part", "papyrus",
         "lighter", "matches", "gasoline", "tinder_box", "oreos", "cola", "chocolate_bar",
         "compressed_biscuits", "mixed_nuts", "durian", "sardines", "instant_noodles", "dumplings", "beef")),
    "破圈对策": ("常见通路的备选解法参考 2.5–8%。同一道障碍应有几种可替代的解法。",
        ("chain_chainsaw", "flamethrower", "fireball_scroll", "freeze_scroll", "heat_patch", "pocket_stove",
         "lantern", "quill", "chain_charm", "repair_wrench", "wool_scarf", "snow_boots")),
    "通用提升": ("能提高战斗或生存效率的装备与用品参考 2–5%。",
        ("shotgun", "rifle", "hunting_rifle", "crowbar", "machete", "snow_shovel", "frost_spear",
         "ice_staff", "flame_staff", "grenade", "vodka", "first_aid_kit", "rescue_beacon",
         "defibrillator", "axe_handle", "building_wand", "floor_wand", "armor_plate", "insulated_lunchbox", "compass")),
    "稀有变招": ("高爆发、应急或特殊用途的替代品参考 0.4–2%。",
        ("rust_revolver", "cluster_charge", "frost_bomb", "fire_bottle", "flare_bomb", "festival_dumpling",
         "field_supply", "fuel_pack", "revival_syringe", "landmine", "safety_helmet")),
}
