# Player class, HERO_ABILITIES, HERO_REGISTRY, and misc server-side placed effects
# (Trap, BurningArea — no HP, trigger/AoE based).
# Stats and display data live in shared/heroes.py; only ability class references
# belong here since those can't be in a shared module.
from shared.heroes import HERO_STATS
from server.abilities import (
    Snipe, PlaceTurret, Dash,
    Fireball, Mend, Teleport, FatedMissile,
    Charge, GroundSlam, Fortify,
    Spin, Bushido, PlaceBanner,
    Stealth, PlaceTrap, Bolt,
    Recall, Hook, IronStack, BattleCry,
    EagleEye, ThrowingNets,
)

# Ability class loadouts — parallel to HERO_STATS in shared/heroes.py.
# When adding a new hero, add its entry here AND in shared/heroes.py.
HERO_ABILITIES = {
    'Soldier': [Snipe, PlaceTurret, Dash, Recall],
    'Mage':    [Fireball, FatedMissile, Teleport, Recall],
    'Hunter':  [Charge, GroundSlam, Fortify, Recall],
    'Samurai': [Spin, Bushido, PlaceBanner, Recall],
    'Archer':  [Stealth, PlaceTrap, Bolt, Recall],
    'Watcher': [Hook, IronStack, BattleCry, Recall],
    'Warden':  [Mend, ThrowingNets, EagleEye, Recall],
}

HERO_REGISTRY = set(HERO_STATS)



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
        self.attack_windup = _s.get('attack_windup', 0.25)
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

        #KDA
        self.kills         = 0
        self.deaths        = 0
        self.assists       = 0
        self.kill_streak   = 0
        self.damage_log        = {}   # {attacker_id: timestamp} — recent attackers for assist tracking
        self._assist_killer_id = None  # set on death, cleared after assist resolution
        self._had_bounty       = False # True if killed player had 3+ kill streak

        #Inventory
        self.inventory = [None] * 6

        #Input
        self.dx = 0
        self.dy = 0

        #Abilities
        self.abilities = [A() for A in HERO_ABILITIES.get(hero_name, [])]

        #Pull state (Hook)
        self.pull_vx    = 0.0
        self.pull_vy    = 0.0
        self.pull_timer = 0.0

        #Status
        self.attack_target       = None
        self.is_dead             = False
        self.respawn_timer       = 0.0
        self.is_attacking        = False      # True during attack windup (melee and ranged)
        self.attack_windup_timer = 0.0
        self._pending_damage     = 0          # damage locked in at windup commit
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
        self.x                   = x
        self.y                   = y
        self.hp                  = self.max_hp
        self.mana                = self.max_mana
        self.dx                  = 0
        self.dy                  = 0
        self.attack_target       = None
        self.is_attacking        = False
        self.attack_timer        = 0.0
        self.attack_windup_timer = 0.0
        self._pending_damage     = 0
        self.is_dead             = False
        self.bush_idx            = -1
        self.pull_vx             = 0.0
        self.pull_vy             = 0.0
        self.pull_timer          = 0.0
        self.damage_log          = {}
        self._assist_killer_id   = None
        self._had_bounty         = False
        self.kill_streak         = 0

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
        d = {
            "id":           self.id,
            "hero":         self.hero,
            "team":         self.team,
            "pos":          [self.x, self.y],
            "hp":           self.hp,
            "max_hp":       self.max_hp,
            "mana":         self.mana,
            "max_mana":     self.max_mana,
            "attack_range": self.attack_range,
            "gold":         self.gold,
            "vision":       self.vision,
            "is_dead":      self.is_dead,
            "is_invisible": self.is_invisible,
            "bush_idx":     self.bush_idx,
            "kills":        self.kills,
            "deaths":       self.deaths,
            "assists":      self.assists,
            "abilities":    [a.to_dict() if a else None for a in self.abilities],
            "inventory":    self.inventory[:],
        }
        if self.is_dead:         anim_state = "dead"
        elif self.is_attacking:  anim_state = "attack"
        elif self.dx or self.dy: anim_state = "running"
        else:                    anim_state = "idle"
        d["anim_state"] = anim_state
        if self.respawn_timer  > 0: d["respawn_timer"]  = round(self.respawn_timer,  2)
        if self.stun_timer     > 0: d["stun_timer"]     = round(self.stun_timer,     2)
        if self.slow_timer     > 0: d["slow_timer"]     = round(self.slow_timer,     2)
        if self.root_timer     > 0: d["root_timer"]     = round(self.root_timer,     2)
        if self.bleed_timer           > 0: d["bleed_timer"]           = round(self.bleed_timer,           2)
        if self.revealed_timer        > 0: d["revealed_timer"]        = round(self.revealed_timer,        2)
        if self.pull_timer            > 0: d["pull_timer"]            = round(self.pull_timer,            2)
        if self.armor_reduction_timer > 0: d["armor_reduction_timer"] = round(self.armor_reduction_timer, 2)
        return d


#-------------------------------------------------------------------------------------------------------------------Trap
class Trap:
    def __init__(self, trap_id, owner_id, team, x, y,
                 root_dur, bleed_dps, bleed_dur, sight_dur, trigger_r, size):
        self.id             = trap_id
        self.owner_id       = owner_id
        self.team           = team
        self.x              = x
        self.y              = y
        self.size           = size
        self.root_dur       = root_dur
        self.bleed_dps      = bleed_dps
        self.bleed_dur      = bleed_dur
        self.sight_dur      = sight_dur
        self.trigger_r      = trigger_r
        self.is_expired     = False
        #Combat
        self.hp             = 1
        self.max_hp         = 1
        self.armor          = 0
        self.revealed_timer = 0.0

    @property
    def is_destroyed(self):
        return self.is_expired

    @is_destroyed.setter
    def is_destroyed(self, val):
        if val:
            self.is_expired = True

    def update(self, dt, players):
        if self.revealed_timer > 0:
            self.revealed_timer = max(0.0, self.revealed_timer - dt)
        if self.is_expired:
            return
        r2 = self.trigger_r ** 2
        for p in players.values():
            if p.is_dead or p.team == self.team:
                continue
            dx = p.x - self.x
            dy = p.y - self.y
            if dx * dx + dy * dy <= r2:
                self._trigger(p)
                return

    def _trigger(self, player):
        player.root_timer     = self.root_dur
        player.bleed_timer    = self.bleed_dur
        player.bleed_dps      = self.bleed_dps
        player.revealed_timer = self.sight_dur
        self.is_expired       = True

    def to_dict(self):
        return {
            "id":             self.id,
            "owner_id":       self.owner_id,
            "team":           self.team,
            "x":              self.x,
            "y":              self.y,
            "size":           self.size,
            "revealed_timer": round(self.revealed_timer, 2),
        }


#-------------------------------------------------------------------------------------------------------------------BurningArea
class BurningArea:
    def __init__(self, area_id, x, y, owner_team, tick_damage=20,
                 size=64, duration=4.0, tick_interval=0.5):
        self.id           = area_id
        self.x            = x
        self.y            = y
        self.owner_team   = owner_team
        self.tick_damage  = tick_damage
        self.size         = size
        self.duration     = duration
        self.tick_interval = tick_interval
        self.tick_timer   = 0.0
        self.is_expired   = False

    def update(self, dt, players, player_turrets):
        self.duration -= dt
        if self.duration <= 0:
            self.is_expired = True
            return
        self.tick_timer += dt
        if self.tick_timer >= self.tick_interval:
            self.tick_timer = 0.0
            self._tick_damage(players, player_turrets)

    def _tick_damage(self, players, player_turrets):
        from server.projectiles import apply_damage  # avoids circular import
        half = self.size // 2
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
            "size":       self.size,
            "duration":   round(self.duration, 2),
            "owner_team": self.owner_team,
        }

