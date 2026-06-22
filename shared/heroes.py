# HERO_STATS — all per-hero numbers and lobby display data in one place.
# Ability class references live in server/entities.py (HERO_ABILITIES) to avoid
# importing server-side modules here.  Add a new hero by adding an entry below,
# then adding its ability classes to HERO_ABILITIES in server/entities.py.
HERO_STATS = {
    'Soldier': dict(
        hp=420, mana=250, attack_damage=75, ability_power=0,
        attack_range=150, attack_speed=1.0,  crit_chance=0.0,
        armor=25, magic_resist=30, speed=115, vision=150,
        is_ranged=True, proj_speed=400,
        attack_windup=0.5,
        desc="Ranged fighter with precision shots and turret support.",
        ability_descs=[
            ("Q", "Snipe",        "Targeted long-range shot"),
            ("E", "Place Turret", "Deploy an auto-attacking turret"),
            ("R", "Dash",         "Dash in your movement direction"),
        ],
    ),
    'Mage': dict(
        hp=400, mana=400, attack_damage=60, ability_power=70,
        attack_range=140, attack_speed=0.55, crit_chance=0.0,
        armor=15, magic_resist=20, speed=110, vision=150,
        is_ranged=True, proj_speed=350,
        attack_windup=0.5,
        desc="Burst caster who excels at area control and healing.",
        ability_descs=[
            ("Q", "Fireball",       "Launch a fireball that burns an area"),
            ("E", "Fated Missile",  "Channel then fire a homing missile — stuns on impact"),
            ("R", "Teleport",       "Channel to teleport to a location"),
        ],
    ),
    'Hunter': dict(
        hp=530, mana=200, attack_damage=80, ability_power=0,
        attack_range=50,  attack_speed=0.9,  crit_chance=0.0,
        armor=30, magic_resist=25, speed=120, vision=150,
        is_ranged=False, proj_speed=0,
        attack_windup=0.25,
        desc="Tanky melee brawler who charges and stuns enemies.",
        ability_descs=[
            ("Q", "Charge",      "Dash to an enemy, stunning them"),
            ("E", "Ground Slam", "AOE slam dealing 50 damage nearby"),
            ("R", "Fortify",     "Gain damage reduction for 5 seconds"),
        ],
    ),
    'Samurai': dict(
        hp=440, mana=250, attack_damage=70, ability_power=0,
        attack_range=60,  attack_speed=1.2,  crit_chance=0.0,
        armor=22, magic_resist=35, speed=110, vision=160,
        is_ranged=False, proj_speed=0,
        attack_windup=0.25,
        desc="Disciplined melee duelist with crit lifesteal and a healing banner.",
        ability_descs=[
            ("Q", "Spin",         "Spin for 5s, dealing 25 dmg every 0.5s in a circle"),
            ("E", "Bushido",      "Passive: 25% crit for 1.4x dmg, heal for damage dealt"),
            ("R", "Place Banner", "Deploy a banner healing allies 2% HP/s for 10s"),
        ],
    ),
    'Archer': dict(
        hp=320, mana=300, attack_damage=65, ability_power=0,
        attack_range=140, attack_speed=0.85, crit_chance=0.0,
        armor=12, magic_resist=10, speed=100, vision=160,
        is_ranged=True, proj_speed=400,
        attack_windup=0.5,
        desc="Stealthy ranged assassin who ambushes from the shadows and sets deadly traps.",
        ability_descs=[
            ("Q", "Stealth",    "Turn invisible for 12s — first attack deals 1.5x damage"),
            ("E", "Place Trap", "Place a trap (max 3) that roots and bleeds enemies for 2s"),
            ("R", "Bolt",       "Fire a heavy bolt that breaks on terrain, deals 280 dmg"),
        ],
    ),
    'Watcher': dict(
        hp=600, mana=250, attack_damage=60, ability_power=0,
        attack_range=80,  attack_speed=0.6,  crit_chance=0.0,
        armor=35, magic_resist=30, speed=95,  vision=180,
        is_ranged=False, proj_speed=0,
        attack_windup=0.25,
        desc="Tanky melee brawler who hooks enemies close and hardens under fire.",
        ability_descs=[
            ("Q", "Hook",       "Channel then launch a hook — pulls hit enemies toward you"),
            ("E", "Iron Stack", "Passive: each auto attack adds +5 armor (up to 10 stacks, 5s)"),
            ("R", "Battle Cry", "Grant +40 speed to nearby allies for 3 seconds"),
        ],
    ),
    'Warden': dict(
        hp=380, mana=350, attack_damage=55, ability_power=0,
        attack_range=130, attack_speed=0.6,  crit_chance=0.0,
        armor=18, magic_resist=22, speed=108, vision=175,
        is_ranged=True, proj_speed=350,
        attack_windup=0.5,
        desc="Ranged support who heals allies, traps enemies, and sees through stealth.",
        ability_descs=[
            ("Q", "Mend",          "Sacrifice HP to heal a target ally"),
            ("E", "Throwing Nets", "Throw a slow net that roots enemies on landing"),
            ("R", "Eagle Eye",     "Passive: reveal invisible enemies within vision range"),
        ],
    ),
}
