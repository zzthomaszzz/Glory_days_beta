# Building classes: ShopBuilding, BuildingBase, BuildingHeadquarter, CapturePoint, Tower,
#                   PlayerTurret, Banner

BUILDING_STATS = {
    'Headquarter': dict(
        size=48, vision=150,
        hp=800, armor=20,
        mineral_start=200,
        minerals_per_tick=2,
        gold_per_mineral=1,
        gold_tick_interval=5.0,
    ),
    'CapturePoint': dict(
        size=32, vision=75,
        hp=300, armor=20,
        mineral_start=50,
        minerals_per_tick=2,
        gold_per_mineral=1,
        gold_tick_interval=5.0,
        capture_time=5.0,
        capture_radius=48,
    ),
    'Tower': dict(
        size=32, vision=200,
        hp=400, armor=30,
        attack_range=150, attack_damage=150,
        attack_speed=0.5, proj_speed=300,
    ),
    'PlayerTurret': dict(
        size=20, vision=150,
    ),
    'Banner': dict(
        size=20, vision=130,
        hp=1, armor=0,
    ),
    'Shop': dict(size=32, range=120),
}

_HQ = BUILDING_STATS['Headquarter']
_CP = BUILDING_STATS['CapturePoint']
_T  = BUILDING_STATS['Tower']
_PT = BUILDING_STATS['PlayerTurret']
_BN = BUILDING_STATS['Banner']
_SH = BUILDING_STATS['Shop']


#-------------------------------------------------------------------------------------------------------------------ShopBuilding
class ShopBuilding:
    SIZE  = _SH['size']
    RANGE = _SH['range']

    def __init__(self, shop_id, x, y):
        self.shop_id = shop_id
        self.x       = x
        self.y       = y

    def to_dict(self):
        return {
            "type":    "ShopBuilding",
            "x":       self.x,
            "y":       self.y,
            "size":    self.SIZE,
            "range":   self.RANGE,
            "is_shop": True,
        }


class BuildingBase:
    def __init__(self, size, x, y, vision, hp, armor=0):
        self.size   = size
        self.x      = x
        self.y      = y
        self.vision = vision
        self.hp     = hp
        self.max_hp = hp
        self.armor  = armor
        self.is_destroyed = False

    @property
    def cx(self): return self.x + self.size / 2

    @property
    def cy(self): return self.y + self.size / 2

    def update(self, dt, players): pass

    def to_dict(self):
        return {
            "type":         self.__class__.__name__,
            "x":            self.x,
            "y":            self.y,
            "size":         self.size,
            "vision":       self.vision,
            "hp":           self.hp,
            "max_hp":       self.max_hp,
            "is_destroyed": self.is_destroyed,
        }


#-------------------------------------------------------------------------------------------------------------------HQ
class BuildingHeadquarter(BuildingBase):
    def __init__(self, team, x, y):
        super().__init__(_HQ['size'], x, y, _HQ['vision'], hp=_HQ['hp'], armor=_HQ['armor'])
        self.team         = team
        self.mineral_pool = _HQ['mineral_start']
        self._gold_timer  = 0.0
        self.shield_tower = None   # set by GameState after towers are created

    @property
    def is_invulnerable(self):
        return self.shield_tower is not None and not self.shield_tower.is_destroyed

    def update(self, dt, players):
        if self.is_destroyed or self.mineral_pool <= 0:
            return
        self._gold_timer += dt
        if self._gold_timer >= _HQ['gold_tick_interval']:
            self._gold_timer = 0.0
            self.mineral_pool = max(0, self.mineral_pool - _HQ['minerals_per_tick'])
            for player in players.values():
                if player.team == self.team:
                    player.gold += _HQ['gold_per_mineral']

    def to_dict(self):
        d = super().to_dict()
        d["team"]            = self.team
        d["mineral_pool"]    = self.mineral_pool
        d["is_invulnerable"] = self.is_invulnerable
        return d


#-------------------------------------------------------------------------------------------------------------------CapturePoint
class CapturePoint(BuildingBase):
    def __init__(self, bid, x, y):
        super().__init__(_CP['size'], x, y, _CP['vision'], hp=_CP['hp'], armor=_CP['armor'])
        self.bid            = bid
        self.team           = 0        # 0 = neutral
        self.capture_timer  = 0.0
        self.capturing_team = None
        self._gold_timer    = 0.0
        self._mineral_pool  = _CP['mineral_start']

    def _reset(self):
        self.team           = 0
        self.hp             = self.max_hp
        self.capture_timer  = 0.0
        self.capturing_team = None
        self._gold_timer    = 0.0
        self.is_destroyed   = False

    def update(self, dt, players):
        if self.is_destroyed:
            if self._mineral_pool > 0:
                self._reset()
            return

        cx = self.x + self.size // 2
        cy = self.y + self.size // 2
        r2 = _CP['capture_radius'] ** 2

        teams_present = set()
        for player in players.values():
            if player.is_dead:
                continue
            dx = player.x - cx
            dy = player.y - cy
            if dx * dx + dy * dy <= r2:
                teams_present.add(player.team)

        if len(teams_present) == 1:
            contesting = next(iter(teams_present))
            if contesting != self.team:
                if self.team == 0:
                    # Neutral — can be captured normally
                    if self.capturing_team != contesting:
                        self.capturing_team = contesting
                        self.capture_timer  = 0.0
                    self.capture_timer += dt
                    if self.capture_timer >= _CP['capture_time']:
                        self.team           = contesting
                        self.capture_timer  = 0.0
                        self.capturing_team = None
                # else: owned by enemy — must destroy it first before capturing
        else:
            self.capture_timer  = 0.0
            self.capturing_team = None

        if self.team != 0 and self._mineral_pool > 0:
            self._gold_timer += dt
            if self._gold_timer >= _CP['gold_tick_interval']:
                self._gold_timer = 0.0
                self._mineral_pool = max(0, self._mineral_pool - _CP['minerals_per_tick'])
                for player in players.values():
                    if player.team == self.team:
                        player.gold += _CP['gold_per_mineral']

    def to_dict(self):
        d = super().to_dict()
        d["team"]           = self.team
        d["capture_timer"]  = round(self.capture_timer, 2)
        d["capture_time"]   = _CP['capture_time']
        d["capturing_team"] = self.capturing_team
        return d


#-------------------------------------------------------------------------------------------------------------------Tower
class Tower(BuildingBase):
    def __init__(self, tower_id, team, x, y):
        super().__init__(_T['size'], x, y, _T['vision'], hp=_T['hp'], armor=_T['armor'])
        self.id            = tower_id
        self.team          = team
        self._attack_timer = 0.0

    def update_attack(self, dt, players, projectiles, proj_counter):
        if self.is_destroyed:
            return
        self._attack_timer -= dt
        if self._attack_timer > 0:
            return
        target = self._find_target(players)
        if not target:
            return
        from server.projectiles import Projectile
        self._attack_timer = 1.0 / _T['attack_speed']
        pid = proj_counter[0]
        proj_counter[0] += 1
        projectiles[pid] = Projectile(
            pid, self.id, self.team,
            self.cx, self.cy,
            "player", target.id,
            _T['attack_damage'], target.armor,
            _T['proj_speed'],
        )

    def _find_target(self, players):
        best    = None
        best_d2 = _T['attack_range'] ** 2
        for p in players.values():
            if p.is_dead or p.team == self.team:
                continue
            dx = p.x - self.cx
            dy = p.y - self.cy
            d2 = dx*dx + dy*dy
            if d2 <= best_d2:
                best_d2 = d2
                best    = p
        return best

    def to_dict(self):
        d = super().to_dict()
        d["team"] = self.team
        return d


#-------------------------------------------------------------------------------------------------------------------PlayerTurret
class PlayerTurret(BuildingBase):
    def __init__(self, turret_id, owner_id, team, x, y,
                 hp, armor, atk_range, atk_dmg, atk_speed, proj_speed):
        super().__init__(_PT['size'], x, y, _PT['vision'], hp=hp, armor=armor)
        self.id            = turret_id
        self.owner_id      = owner_id
        self.team          = team
        self.attack_range  = atk_range
        self.attack_damage = atk_dmg
        self.attack_speed  = atk_speed
        self.proj_speed    = proj_speed
        self.attack_timer  = 0.0

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
class Banner(BuildingBase):
    def __init__(self, banner_id, owner_id, team, x, y,
                 duration, heal_radius, heal_pct_sec):
        super().__init__(_BN['size'], x, y, _BN['vision'], hp=_BN['hp'], armor=_BN['armor'])
        self.id           = banner_id
        self.owner_id     = owner_id
        self.team         = team
        self.duration     = duration
        self.heal_radius  = heal_radius
        self.heal_pct_sec = heal_pct_sec

    def update(self, dt, players):
        if self.is_destroyed:
            return
        self.duration -= dt
        if self.duration <= 0:
            self.is_destroyed = True
            return
        r2 = self.heal_radius ** 2
        for p in players.values():
            if p.is_dead or p.team != self.team:
                continue
            dx, dy = p.x - self.x, p.y - self.y
            if dx * dx + dy * dy <= r2:
                p.hp = min(p.max_hp, p.hp + p.max_hp * self.heal_pct_sec * dt)

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
