"""PracticeClient: local game simulation, no server required."""
import math
import time

from shared.heroes import HERO_STATS
from shared.map_data import CAPTURE_ZONES
from shared.constants import MAP_W, MAP_H


_MY_ID           = "practice_player"
_DUMMY_IDS       = ["dummy_0", "dummy_1", "dummy_2"]
_DUMMY_POSITIONS = [(580, 340), (660, 420), (740, 340)]
_DUMMY_HP        = 400.0
_DUMMY_RESPAWN   = 4.0
_DUMMY_REGEN     = 25.0   # hp/s passive regen on dummies

_TEAM1_SPAWN = (48.0, 48.0)


class PracticeClient:
    """Mimics NetworkClient API using a fully local game simulation."""

    def __init__(self, hero_name: str):
        self.my_player_id   = _MY_ID
        self.my_team        = 1
        self.is_connected   = True
        self.shops          = {
            "shop_0": {"x": 80,   "y": 80,   "size": 28},
            "shop_1": {"x": 1168, "y": 688,  "size": 28},
        }
        self.latest_snapshot   = {}
        self.previous_snapshot = {}
        self.last_snapshot_time = time.time()

        stats = HERO_STATS.get(hero_name, HERO_STATS["Soldier"])

        #Player
        self._hero     = hero_name
        self._px       = float(_TEAM1_SPAWN[0])
        self._py       = float(_TEAM1_SPAWN[1])
        self._speed    = float(stats.get("speed", 110))
        self._hp       = float(stats.get("hp", 400))
        self._max_hp   = float(stats.get("hp", 400))
        self._mana     = float(stats.get("mana", 200))
        self._max_mana = float(stats.get("mana", 200))
        self._atk_dmg  = float(stats.get("attack_damage", 50))
        self._atk_rng  = float(stats.get("attack_range", 120))
        self._gold     = 300

        self._dx = 0
        self._dy = 0

        #Ability cooldowns and state
        self._cd           = {0: 0.0, 1: 0.0, 2: 0.0}
        self._is_invisible = False
        self._invis_timer  = 0.0
        self._is_spinning  = False
        self._spin_timer   = 0.0
        self._is_fortified = False
        self._fortify_timer = 0.0

        #Ground Slam ring VFX
        self._ring_active = False
        self._ring_r      = 0.0
        self._ring_x      = 0.0
        self._ring_y      = 0.0

        #Teleport pulse VFX
        self._pulse_active = False
        self._pulse_r      = 0.0
        self._pulse_x      = 0.0
        self._pulse_y      = 0.0

        #Auto-attack
        self._atk_cd = 0.0

        #Projectiles
        self._projs  = {}   # id → {pos, vx, vy, owner_team, target_id, dmg}
        self._fbs    = {}   # id → {x, y, vx, vy, tx, ty}
        self._bolts  = {}   # id → {x, y, vx, vy, angle, owner_team}
        self._hooks  = {}   # id → {x, y, vx, vy, owner_team, dist}
        self._burns  = {}   # id → {x, y, size, timer}
        self._id_ctr = 0

        #Training dummies
        self._dummies = {
            _DUMMY_IDS[i]: {
                "hp": _DUMMY_HP, "max_hp": _DUMMY_HP,
                "x":  float(pos[0]), "y": float(pos[1]),
                "is_dead": False, "respawn_timer": 0.0,
            }
            for i, pos in enumerate(_DUMMY_POSITIONS)
        }

        self._match_time = 0.0

        self._buildings = self._make_buildings()
        self._rebuild_snap()

    # ── NetworkClient interface ───────────────────────────────────────────────

    async def send_input(self, dx, dy, attack=None, ability=None,
                         ability_target=None, ability_target_id=None):
        self._dx = dx
        self._dy = dy
        if ability is not None:
            self._use_ability(ability, ability_target)

    async def send_buy_item(self, item_name): pass
    async def send_sell_item(self, slot):     pass
    async def send_ready(self):               pass
    async def send_force_start(self):         pass

    def get_interpolated_pos(self, category, entity_id):
        data = self.latest_snapshot.get(category, {}).get(entity_id)
        return list(data["pos"]) if data else None

    def get_interpolated_xy(self, category, entity_id):
        data = self.latest_snapshot.get(category, {}).get(entity_id)
        if not data:
            return None
        if "pos" in data:
            return (data["pos"][0], data["pos"][1])
        return (data["x"], data["y"])

    def get_entity_ids(self, category):
        return list(self.latest_snapshot.get(category, {}).keys())

    # ── Local simulation ──────────────────────────────────────────────────────

    def update(self, dt: float):
        self._match_time += dt
        self._move(dt)
        self._tick_abilities(dt)
        self._tick_attack(dt)
        self._tick_projectiles(dt)
        self._tick_dummies(dt)
        self._rebuild_snap()
        self.last_snapshot_time = time.time()

    def _move(self, dt):
        dx, dy = self._dx, self._dy
        if dx and dy:
            dx *= 0.707
            dy *= 0.707
        self._px = max(8.0, min(MAP_W - 8.0, self._px + dx * self._speed * dt))
        self._py = max(8.0, min(MAP_H - 8.0, self._py + dy * self._speed * dt))

    def _tick_abilities(self, dt):
        for s in self._cd:
            self._cd[s] = max(0.0, self._cd[s] - dt)
        if self._ring_active:
            self._ring_r += 260.0 * dt
            if self._ring_r >= 100.0:
                self._ring_active = False
                self._ring_r = 0.0
        if self._pulse_active:
            self._pulse_r += 280.0 * dt
            if self._pulse_r >= 150.0:
                self._pulse_active = False
                self._pulse_r = 0.0
        if self._is_invisible:
            self._invis_timer -= dt
            if self._invis_timer <= 0:
                self._is_invisible = False
        if self._is_spinning:
            self._spin_timer -= dt
            if self._spin_timer <= 0:
                self._is_spinning = False
        if self._is_fortified:
            self._fortify_timer -= dt
            if self._fortify_timer <= 0:
                self._is_fortified = False

    def _tick_attack(self, dt):
        self._atk_cd = max(0.0, self._atk_cd - dt)
        if self._atk_cd > 0:
            return
        best_id, best_d = None, float("inf")
        for did, dum in self._dummies.items():
            if dum["is_dead"]:
                continue
            d = math.hypot(dum["x"] - self._px, dum["y"] - self._py)
            if d < best_d and d <= self._atk_rng:
                best_id, best_d = did, d
        if not best_id:
            return
        self._atk_cd = 1.0
        dum = self._dummies[best_id]
        ddx, ddy = dum["x"] - self._px, dum["y"] - self._py
        d = math.hypot(ddx, ddy) or 1
        pid = self._nid()
        self._projs[pid] = {
            "pos": [self._px, self._py],
            "vx": ddx / d * 400.0, "vy": ddy / d * 400.0,
            "owner_team": 1, "target_id": best_id, "dmg": self._atk_dmg,
        }

    def _tick_projectiles(self, dt):
        #Auto-attack bullets
        dead = []
        for pid, p in self._projs.items():
            p["pos"][0] += p["vx"] * dt
            p["pos"][1] += p["vy"] * dt
            dum = self._dummies.get(p["target_id"])
            if dum and not dum["is_dead"]:
                if math.hypot(dum["x"] - p["pos"][0], dum["y"] - p["pos"][1]) < 12:
                    self._hurt(p["target_id"], p["dmg"])
                    dead.append(pid)
        for pid in dead:
            del self._projs[pid]

        #Fireballs
        dead = []
        for pid, fb in self._fbs.items():
            fb["x"] += fb["vx"] * dt
            fb["y"] += fb["vy"] * dt
            if math.hypot(fb["tx"] - fb["x"], fb["ty"] - fb["y"]) < 10:
                bid = self._nid()
                self._burns[bid] = {"x": fb["tx"], "y": fb["ty"], "size": 64, "timer": 3.0}
                for did, dum in self._dummies.items():
                    if not dum["is_dead"] and math.hypot(dum["x"] - fb["tx"], dum["y"] - fb["ty"]) < 40:
                        self._hurt(did, 80.0)
                dead.append(pid)
        for pid in dead:
            del self._fbs[pid]

        #Burning areas decay
        for ba in self._burns.values():
            ba["timer"] -= dt
        expired = [bid for bid, ba in self._burns.items() if ba["timer"] <= 0]
        for bid in expired:
            del self._burns[bid]

        #Bolts
        dead = []
        for pid, bp in self._bolts.items():
            bp["x"] += bp["vx"] * dt
            bp["y"] += bp["vy"] * dt
            if not (0 <= bp["x"] <= MAP_W and 0 <= bp["y"] <= MAP_H):
                dead.append(pid)
                continue
            for did, dum in self._dummies.items():
                if not dum["is_dead"] and math.hypot(dum["x"] - bp["x"], dum["y"] - bp["y"]) < 12:
                    self._hurt(did, 120.0)
                    dead.append(pid)
                    break
        for pid in dead:
            self._bolts.pop(pid, None)

        #Hook projectiles (travel up to 320px)
        dead = []
        for pid, hp in self._hooks.items():
            hp["x"] += hp["vx"] * dt
            hp["y"] += hp["vy"] * dt
            hp["dist"] += math.hypot(hp["vx"] * dt, hp["vy"] * dt)
            if hp["dist"] > 320 or not (0 <= hp["x"] <= MAP_W and 0 <= hp["y"] <= MAP_H):
                dead.append(pid)
        for pid in dead:
            self._hooks.pop(pid, None)

    def _hurt(self, did, dmg):
        dum = self._dummies[did]
        dum["hp"] = max(0.0, dum["hp"] - dmg)
        if dum["hp"] == 0:
            dum["is_dead"]       = True
            dum["respawn_timer"] = _DUMMY_RESPAWN

    def _tick_dummies(self, dt):
        for dum in self._dummies.values():
            if dum["is_dead"]:
                dum["respawn_timer"] -= dt
                if dum["respawn_timer"] <= 0:
                    dum["is_dead"] = False
                    dum["hp"]      = dum["max_hp"]
            else:
                dum["hp"] = min(dum["max_hp"], dum["hp"] + _DUMMY_REGEN * dt)

    def _use_ability(self, slot, target):
        if self._cd[slot] > 0:
            return
        hero = self._hero
        match slot:
            case 0:   # Q — fireball
                if not target:
                    return
                tx, ty = float(target[0]), float(target[1])
                ddx, ddy = tx - self._px, ty - self._py
                d = math.hypot(ddx, ddy) or 1
                pid = self._nid()
                self._fbs[pid] = {
                    "x": self._px, "y": self._py,
                    "vx": ddx / d * 350.0, "vy": ddy / d * 350.0,
                    "tx": tx, "ty": ty,
                }
                self._cd[0] = 8.0
            case 1:   # E — slam ring
                self._ring_active = True
                self._ring_r      = 0.0
                self._ring_x      = self._px
                self._ring_y      = self._py
                self._cd[1]       = 10.0
            case 2:   # R — hero-specific
                match hero:
                    case "Rat":
                        self._is_invisible = not self._is_invisible
                        self._invis_timer  = 12.0
                        self._cd[2]        = 15.0
                    case "Mage":
                        if not target:
                            return
                        tx, ty = float(target[0]), float(target[1])
                        self._px           = max(8.0, min(MAP_W - 8.0, tx))
                        self._py           = max(8.0, min(MAP_H - 8.0, ty))
                        self._pulse_active = True
                        self._pulse_r      = 0.0
                        self._pulse_x      = self._px
                        self._pulse_y      = self._py
                        self._cd[2]        = 12.0
                    case "Samurai":
                        self._is_spinning  = True
                        self._spin_timer   = 5.0
                        self._cd[2]        = 16.0
                    case "Hunter":
                        self._is_fortified  = True
                        self._fortify_timer = 3.0
                        self._cd[2]         = 14.0
                    case "Watcher":
                        if not target:
                            return
                        tx, ty = float(target[0]), float(target[1])
                        ddx, ddy = tx - self._px, ty - self._py
                        d = math.hypot(ddx, ddy) or 1
                        pid = self._nid()
                        self._hooks[pid] = {
                            "x": self._px, "y": self._py,
                            "vx": ddx / d * 450.0, "vy": ddy / d * 450.0,
                            "owner_team": 1, "dist": 0.0,
                        }
                        self._cd[2] = 14.0
                    case "Soldier" | _:
                        if not target:
                            return
                        tx, ty = float(target[0]), float(target[1])
                        ddx, ddy = tx - self._px, ty - self._py
                        d = math.hypot(ddx, ddy) or 1
                        angle = math.degrees(math.atan2(-ddy, ddx))
                        pid = self._nid()
                        self._bolts[pid] = {
                            "x": self._px, "y": self._py,
                            "vx": ddx / d * 500.0, "vy": ddy / d * 500.0,
                            "angle": angle, "owner_team": 1,
                        }
                        self._cd[2] = 12.0

    def _rebuild_snap(self):
        abilities = self._make_abilities()
        players = {
            _MY_ID: {
                "hero": self._hero, "team": 1,
                "pos": [self._px, self._py],
                "hp": self._hp, "max_hp": self._max_hp,
                "mana": self._mana, "max_mana": self._max_mana,
                "gold": self._gold,
                "level": 1, "xp": 0,
                "attack_range": self._atk_rng, "vision": 1500,
                "is_dead": False, "is_invisible": self._is_invisible,
                "revealed_timer": 0.0,
                "stun_timer": 0.0, "slow_timer": 0.0,
                "root_timer": 0.0, "bleed_timer": 0.0,
                "bush_idx": -1, "inventory": [None] * 5,
                "kills": 0, "deaths": 0, "assists": 0,
                "abilities": abilities,
            }
        }
        for did, dum in self._dummies.items():
            players[did] = {
                "hero": "Hunter", "team": 2,
                "pos": [dum["x"], dum["y"]],
                "hp": dum["hp"], "max_hp": dum["max_hp"],
                "mana": 0, "max_mana": 0, "gold": 0,
                "level": 1, "xp": 0, "attack_range": 0, "vision": 0,
                "is_dead": dum["is_dead"], "is_invisible": False,
                "revealed_timer": 0.0,
                "stun_timer": 0.0, "slow_timer": 0.0,
                "root_timer": 0.0, "bleed_timer": 0.0,
                "bush_idx": -1, "inventory": [None] * 5, "abilities": [],
            }
        self.previous_snapshot = self.latest_snapshot
        self.latest_snapshot = {
            "game_phase": "live", "winner": None,
            "match_time": self._match_time,
            "players":    players,
            "buildings":  self._buildings,
            "turrets":    {},
            "projectiles": {
                pid: {"pos": list(p["pos"]), "owner_team": p["owner_team"]}
                for pid, p in self._projs.items()
            },
            "fireball_projectiles": {
                pid: {"x": fb["x"], "y": fb["y"]}
                for pid, fb in self._fbs.items()
            },
            "bolt_projectiles": {
                pid: {"x": bp["x"], "y": bp["y"],
                      "angle": bp["angle"], "owner_team": bp["owner_team"]}
                for pid, bp in self._bolts.items()
            },
            "hook_projectiles": {
                pid: {"x": hp["x"], "y": hp["y"], "owner_team": hp["owner_team"]}
                for pid, hp in self._hooks.items()
            },
            "burning_areas": {
                bid: {"x": ba["x"], "y": ba["y"], "size": ba["size"]}
                for bid, ba in self._burns.items()
            },
            "banners": {}, "traps": {},
            "rune": {
                "state": "active", "respawn_timer": 0.0,
                "capture_timer": 0.0, "capturer_team": None,
            },
        }

    def _make_abilities(self):
        _base = {
            "is_on_cooldown": False, "is_placement": False, "is_point_cast": False,
            "is_targeted": False, "is_ally_targeted": False,
            "cast_range": 0, "place_range": 300, "aoe_size": 64,
            "channel_time": 0.0, "channel_timer": 0.0,
            "is_recall": False, "is_channeling": False,
            "slam_radius": 100, "ring_active": False, "ring_radius": 0,
            "ring_x": 0, "ring_y": 0,
            "is_spinning": False, "is_active": False,
            "pulse_active": False, "pulse_x": 0, "pulse_y": 0, "pulse_radius": 0,
            "target_id": None, "true_sight_timer": 0.0,
        }

        q = dict(_base)
        q["name"]           = "Fireball"
        q["is_on_cooldown"] = self._cd[0] > 0
        q["is_placement"]   = True
        q["place_range"]    = 350

        e = dict(_base)
        e["name"]           = "GroundSlam"
        e["is_on_cooldown"] = self._cd[1] > 0
        e["ring_active"]    = self._ring_active
        e["ring_radius"]    = int(self._ring_r)
        e["ring_x"]         = int(self._ring_x)
        e["ring_y"]         = int(self._ring_y)

        r = dict(_base)
        r["is_on_cooldown"] = self._cd[2] > 0
        match self._hero:
            case "Rat":
                r["name"] = "Stealth"
            case "Mage":
                r["name"]         = "Teleport"
                r["is_placement"] = True
                r["place_range"]  = 350
                r["pulse_active"] = self._pulse_active
                r["pulse_x"]      = int(self._pulse_x)
                r["pulse_y"]      = int(self._pulse_y)
                r["pulse_radius"] = int(self._pulse_r)
            case "Samurai":
                r["name"]        = "Spin"
                r["is_spinning"] = self._is_spinning
                r["slam_radius"] = 60
            case "Hunter":
                r["name"]      = "Fortify"
                r["is_active"] = self._is_fortified
            case "Watcher":
                r["name"]         = "Hook"
                r["is_placement"] = True
                r["place_range"]  = 320
            case _:
                r["name"]         = "Bolt"
                r["is_placement"] = True
                r["place_range"]  = 400

        return [q, e, r]

    def _make_buildings(self):
        bld = {}
        bid = 0
        for team, (hx, hy) in ((1, (16, 16)), (2, (1216, 736))):
            bld[str(bid)] = {
                "type": "BuildingHeadquarter", "team": team,
                "x": hx, "y": hy, "size": 48,
                "hp": 2000, "max_hp": 2000,
                "is_destroyed": False, "is_invulnerable": False,
                "vision": 200, "mineral_pool": 1500,
            }
            bid += 1
        for cx, cy in CAPTURE_ZONES:
            bld[str(bid)] = {
                "type": "CapturePoint", "team": 0,
                "x": cx, "y": cy, "size": 32,
                "hp": 200, "max_hp": 200,
                "is_destroyed": False, "is_invulnerable": False,
                "vision": 120, "mineral_pool": 0,
                "capture_timer": 0.0, "capture_time": 5.0, "capturing_team": None,
            }
            bid += 1
        return bld

    def _nid(self) -> str:
        self._id_ctr += 1
        return str(self._id_ctr)
