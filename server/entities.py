# Player class, HERO_ABILITIES, HERO_REGISTRY, and misc server-side entities
# (Trap, BurningArea, PlayerTurret, Banner).
# Stats and display data live in shared/heroes.py; only ability class references
# belong here since those can't be in a shared module.
from shared.heroes import HERO_STATS
from server.abilities import (
    Snipe, PlaceTurret, Dash,
    Fireball, Mend, Teleport,
    Charge, GroundSlam, Fortify,
    Spin, Bushido, PlaceBanner,
    Stealth, PlaceTrap, Bolt,
    Recall, Hook, IronStack, BattleCry,
)

# Ability class loadouts — parallel to HERO_STATS in shared/heroes.py.
# When adding a new hero, add its entry here AND in shared/heroes.py.
HERO_ABILITIES = {
    'Soldier': [Snipe, PlaceTurret, Dash, Recall],
    'Mage':    [Fireball, Mend, Teleport, Recall],
    'Hunter':  [Charge, GroundSlam, Fortify, Recall],
    'Samurai': [Spin, Bushido, PlaceBanner, Recall],
    'Rat':     [Stealth, PlaceTrap, Bolt, Recall],
    'Watcher': [Hook, IronStack, BattleCry, Recall],
}

HERO_REGISTRY = set(HERO_STATS)

# Tunable numbers for spawned entities. Each class reads its own sub-dict.
ENTITY_STATS = {
    'Trap': dict(
        root_dur=2.0, bleed_dps=30, bleed_dur=2.0,
        sight_dur=3.0, trigger_r=20, size=16,
    ),
    'BurningArea': dict(
        size=64, duration=4.0, tick_damage=20, tick_interval=0.5,
    ),
    'PlayerTurret': dict(
        hp=200, armor=5, atk_range=100, atk_dmg=40,
        atk_speed=0.8, vision=100, size=20, proj_speed=200,
    ),
    'Banner': dict(
        hp=1, armor=0, vision=130, size=20,
        duration=10.0, heal_radius=100, heal_pct_sec=0.02,
    ),
}


class EntityBase:
    def __init__(self, size, x, y, vision):
        self.size   = size
        self.x      = x
        self.y      = y
        self.vision = vision


class Player(EntityBase):
    def __init__(self, player_id, team, hero_name='Soldier'):
        _s = HERO_STATS.get(hero_name, HERO_STATS['Soldier'])
        super().__init__(32, 0, 0, _s['vision'])

        #Identity
        self.hero = hero_name
        self.id   = player_id
        self.team = team

        #Vitals
        self.hp       = _s['hp']
        self.max_hp   = _s['hp']
        self.mana     = _s['mana']
        self.max_mana = _s['mana']

        #Offense
        self.attack_damage = _s['attack_damage']
        self.ability_power = _s['ability_power']
        self.attack_range  = _s['attack_range']
        self.attack_speed  = _s['attack_speed']
        self.attack_timer  = 0.0
        self.crit_chance   = _s['crit_chance']

        #Defense
        self.armor        = _s['armor']
        self.magic_resist = _s['magic_resist']

        #Mobility
        self.speed = _s['speed']

        #Combat type
        self.is_ranged  = _s['is_ranged']
        self.proj_speed = _s['proj_speed']

        #Economy
        self.gold       = 0
        self.hp_regen   = 0.0
        self.mana_regen = 0.0

        #Inventory
        self.inventory = [None] * 6

        #Input
        self.dx = 0
        self.dy = 0

        #Abilities
        self.abilities = [A() for A in HERO_ABILITIES.get(hero_name, [])]

        #Status
        self.attack_target       = None
        self.is_dead             = False
        self.respawn_timer       = 0.0
        self.is_attacking        = False
        self.attack_windup_timer = 0.0
        self.stun_timer          = 0.0
        self.slow_timer          = 0.0
        self.slow_factor         = 1.0
        self.root_timer          = 0.0
        self.armor_reduction       = 0
        self.armor_reduction_timer = 0.0
        self.bleed_timer          = 0.0
        self.bleed_dps            = 0.0
        self.revealed_timer       = 0.0
        self.is_invisible         = False
        self._stealth_bonus_ready = False
        self.bush_idx             = -1

    def reset_on_spawn(self, x, y):
        self.x             = x
        self.y             = y
        self.hp            = self.max_hp
        self.mana          = self.max_mana
        self.dx            = 0
        self.dy            = 0
        self.attack_target = None
        self.is_attacking  = False
        self.is_dead       = False
        self.bush_idx      = -1

    def reset_full(self, x, y):
        self.reset_on_spawn(x, y)
        self.respawn_timer         = 0.0
        self.stun_timer            = 0.0
        self.slow_timer            = 0.0
        self.slow_factor           = 1.0
        self.root_timer            = 0.0
        self.bleed_timer           = 0.0
        self.bleed_dps             = 0.0
        self.revealed_timer        = 0.0
        self.is_invisible          = False
        self._stealth_bonus_ready  = False
        self.armor_reduction       = 0
        self.armor_reduction_timer = 0.0
        for ab in self.abilities:
            if ab:
                ab.is_on_cooldown = False
                ab.cooldown_timer = 0.0
                if hasattr(ab, 'is_channeling'):
                    ab.is_channeling = False
                if hasattr(ab, 'is_active'):
                    ab.is_active = False

    def to_dict(self):
        return {
            "id":           self.id,
            "hero":         self.hero,
            "team":         self.team,
            "pos":          [self.x, self.y],
            "hp":           self.hp,
            "max_hp":       self.max_hp,
            "mana":         self.mana,
            "max_mana":     self.max_mana,
            "attack_damage": self.attack_damage,
            "ability_power": self.ability_power,
            "attack_range": self.attack_range,
            "armor":        self.armor,
            "magic_resist": self.magic_resist,
            "speed":        self.speed,
            "gold":         self.gold,
            "vision":       self.vision,
            "is_dead":      self.is_dead,
            "respawn_timer":  round(self.respawn_timer,  2),
            "stun_timer":     round(self.stun_timer,     2),
            "slow_timer":     round(self.slow_timer,     2),
            "root_timer":     round(self.root_timer,     2),
            "bleed_timer":    round(self.bleed_timer,    2),
            "revealed_timer": round(self.revealed_timer, 2),
            "is_invisible": self.is_invisible,
            "bush_idx":     self.bush_idx,
            "abilities":    [a.to_dict() if a else None for a in self.abilities],
            "inventory":    self.inventory[:],
        }


#-------------------------------------------------------------------------------------------------------------------Trap
class Trap:
    _s        = ENTITY_STATS['Trap']
    ROOT_DUR  = _s['root_dur']
    BLEED_DPS = _s['bleed_dps']
    BLEED_DUR = _s['bleed_dur']
    SIGHT_DUR = _s['sight_dur']
    TRIGGER_R = _s['trigger_r']
    SIZE      = _s['size']

    def __init__(self, trap_id, owner_id, team, x, y):
        self.id         = trap_id
        self.owner_id   = owner_id
        self.team       = team
        self.x          = x
        self.y          = y
        self.size       = self.SIZE
        self.is_expired = False

    def update(self, dt, players):
        if self.is_expired:
            return
        r2 = self.TRIGGER_R ** 2
        for p in players.values():
            if p.is_dead or p.team == self.team:
                continue
            dx = p.x - self.x
            dy = p.y - self.y
            if dx * dx + dy * dy <= r2:
                self._trigger(p)
                return

    def _trigger(self, player):
        player.root_timer     = self.ROOT_DUR
        player.bleed_timer    = self.BLEED_DUR
        player.bleed_dps      = self.BLEED_DPS
        player.revealed_timer = self.SIGHT_DUR
        self.is_expired       = True

    def to_dict(self):
        return {
            "id":       self.id,
            "owner_id": self.owner_id,
            "team":     self.team,
            "x":        self.x,
            "y":        self.y,
            "size":     self.SIZE,
        }


#-------------------------------------------------------------------------------------------------------------------BurningArea
class BurningArea:
    _s            = ENTITY_STATS['BurningArea']
    SIZE          = _s['size']
    DURATION      = _s['duration']
    TICK_DAMAGE   = _s['tick_damage']
    TICK_INTERVAL = _s['tick_interval']

    def __init__(self, area_id, x, y, owner_team, tick_damage=None):
        self.id           = area_id
        self.x            = x
        self.y            = y
        self.owner_team   = owner_team
        self.tick_damage  = tick_damage if tick_damage is not None else self.TICK_DAMAGE
        self.duration     = self.DURATION
        self.tick_timer   = 0.0
        self.is_expired   = False

    def update(self, dt, players, player_turrets):
        self.duration -= dt
        if self.duration <= 0:
            self.is_expired = True
            return
        self.tick_timer += dt
        if self.tick_timer >= self.TICK_INTERVAL:
            self.tick_timer = 0.0
            self._tick_damage(players, player_turrets)

    def _tick_damage(self, players, player_turrets):
        from server.projectiles import apply_damage  # avoids circular import
        half = self.SIZE // 2
        for p in players.values():
            if p.is_dead or p.team == self.owner_team:
                continue
            if abs(p.x - self.x) <= half and abs(p.y - self.y) <= half:
                apply_damage(p, self.tick_damage, 0)
        for t in player_turrets.values():
            if t.is_destroyed or t.team == self.owner_team:
                continue
            if abs(t.x - self.x) <= half and abs(t.y - self.y) <= half:
                apply_damage(t, self.tick_damage, 0)

    def to_dict(self):
        return {
            "id":         self.id,
            "x":          self.x,
            "y":          self.y,
            "size":       self.SIZE,
            "duration":   round(self.duration, 2),
            "owner_team": self.owner_team,
        }


#-------------------------------------------------------------------------------------------------------------------PlayerTurret
class PlayerTurret:
    _s         = ENTITY_STATS['PlayerTurret']
    HP         = _s['hp']
    ARMOR      = _s['armor']
    ATK_RANGE  = _s['atk_range']
    ATK_DMG    = _s['atk_dmg']
    ATK_SPEED  = _s['atk_speed']
    VISION     = _s['vision']
    SIZE       = _s['size']
    PROJ_SPEED = _s['proj_speed']

    def __init__(self, turret_id, owner_id, team, x, y):
        self.id            = turret_id
        self.owner_id      = owner_id
        self.team          = team
        self.x             = x
        self.y             = y
        self.hp            = self.HP
        self.max_hp        = self.HP
        self.armor         = self.ARMOR
        self.attack_range  = self.ATK_RANGE
        self.attack_damage = self.ATK_DMG
        self.attack_speed  = self.ATK_SPEED
        self.vision        = self.VISION
        self.size          = self.SIZE
        self.proj_speed    = self.PROJ_SPEED
        self.attack_timer  = 0.0
        self.is_destroyed  = False

    def to_dict(self):
        return {
            "id":           self.id,
            "owner_id":     self.owner_id,
            "team":         self.team,
            "x":            self.x,
            "y":            self.y,
            "hp":           self.hp,
            "max_hp":       self.max_hp,
            "attack_range": self.attack_range,
            "vision":       self.vision,
            "size":         self.size,
            "is_destroyed": self.is_destroyed,
        }


#-------------------------------------------------------------------------------------------------------------------Banner
class Banner:
    _s           = ENTITY_STATS['Banner']
    HP           = _s['hp']
    ARMOR        = _s['armor']
    VISION       = _s['vision']
    SIZE         = _s['size']
    DURATION     = _s['duration']
    HEAL_RADIUS  = _s['heal_radius']
    HEAL_PCT_SEC = _s['heal_pct_sec']

    def __init__(self, banner_id, owner_id, team, x, y):
        self.id           = banner_id
        self.owner_id     = owner_id
        self.team         = team
        self.x            = x
        self.y            = y
        self.hp           = self.HP
        self.max_hp       = self.HP
        self.armor        = self.ARMOR
        self.vision       = self.VISION
        self.size         = self.SIZE
        self.duration     = self.DURATION
        self.is_destroyed = False

    def update(self, dt, players):
        if self.is_destroyed:
            return
        self.duration -= dt
        if self.duration <= 0:
            self.is_destroyed = True
            return
        r2 = self.HEAL_RADIUS ** 2
        for p in players.values():
            if p.is_dead or p.team != self.team:
                continue
            dx, dy = p.x - self.x, p.y - self.y
            if dx * dx + dy * dy <= r2:
                p.hp = min(p.max_hp, p.hp + p.max_hp * self.HEAL_PCT_SEC * dt)

    def to_dict(self):
        return {
            "id":           self.id,
            "owner_id":     self.owner_id,
            "team":         self.team,
            "x":            self.x,
            "y":            self.y,
            "hp":           self.hp,
            "max_hp":       self.max_hp,
            "size":         self.size,
            "vision":       self.vision,
            "duration":     round(self.duration, 1),
            "is_destroyed": self.is_destroyed,
        }
