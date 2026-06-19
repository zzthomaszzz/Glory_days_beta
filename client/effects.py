import pygame


#Radii for the attack-target indicator ring per entity type
_INDICATOR_RADIUS = {
    "player":   18,
    "building": 30,
    "turret":   14,
    "banner":   14,
}

_FLASH_DURATION       = 0.15
_FLOATER_DURATION     = 0.85
_GOLD_FLOATER_DURATION = 1.1
_DEATH_RING_DURATION  = 0.6
_FLOATER_RISE_SPEED   = 38   # pixels per second upward


class EffectsSystem:
    def __init__(self, font_floater):
        #Floating damage / gold text
        self._floaters = []   # {wx, wy, text, color, timer, duration}

        #Per-entity hit-flash (white overlay on damage)
        self._hit_flash = {}   # entity_id -> seconds remaining

        #Death burst rings
        self._death_effects = []   # {wx, wy, timer, duration}

        #Delta tracking — detect HP drops / deaths between snapshots
        self._prev_hp      = {}    # entity_id -> last known hp
        self._prev_is_dead = {}    # entity_id -> bool
        self._prev_gold    = None  # last known gold value for our player

        self._font = font_floater

    def process_snapshot(self, snap, my_id, my_team, is_visible, is_on_screen):
        """Diff current snapshot against previous frame and emit events."""
        for pid, p in snap.get("players", {}).items():
            curr_hp   = p.get("hp", 0)
            curr_dead = p.get("is_dead", False)
            prev_hp   = self._prev_hp.get(pid)
            prev_dead = self._prev_is_dead.get(pid, False)
            wx, wy    = p["pos"]

            is_self = pid == my_id
            visible = is_self or is_visible(wx, wy, entity_id=pid)

            if visible and prev_hp is not None and curr_hp < prev_hp and not curr_dead:
                dmg = round(prev_hp - curr_hp)
                col = (255, 80, 80) if p.get("team") != my_team else (255, 160, 60)
                self._emit_floater(wx, wy - 18, f"-{dmg}", col, _FLOATER_DURATION)
                self._hit_flash[pid] = _FLASH_DURATION

            if not prev_dead and curr_dead:
                self._death_effects.append({
                    "wx": wx, "wy": wy,
                    "timer": _DEATH_RING_DURATION, "duration": _DEATH_RING_DURATION,
                })

            self._prev_hp[pid]      = curr_hp
            self._prev_is_dead[pid] = curr_dead

        # Gold-gain floater near our HQ
        my_p      = snap.get("players", {}).get(my_id, {})
        curr_gold = my_p.get("gold", 0)
        if self._prev_gold is not None and curr_gold > self._prev_gold:
            gain = curr_gold - self._prev_gold
            for b in snap.get("buildings", {}).values():
                if b.get("type") == "BuildingHeadquarter" and b.get("team") == my_team:
                    bx, by = b["x"], b["y"]
                    if is_on_screen(bx, by):
                        self._emit_floater(bx, by - 30, f"+{gain}g", (220, 185, 40), _GOLD_FLOATER_DURATION)
                    break
        self._prev_gold = curr_gold

    def tick(self, dt):
        """Advance all timers and remove expired entries."""
        for f in self._floaters:
            f["timer"] -= dt
        for e in self._death_effects:
            e["timer"] -= dt
        self._floaters      = [f for f in self._floaters      if f["timer"] > 0]
        self._death_effects = [e for e in self._death_effects if e["timer"] > 0]
        self._hit_flash     = {pid: t - dt for pid, t in self._hit_flash.items() if t - dt > 0}

    def draw_hit_flash(self, screen, entity_id, sx, sy, size=32):
        """Overlay a white flash on an entity at screen coords (sx, sy)."""
        flash_t = self._hit_flash.get(entity_id, 0)
        if flash_t <= 0:
            return
        alpha      = int(200 * flash_t / _FLASH_DURATION)
        flash_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        flash_surf.fill((255, 255, 255, alpha))
        screen.blit(flash_surf, (sx - size // 2, sy - size // 2))

    def draw_attack_indicator(self, screen, target_type, target_id, snap, client, vfx_time, w2s):
        """Draw a pulsing ring around the current attack target."""
        pos = _resolve_target_pos(target_type, target_id, snap, client)
        if pos is None:
            return
        ix, iy = w2s(pos[0], pos[1])
        r      = _INDICATOR_RADIUS.get(target_type, 18)

        import math
        pulse = 0.5 + 0.5 * math.sin(vfx_time * 6)
        alpha = int(140 + 80 * pulse)

        surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 200, 60, alpha), (r + 2, r + 2), r, 2)
        screen.blit(surf, (ix - r - 2, iy - r - 2))

    def draw_world_effects(self, screen, w2s, is_on_screen):
        """Render death rings and floating text. Call after all world entities."""
        # Death rings — expand outward and fade
        for eff in self._death_effects:
            t_frac = 1.0 - (eff["timer"] / eff["duration"])
            radius = int(10 + t_frac * 22)
            alpha  = int(200 * (1.0 - t_frac))
            ex, ey = w2s(eff["wx"], eff["wy"])
            if radius > 0 and is_on_screen(eff["wx"], eff["wy"]):
                ring = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ring, (210, 55, 55, alpha), (radius + 2, radius + 2), radius, 2)
                screen.blit(ring, (ex - radius - 2, ey - radius - 2))

        # Damage / gold numbers — rise upward and fade
        for f in self._floaters:
            if not is_on_screen(f["wx"], f["wy"]):
                continue
            elapsed = f["duration"] - f["timer"]
            fx, fy  = w2s(f["wx"], f["wy"])
            fy     -= int(elapsed * _FLOATER_RISE_SPEED)
            alpha   = int(255 * (f["timer"] / f["duration"]))
            txt     = self._font.render(f["text"], True, f["color"])
            txt.set_alpha(alpha)
            screen.blit(txt, txt.get_rect(centerx=fx, centery=fy))

    # -------------------------------------------------------------------------

    def _emit_floater(self, wx, wy, text, color, duration):
        self._floaters.append({
            "wx": wx, "wy": wy,
            "text": text, "color": color,
            "timer": duration, "duration": duration,
        })


def _resolve_target_pos(target_type, target_id, snap, client):
    """Return world (x, y) for a given attack target, or None if gone."""
    match target_type:
        case "player":
            return client.get_interpolated_pos("players", str(target_id))
        case "building":
            b = snap.get("buildings", {}).get(str(target_id))
            if b and not b.get("is_destroyed"):
                bs = b.get("size", 48)
                return b["x"] + bs // 2, b["y"] + bs // 2
        case "turret":
            t = snap.get("turrets", {}).get(str(target_id))
            if t and not t.get("is_destroyed"):
                return t["x"], t["y"]
        case "banner":
            bn = snap.get("banners", {}).get(str(target_id))
            if bn and not bn.get("is_destroyed"):
                return bn["x"], bn["y"]
    return None


def target_is_gone(target_type, target_id, snap):
    """Return True if the attack target no longer exists or is dead/destroyed."""
    match target_type:
        case "player":
            p = snap.get("players", {}).get(str(target_id), {})
            return not p or p.get("is_dead", False)
        case "building":
            b = snap.get("buildings", {}).get(str(target_id), {})
            return not b or b.get("is_destroyed", False)
        case "turret":
            t = snap.get("turrets", {}).get(str(target_id), {})
            return not t or t.get("is_destroyed", False)
        case "banner":
            bn = snap.get("banners", {}).get(str(target_id), {})
            return not bn or bn.get("is_destroyed", False)
    return True
