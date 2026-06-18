ITEMS = {
    "Scythe": {
        "cost":   100,
        "stats":  {"attack_damage": 50},
        "label":  "SCY",
        "desc":   "+50 Attack Damage",
    },
    "Chain Vest": {
        "cost":   80,
        "stats":  {"armor": 10, "magic_resist": 5},
        "label":  "CVS",
        "desc":   "+10 Armor  +5 Magic Resist",
    },
    "Staff": {
        "cost":   100,
        "stats":  {"ability_power": 50},
        "label":  "STF",
        "desc":   "+50 Ability Power",
    },
    "Ancient Rune": {
        "cost":   30,
        "stats":  {"hp_regen": 5},
        "label":  "RUN",
        "desc":   "+5 HP Regen / sec",
    },
    "Boots": {
        "cost":   30,
        "stats":  {"speed": 30},
        "label":  "BOT",
        "desc":   "+30 Move Speed",
    },
    "Fang": {
        "cost":   80,
        "stats":  {"attack_damage": 20},
        "label":  "FNG",
        "desc":   "+20 Damage  -10 enemy armor on hit (3s)",
    },
}

ITEM_KEYS = list(ITEMS.keys())
