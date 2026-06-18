from server.abilities import *


class EntityBase:
    def __init__(self, size, x, y, vision):
        self.size = size
        self.x = x
        self.y = y
        self.vision = vision


class Player(EntityBase):
    #Base stats — override per hero subclass
    BASE_HP            = 550
    BASE_MANA          = 300
    BASE_ATTACK_DAMAGE = 55
    BASE_ABILITY_POWER = 0
    BASE_ATTACK_RANGE  = 50
    BASE_ATTACK_SPEED  = 0.65
    BASE_CRIT_CHANCE   = 0.0
    BASE_ARMOR         = 25
    BASE_MAGIC_RESIST  = 30
    BASE_SPEED         = 100
    BASE_VISION        = 200

    is_ranged  = False
    proj_speed = 0

    default_abilities = [None, None, None]

    def __init__(self, player_id, team):
        super().__init__(32, 0, 0, self.BASE_VISION)
        #Identity
        self.id = player_id
        self.team = team

        #Vitals
        self.hp = self.BASE_HP
        self.max_hp = self.BASE_HP
        self.mana = self.BASE_MANA
        self.max_mana = self.BASE_MANA

        #Offense
        self.attack_damage = self.BASE_ATTACK_DAMAGE
        self.ability_power = self.BASE_ABILITY_POWER
        self.attack_range  = self.BASE_ATTACK_RANGE
        self.attack_speed  = self.BASE_ATTACK_SPEED
        self.attack_timer  = 0.0
        self.crit_chance   = self.BASE_CRIT_CHANCE

        #Defense
        self.armor        = self.BASE_ARMOR
        self.magic_resist = self.BASE_MAGIC_RESIST

        #Mobility
        self.speed = self.BASE_SPEED

        #Economy
        self.gold     = 0
        self.hp_regen = 0.0

        #Inventory
        self.inventory = [None] * 6

        #Input
        self.dx = 0
        self.dy = 0

        #Abilities
        self.abilities = [A() if A else None for A in self.__class__.default_abilities]

        #Status
        self.attack_target = None
        self.is_dead = False
        self.respawn_timer = 0.0
        self.is_attacking = False
        self.attack_windup_timer = 0.0
        self.stun_timer  = 0.0
        self.slow_timer  = 0.0
        self.slow_factor = 1.0
        self.armor_reduction       = 0
        self.armor_reduction_timer = 0.0

    def to_dict(self):
        return {
            "id": self.id,
            "hero": self.__class__.__name__,
            "team": self.team,
            "pos": [self.x, self.y],
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mana": self.mana,
            "max_mana": self.max_mana,
            "attack_damage": self.attack_damage,
            "ability_power": self.ability_power,
            "attack_range": self.attack_range,
            "armor": self.armor,
            "magic_resist": self.magic_resist,
            "speed": self.speed,
            "gold": self.gold,
            "vision": self.vision,
            "is_dead": self.is_dead,
            "respawn_timer": round(self.respawn_timer, 2),
            "stun_timer":  round(self.stun_timer,  2),
            "slow_timer":  round(self.slow_timer,  2),
            "abilities": [a.to_dict() if a else None for a in self.abilities],
            "inventory": self.inventory[:],
        }


#-------------------------------------------------------------------------------------------------------------------Soldier
class Soldier(Player):
    BASE_HP            = 420
    BASE_ATTACK_DAMAGE = 75
    BASE_ATTACK_RANGE  = 150
    BASE_ATTACK_SPEED  = 1
    BASE_SPEED         = 115
    BASE_VISION        = 150
    is_ranged          = True
    proj_speed         = 400

    default_abilities  = [Snipe, PlaceTurret, Dash]


#-------------------------------------------------------------------------------------------------------------------Mage
class Mage(Player):
    BASE_HP            = 400
    BASE_MANA          = 350
    BASE_ATTACK_DAMAGE = 30
    BASE_ABILITY_POWER = 70
    BASE_ATTACK_RANGE  = 120
    BASE_ATTACK_SPEED  = 0.75
    BASE_ARMOR         = 15
    BASE_MAGIC_RESIST  = 20
    BASE_SPEED         = 110
    BASE_VISION        = 180
    is_ranged          = True
    proj_speed         = 250

    default_abilities  = [Fireball, Mend, Teleport]


#-------------------------------------------------------------------------------------------------------------------Hunter
class Hunter(Player):
    BASE_HP            = 530
    BASE_ATTACK_DAMAGE = 80
    BASE_ATTACK_RANGE  = 50
    BASE_ATTACK_SPEED  = 0.9
    BASE_ARMOR         = 40
    BASE_MAGIC_RESIST  = 25
    BASE_SPEED         = 120
    BASE_VISION        = 150
    is_ranged          = False
    proj_speed         = 0

    default_abilities  = [Charge, GroundSlam, Fortify]


#-------------------------------------------------------------------------------------------------------------------Registry
HERO_REGISTRY = {
    "Soldier": Soldier,
    "Mage":    Mage,
    "Hunter":  Hunter,
}


#-------------------------------------------------------------------------------------------------------------------BurningArea
class BurningArea:
    SIZE          = 64
    DURATION      = 4.0
    TICK_DAMAGE   = 20
    TICK_INTERVAL = 0.5

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
        from server.projectiles import apply_damage
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
    HP         = 200
    ARMOR      = 5
    ATK_RANGE  = 100
    ATK_DMG    = 40
    ATK_SPEED  = 0.8
    VISION     = 100
    SIZE       = 20
    PROJ_SPEED = 200

    def __init__(self, turret_id, owner_id, team, x, y):
        self.id           = turret_id
        self.owner_id     = owner_id
        self.team         = team
        self.x            = x
        self.y            = y
        self.hp           = self.HP
        self.max_hp       = self.HP
        self.armor        = self.ARMOR
        self.attack_range = self.ATK_RANGE
        self.attack_damage = self.ATK_DMG
        self.attack_speed = self.ATK_SPEED
        self.vision       = self.VISION
        self.size         = self.SIZE
        self.proj_speed   = self.PROJ_SPEED
        self.attack_timer = 0.0
        self.is_destroyed = False

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
