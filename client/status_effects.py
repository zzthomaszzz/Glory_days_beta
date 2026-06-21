# StatusEffectRenderer: per-player status indicator visuals (stun, slow, root, bleed, etc.)
import math
import pygame


class StatusEffectRenderer:
    def __init__(self, load_asset_fn):
        self._stun_icon = load_asset_fn("stun_icon.png", (12, 12))
        self._slow_icon = load_asset_fn("slow_icon.png", (12, 12))

    def draw(self, screen, p_data, sx, sy, vfx_time):
        """Draw all active status effect indicators for a player at screen coords (sx, sy)."""
        hp     = p_data.get("hp", 1)
        max_hp = max(1, p_data.get("max_hp", 1))

        # ── Root — pulsing green ring ─────────────────────────────────────────
        if p_data.get("root_timer", 0) > 0:
            pulse = 0.5 + 0.5 * math.sin(vfx_time * 6.0)
            r     = int(19 + pulse * 2)
            pygame.draw.circle(screen, (80, 200, 80), (sx, sy), r, 2)

        # ── Armor reduction — orange broken ring ──────────────────────────────
        if p_data.get("armor_reduction_timer", 0) > 0:
            rect = pygame.Rect(sx - 24, sy - 24, 48, 48)
            for i in range(4):
                start = i * (math.pi / 2) + 0.35
                end   = start + (math.pi / 2) - 0.70
                pygame.draw.arc(screen, (220, 120, 30), rect, start, end, 2)

        # ── Being pulled / hooked — fast-pulsing purple ring ─────────────────
        if p_data.get("pull_timer", 0) > 0:
            pulse = 0.5 + 0.5 * math.sin(vfx_time * 14.0)
            r     = int(22 + pulse * 3)
            pygame.draw.circle(screen, (160, 60, 220), (sx, sy), r, 2)

        # ── Bleed — deterministic falling red drops ───────────────────────────
        if p_data.get("bleed_timer", 0) > 0:
            for i in range(3):
                phase  = (vfx_time * 1.8 + i * 0.33) % 1.0
                drop_x = sx + (i - 1) * 5
                drop_y = sy + 8 + int(phase * 18)
                bright = int(220 - 100 * phase)
                pygame.draw.circle(screen, (bright, 15, 15), (drop_x, drop_y), 2)

        # ── Icon row + animated extras ────────────────────────────────────────
        icon_x = sx - 6

        if p_data.get("stun_timer", 0) > 0:
            if self._stun_icon:
                screen.blit(self._stun_icon, (icon_x, sy - 36))
                icon_x += 13
            # 3 yellow stars orbiting the player's head
            for i in range(3):
                angle = vfx_time * 4.0 + i * (2 * math.pi / 3)
                ox = sx + int(14 * math.cos(angle))
                oy = sy - 6 + int(7 * math.sin(angle))
                pygame.draw.circle(screen, (255, 220, 40), (ox, oy), 3)

        if p_data.get("slow_timer", 0) > 0:
            if self._slow_icon:
                screen.blit(self._slow_icon, (icon_x, sy - 36))
                icon_x += 13
            else:
                pygame.draw.circle(screen, (60, 180, 220), (sx, sy), 20, 1)
