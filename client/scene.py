import os
import math
import pygame
import asyncio

from client.net import NetworkClient
from client.map_system import MapSystem
from client.effects import EffectsSystem, target_is_gone
from client.hud import HudRenderer, TEAM_COLOURS, MINI_W, MINI_H, MINI_SX, MINI_SY
from shared.constants import (
    CLIENT_INPUT_INTERVAL, BASE_VISION, TURRET_VISION,
    CLIENT_DEFAULT_HOST, SERVER_PORT, SNAPSHOT_INTERVAL,
    MAP_W, MAP_H,
    RUNE_X, RUNE_Y, RUNE_RADIUS, RUNE_CAPTURE_TIME,
)
from shared.map_data import OBSTACLES, SPAWN_ZONES, BUSHES, CAPTURE_ZONES
from shared.items import ITEMS, ITEM_KEYS

import sys
if getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(sys.executable)   # running as PyInstaller exe
else:
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # running from source

VIEWPORT_W = 640
VIEWPORT_H = 400

# Set by main.py after detecting screen resolution
_SCREEN_W = 1920
_SCREEN_H = 1080
_SCALE_X  = 3.0
_SCALE_Y  = 2.7

# Camera edge scroll
_EDGE_ZONE  = 15
_EDGE_SPEED = 220

HERO_ASSET_MAP = {
    "Soldier": os.path.join(_ROOT, "asset", "soldier.png"),
    "Mage":    os.path.join(_ROOT, "asset", "mage.png"),
    "Hunter":  os.path.join(_ROOT, "asset", "hunter.png"),
    "Samurai": os.path.join(_ROOT, "asset", "samurai.png"),
    "Rat":     os.path.join(_ROOT, "asset", "rat.png"),
    "Player":  os.path.join(_ROOT, "asset", "default_player.png"),
}

_HERO_CARDS = [
    {
        "name":  "Soldier",
        "desc":  "Ranged fighter with precision shots and turret support.",
        "stats": {"HP": 420, "Damage": 75, "Range": 150, "Speed": 115, "Armor": 25},
        "abilities": [
            ("Q", "Snipe",        "Targeted long-range shot"),
            ("E", "Place Turret", "Deploy an auto-attacking turret"),
            ("R", "Dash",         "Dash in your movement direction"),
        ],
    },
    {
        "name":  "Mage",
        "desc":  "Burst caster who excels at area control and healing.",
        "stats": {"HP": 400, "Damage": 30, "Range": 120, "Speed": 110, "Armor": 15},
        "abilities": [
            ("Q", "Fireball",  "Launch a fireball that burns an area"),
            ("E", "Mend",      "Channel to heal a target ally"),
            ("R", "Teleport",  "Channel to teleport to a location"),
        ],
    },
    {
        "name":  "Hunter",
        "desc":  "Tanky melee brawler who charges and stuns enemies.",
        "stats": {"HP": 530, "Damage": 80, "Range": 50, "Speed": 120, "Armor": 40},
        "abilities": [
            ("Q", "Charge",      "Dash to an enemy, stunning them"),
            ("E", "Ground Slam", "AOE slam dealing 50 damage nearby"),
            ("R", "Fortify",     "Gain damage reduction for 5 seconds"),
        ],
    },
    {
        "name":  "Samurai",
        "desc":  "Disciplined melee duelist with crit lifesteal and a healing banner.",
        "stats": {"HP": 480, "Damage": 70, "Range": 60, "Speed": 110, "Armor": 22},
        "abilities": [
            ("Q", "Spin",        "Spin for 5s, dealing 25 dmg every 0.5s in a circle"),
            ("E", "Bushido",     "Passive: 25% crit for 1.4x dmg, heal for damage dealt"),
            ("R", "Place Banner","Deploy a banner healing allies 2% HP/s for 10s (1 HP)"),
        ],
    },
    {
        "name":  "Rat",
        "desc":  "Sneaky ranged assassin who ambushes from stealth and sets deadly traps.",
        "stats": {"HP": 360, "Damage": 50, "Range": 130, "Speed": 130, "Armor": 12},
        "abilities": [
            ("Q", "Stealth",    "Turn invisible for 12s — first attack deals 1.5x damage"),
            ("E", "Place Trap", "Place a trap (max 3) that roots and bleeds enemies for 2s"),
            ("R", "Bolt",       "Fire a slow heavy bolt that breaks on terrain, deals 280 dmg"),
        ],
    },
]


def _hs_layout():
    sw, sh  = _SCREEN_W, _SCREEN_H
    left_w  = sw * 2 // 3
    right_w = sw - left_w

    n       = len(_HERO_CARDS)
    COLS    = 3
    rows    = math.ceil(n / COLS)
    pad     = int(left_w * 0.05)
    gap     = int(left_w * 0.02)
    row_gap = 10

    card_w  = (left_w - 2 * pad - (COLS - 1) * gap) // COLS
    avail_h = int(sh * 0.68)
    card_h  = min(int(sh * 0.50), (avail_h - (rows - 1) * row_gap) // rows)
    card_y  = int(sh * 0.18)

    cards = []
    for i in range(n):
        col              = i % COLS
        row              = i // COLS
        cards_in_row     = min(COLS, n - row * COLS)
        row_x_offset     = (COLS - cards_in_row) * (card_w + gap) // 2
        cx = pad + row_x_offset + col * (card_w + gap)
        cy = card_y + row * (card_h + row_gap)
        cards.append(pygame.Rect(cx, cy, card_w, card_h))

    right_cx = left_w + right_w // 2
    btn_w    = int(right_w * 0.62)
    btn_h    = int(sh * 0.056)
    btn_x    = right_cx - btn_w // 2
    btn_y    = int(sh * 0.88)

    last_card_bottom = card_y + rows * card_h + (rows - 1) * row_gap
    inp_w = int(left_w * 0.32)
    inp_h = int(sh * 0.038)
    inp_x = (left_w - inp_w) // 2
    inp_y = last_card_bottom + int(sh * 0.03)

    return {
        "left_w": left_w, "right_w": right_w,
        "cards": cards, "card_w": card_w, "card_h": card_h,
        "btn_w": btn_w, "btn_h": btn_h, "btn_x": btn_x, "btn_y": btn_y,
        "inp_w": inp_w, "inp_h": inp_h, "inp_x": inp_x, "inp_y": inp_y,
    }


#-------------------------------------------------------------------------------------------------------------------HeroSelect
class SceneHeroSelect:
    def __init__(self):
        self.next_scene    = self
        self.chosen_hero   = None
        self._hovered      = None
        self._server_addr  = f"{CLIENT_DEFAULT_HOST}:{SERVER_PORT}"
        self._addr_focused = False
        self._cursor_timer = 0.0
        self._cursor_vis   = True

        lay = _hs_layout()
        sw, sh = _SCREEN_W, _SCREEN_H
        left_w = lay["left_w"]
        cw, ch = lay["card_w"], lay["card_h"]
        self._left_w = left_w

        self._card_rects_ui = lay["cards"]
        self._btn_rect_ui   = pygame.Rect(lay["btn_x"], lay["btn_y"], lay["btn_w"], lay["btn_h"])
        self._input_rect_ui = pygame.Rect(lay["inp_x"], lay["inp_y"], lay["inp_w"], lay["inp_h"])

        raw_bg = pygame.image.load(os.path.join(_ROOT, "asset", "lobby.png")).convert()
        self._bg_ui      = pygame.transform.smoothscale(raw_bg, (sw, sh))
        self._overlay_ui = pygame.Surface((sw, sh), pygame.SRCALPHA)
        self._overlay_ui.fill((0, 0, 0, 160))

        # Card portraits (big, fill most of card)
        self._portraits_card   = {}
        # Detail panel portraits (medium)
        self._portraits_detail = {}
        port_w  = int(cw * 0.78)
        port_h  = int(ch * 0.62)
        det_sz  = int(lay["right_w"] * 0.42)
        for card in _HERO_CARDS:
            path = HERO_ASSET_MAP.get(card["name"])
            if path and os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self._portraits_card[card["name"]]   = pygame.transform.smoothscale(img, (port_w, port_h))
                self._portraits_detail[card["name"]] = pygame.transform.smoothscale(img, (det_sz, det_sz))

        self._font_title      = pygame.font.SysFont("arial", 44, bold=True)
        self._font_card_name  = pygame.font.SysFont("arial", 20, bold=True)
        self._font_det_name   = pygame.font.SysFont("arial", 32, bold=True)
        self._font_det_desc   = pygame.font.SysFont("arial", 14)
        self._font_stat_lbl   = pygame.font.SysFont("arial", 15)
        self._font_stat_val   = pygame.font.SysFont("arial", 15, bold=True)
        self._font_ab_key     = pygame.font.SysFont("arial", 13, bold=True)
        self._font_ab_name    = pygame.font.SysFont("arial", 14, bold=True)
        self._font_ab_desc    = pygame.font.SysFont("arial", 13)
        self._font_ab_hdr     = pygame.font.SysFont("arial", 14, bold=True)
        self._font_btn        = pygame.font.SysFont("arial", 28, bold=True)
        self._font_hint       = pygame.font.SysFont("arial", 15)
        self._font_addr       = pygame.font.SysFont("arial", 17)

    def process_input(self, events):
        mx, my = pygame.mouse.get_pos()   # raw screen coords → native-res rects
        self._hovered = None
        for i, rect in enumerate(self._card_rects_ui):
            if rect.collidepoint(mx, my):
                self._hovered = i

        for event in events:
            if event.type == pygame.QUIT:
                self.next_scene = None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self._addr_focused:
                        self._addr_focused = False
                    else:
                        self.next_scene = None
                elif self._addr_focused:
                    if event.key == pygame.K_BACKSPACE:
                        self._server_addr = self._server_addr[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._addr_focused = False
                    elif event.unicode and event.unicode.isprintable():
                        self._server_addr += event.unicode
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                ex, ey = event.pos
                self._addr_focused = self._input_rect_ui.collidepoint(ex, ey)
                for i, rect in enumerate(self._card_rects_ui):
                    if rect.collidepoint(ex, ey):
                        self.chosen_hero = _HERO_CARDS[i]["name"]
                if self.chosen_hero and self._btn_rect_ui.collidepoint(ex, ey):
                    self.next_scene = SceneConnecting(self.chosen_hero, self._server_addr)

    def update(self, dt):
        if self._addr_focused:
            self._cursor_timer += dt
            if self._cursor_timer >= 0.5:
                self._cursor_timer = 0.0
                self._cursor_vis = not self._cursor_vis
        else:
            self._cursor_timer = 0.0
            self._cursor_vis   = True

    def render(self, screen):
        screen.fill((0, 0, 0))

    def render_ui(self, ui_surf):
        sw, sh   = _SCREEN_W, _SCREEN_H
        left_w   = self._left_w
        right_x  = left_w
        right_w  = sw - right_x
        right_cx = right_x + right_w // 2

        ui_surf.blit(self._bg_ui, (0, 0))
        ui_surf.blit(self._overlay_ui, (0, 0))

        # Title — full width
        title = self._font_title.render("SELECT YOUR HERO", True, (220, 200, 100))
        ui_surf.blit(title, title.get_rect(centerx=sw // 2, top=int(sh * 0.05)))

        # Vertical divider
        pygame.draw.line(ui_surf, (45, 55, 85), (left_w, int(sh * 0.13)), (left_w, int(sh * 0.96)), 1)

        mx, my = pygame.mouse.get_pos()

        # ── Left 2/3: hero cards ─────────────────────────────────────────
        for i, (card, rect) in enumerate(zip(_HERO_CARDS, self._card_rects_ui)):
            is_selected = self.chosen_hero == card["name"]
            is_hovered  = self._hovered == i

            surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            if is_selected:
                surf.fill((40, 70, 130, 220))
            elif is_hovered:
                surf.fill((50, 55, 80, 200))
            else:
                surf.fill((22, 26, 44, 200))
            ui_surf.blit(surf, rect.topleft)

            border_col = (100, 160, 255) if is_selected else (70, 82, 115) if is_hovered else (40, 48, 74)
            border_w   = 3 if is_selected else 1
            pygame.draw.rect(ui_surf, border_col, rect, border_w, border_radius=8)

            portrait = self._portraits_card.get(card["name"])
            if portrait:
                px = rect.x + (rect.w - portrait.get_width()) // 2
                ui_surf.blit(portrait, (px, rect.y + 10))
                pb = rect.y + 10 + portrait.get_height()
            else:
                pb = rect.y + int(rect.h * 0.62)

            name_s = self._font_card_name.render(card["name"].upper(), True, (230, 230, 240))
            ui_surf.blit(name_s, name_s.get_rect(centerx=rect.centerx, top=pb + 10))

        # ── Right 1/3: detail panel ──────────────────────────────────────
        panel_pad = int(right_w * 0.05)
        panel_x   = right_x + panel_pad
        panel_w   = right_w - 2 * panel_pad
        panel_y   = int(sh * 0.13)
        panel_h   = int(sh * 0.72)

        panel_bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_bg.fill((12, 15, 26, 210))
        ui_surf.blit(panel_bg, (panel_x, panel_y))
        pygame.draw.rect(ui_surf, (45, 58, 90), (panel_x, panel_y, panel_w, panel_h), 1, border_radius=6)

        if self.chosen_hero:
            card    = next(c for c in _HERO_CARDS if c["name"] == self.chosen_hero)
            y       = panel_y + 14

            portrait = self._portraits_detail.get(self.chosen_hero)
            if portrait:
                px = panel_x + (panel_w - portrait.get_width()) // 2
                ui_surf.blit(portrait, (px, y))
                y += portrait.get_height() + 10

            name_s = self._font_det_name.render(card["name"].upper(), True, (220, 200, 100))
            ui_surf.blit(name_s, name_s.get_rect(centerx=panel_x + panel_w // 2, top=y))
            y += name_s.get_height() + 5

            desc_s = self._font_det_desc.render(card["desc"], True, (150, 158, 185))
            ui_surf.blit(desc_s, desc_s.get_rect(centerx=panel_x + panel_w // 2, top=y))
            y += desc_s.get_height() + 10

            pygame.draw.line(ui_surf, (40, 52, 82), (panel_x + 10, y), (panel_x + panel_w - 10, y))
            y += 10

            # Stats (2-column grid)
            stat_items = list(card["stats"].items())
            col_w = panel_w // 2
            for idx, (lbl, val) in enumerate(stat_items):
                col = idx % 2
                row = idx // 2
                sx  = panel_x + col * col_w + 10
                sy  = y + row * 22
                l_s = self._font_stat_lbl.render(f"{lbl}:", True, (120, 130, 165))
                v_s = self._font_stat_val.render(str(val), True, (210, 215, 230))
                ui_surf.blit(l_s, (sx, sy))
                ui_surf.blit(v_s, (sx + l_s.get_width() + 5, sy))
            y += ((len(stat_items) + 1) // 2) * 22 + 10

            pygame.draw.line(ui_surf, (40, 52, 82), (panel_x + 10, y), (panel_x + panel_w - 10, y))
            y += 8

            hdr = self._font_ab_hdr.render("ABILITIES", True, (150, 135, 70))
            ui_surf.blit(hdr, hdr.get_rect(centerx=panel_x + panel_w // 2, top=y))
            y += hdr.get_height() + 8

            for key, name, desc in card["abilities"]:
                key_r = pygame.Rect(panel_x + 8, y + 2, 22, 22)
                pygame.draw.rect(ui_surf, (35, 46, 74), key_r, border_radius=4)
                pygame.draw.rect(ui_surf, (65, 85, 125), key_r, 1, border_radius=4)
                k_s = self._font_ab_key.render(key, True, (190, 205, 235))
                ui_surf.blit(k_s, k_s.get_rect(center=key_r.center))

                n_s = self._font_ab_name.render(name, True, (195, 180, 115))
                ui_surf.blit(n_s, (panel_x + 36, y + 2))
                d_s = self._font_ab_desc.render(desc, True, (120, 128, 155))
                ui_surf.blit(d_s, (panel_x + 36, y + 18))
                y += 40
        else:
            hint = self._font_hint.render("Select a hero to preview", True, (90, 96, 130))
            ui_surf.blit(hint, hint.get_rect(centerx=panel_x + panel_w // 2, centery=panel_y + panel_h // 2))

        # ── LOCK IN button ────────────────────────────────────────────────
        if self.chosen_hero:
            btn_col = (40, 165, 75) if self._btn_rect_ui.collidepoint(mx, my) else (28, 130, 55)
            pygame.draw.rect(ui_surf, btn_col, self._btn_rect_ui, border_radius=10)
            pygame.draw.rect(ui_surf, (60, 220, 100), self._btn_rect_ui, 2, border_radius=10)
            btn_text = self._font_btn.render("LOCK IN", True, (255, 255, 255))
            ui_surf.blit(btn_text, btn_text.get_rect(center=self._btn_rect_ui.center))

        # ── Server address input ──────────────────────────────────────────
        lbl = self._font_addr.render("Server:", True, (140, 148, 175))
        lbl_rect = lbl.get_rect(right=self._input_rect_ui.left - 8, centery=self._input_rect_ui.centery)
        ui_surf.blit(lbl, lbl_rect)

        box_col = (25, 28, 46) if not self._addr_focused else (18, 22, 40)
        rim_col = (100, 160, 255) if self._addr_focused else (52, 62, 92)
        pygame.draw.rect(ui_surf, box_col, self._input_rect_ui, border_radius=6)
        pygame.draw.rect(ui_surf, rim_col, self._input_rect_ui, 2, border_radius=6)

        display = self._server_addr
        if self._addr_focused and self._cursor_vis:
            display += "|"
        addr_surf = self._font_addr.render(display, True, (210, 218, 238))
        ui_surf.blit(addr_surf, addr_surf.get_rect(
            midleft=(self._input_rect_ui.left + 8, self._input_rect_ui.centery)
        ))


#-------------------------------------------------------------------------------------------------------------------Connecting
class SceneConnecting:
    def __init__(self, hero_name, server_addr=None):
        self.next_scene = self
        self._hero_name = hero_name
        self._font = pygame.font.SysFont("arial", 22)
        raw = (server_addr or f"{CLIENT_DEFAULT_HOST}:{SERVER_PORT}").strip()
        if ":" in raw:
            h, _, p = raw.rpartition(":")
            try:
                self._host = h.strip() or CLIENT_DEFAULT_HOST
                self._port = int(p.strip())
            except ValueError:
                self._host, self._port = CLIENT_DEFAULT_HOST, SERVER_PORT
        else:
            self._host = raw or CLIENT_DEFAULT_HOST
            self._port = SERVER_PORT
        self._error = None
        asyncio.create_task(self._connect())

    async def _connect(self):
        try:
            client = NetworkClient(self._host, self._port, SNAPSHOT_INTERVAL)
            await client.connect()
            await client.send_hero_select(self._hero_name)
            asyncio.create_task(client.receive_loop())
            ok = await client.wait_for_welcome()
            if not ok:
                self._error = f"No response from {self._host}:{self._port}\nCheck server is running and address is correct."
                return
            self.next_scene = SceneTest(client)
        except Exception as e:
            self._error = f"Failed to connect: {e}"

    def process_input(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                self.next_scene = None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.next_scene = SceneHeroSelect()

    def update(self, dt): pass

    def render(self, screen):
        screen.fill((8, 10, 18))

    def render_ui(self, ui_surf):
        cx, cy = _SCREEN_W // 2, _SCREEN_H // 2
        if self._error:
            lines = self._error.split("\n")
            for i, line in enumerate(lines):
                col = (220, 80, 80) if i == 0 else (160, 160, 180)
                s = self._font.render(line, True, col)
                ui_surf.blit(s, s.get_rect(center=(cx, cy - 20 + i * 30)))
            hint = self._font.render("Press ESC to go back", True, (100, 100, 120))
            ui_surf.blit(hint, hint.get_rect(center=(cx, cy + 60)))
        else:
            text = self._font.render(f"Connecting to {self._host}:{self._port}...", True, (180, 180, 200))
            ui_surf.blit(text, text.get_rect(center=(cx, cy)))


#-------------------------------------------------------------------------------------------------------------------Base
class SceneBase:
    def __init__(self, client: NetworkClient):
        self.client = client
        self.next_scene = self

    def process_input(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                self.next_scene = None

    def update(self, dt): pass
    def render(self, screen): pass
    def render_ui(self, ui_surf): pass


VISION_BY_TYPE = {
    "BuildingHeadquarter": BASE_VISION,
    "CapturePoint":        BASE_VISION,
    "Turret":              TURRET_VISION,
}

#-------------------------------------------------------------------------------------------------------------------Game
class SceneTest(SceneBase):
    def __init__(self, client):
        super().__init__(client)
        self.dx = 0
        self.dy = 0
        self.input_send_timer = 0.0
        self.map_bg = pygame.image.load(os.path.join(_ROOT, "asset", "map.png")).convert()
        self.map_system = MapSystem(OBSTACLES, SPAWN_ZONES)
        self._prev_building_states = {}
        self._building_vision_dirty = True
        self._last_fog_key = []
        self._pending_attack = None
        self._pending_ability = None
        self._show_range = False
        self._show_debug = False
        self._hero_images = {}

        # Camera
        self.cam_x = 0.0
        self.cam_y = 0.0
        self._cam_locked = True

        # HUD — owns all UI rendering, fonts, minimap, assets
        self.hud = HudRenderer(_SCREEN_W, _SCREEN_H, self._load_asset, OBSTACLES)

        # Turret placement mode
        self._placement_mode   = None   # ability slot index while in placement, else None
        self._ability_target   = None   # (world_x, world_y) pending send

        # Entity targeting mode (e.g. Snipe)
        self._entity_target_mode = None   # ability slot index while selecting target, else None
        self._ability_target_id  = None   # str player_id pending send

        # Shop
        self._shop_open = False

        # Clamped placement cursor (world pos), set each render frame, read in process_input
        self._clamped_placement_pos = None

        # World sprites (pre-scaled to actual in-game sizes)
        self._turret_img  = self._load_asset("turret.png",       (20, 20))
        self._capture_img = self._load_asset("capture_point.png", (32, 32))
        self._hq_imgs     = {
            1: self._load_asset("hq_t1.png", (48, 48)),
            2: self._load_asset("hq_t2.png", (48, 48)),
        }
        self._hq_imgs_cp  = {
            1: self._load_asset("hq_t1.png", (32, 32)),
            2: self._load_asset("hq_t2.png", (32, 32)),
        }

        #Ability / effect sprites
        self._spin_aura_img = self._load_asset("spin_aura.png",  None)       # scaled dynamically per slam_radius
        self._fireball_img  = self._load_asset("fireball.png",   (12, 12))
        self._burn_area_img = self._load_asset("burn_area.png",  (64, 64))   # smoothscaled to actual area size
        self._banner_img    = self._load_asset("banner.png",     (20, 30))
        self._bullet_img    = self._load_asset("bullet.png",     (6,  6))
        self._stun_icon_img = self._load_asset("stun_icon.png",  (12, 12))
        self._slow_icon_img = self._load_asset("slow_icon.png",  (12, 12))
        self._bolt_img      = self._load_asset("bolt.png",       (20, 5))
        self._trap_img      = self._load_asset("trap.png",       (16, 16))

        # Lobby / ready state
        self._my_ready = False

        self._font_floater = pygame.font.SysFont("consolas", 14, bold=True)
        self._font_label   = pygame.font.SysFont("consolas", 10)

        # Visual effects
        self.effects              = EffectsSystem(self._font_floater)
        self._last_proc_snap      = 0.0
        self._local_attack_target = None   # (target_type, target_id) — drives indicator ring
        self._vfx_time            = 0.0    # monotonic clock for pulsing animations

    def _load_asset(self, filename, size=None):
        path = os.path.join(_ROOT, "asset", filename)
        if not os.path.exists(path):
            return None
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        return img

    def _w2s(self, wx, wy):
        return int(wx - self.cam_x), int(wy - self.cam_y)

    def _is_on_screen(self, wx, wy, pad=32):
        return (self.cam_x - pad <= wx <= self.cam_x + VIEWPORT_W + pad and
                self.cam_y - pad <= wy <= self.cam_y + VIEWPORT_H + pad)

    def process_input(self, events):
        super().process_input(events)
        self.dx = 0
        self.dy = 0
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]: self.dx -= 1
        if keys[pygame.K_d]: self.dx += 1
        if keys[pygame.K_w]: self.dy -= 1
        if keys[pygame.K_s]: self.dy += 1

        mini_rect_screen = pygame.Rect(8, _SCREEN_H - MINI_H - 8, MINI_W, MINI_H)

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                sx, sy = event.pos
                if event.button == 3:
                    # Right-click on an inventory slot sells the item
                    _inv_data = self.client.latest_snapshot.get("players", {}).get(
                        self.client.my_player_id, {}).get("inventory", [])
                    _sold = False
                    for _i, _r in enumerate(self.hud.geometry["inventory_rects"]):
                        if _r.collidepoint(sx, sy) and _i < len(_inv_data) and _inv_data[_i]:
                            asyncio.create_task(self.client.send_sell_item(_i))
                            _sold = True
                            break
                    if not _sold:
                        self._placement_mode     = None
                        self._entity_target_mode = None
                elif event.button == 1:
                    # Lobby buttons take priority over all world clicks
                    _snap_ph = self.client.latest_snapshot.get("game_phase", "live")
                    if _snap_ph == "waiting":
                        if self.hud.ready_btn_rect and self.hud.ready_btn_rect.collidepoint(sx, sy) and not self._my_ready:
                            self._my_ready = True
                            asyncio.create_task(self.client.send_ready())
                            continue
                        if self.hud.force_start_rect and self.hud.force_start_rect.collidepoint(sx, sy):
                            asyncio.create_task(self.client.send_force_start())
                            continue
                    if self._entity_target_mode is not None:
                        wx        = sx / _SCALE_X + self.cam_x
                        wy        = sy / _SCALE_Y + self.cam_y
                        snap      = self.client.latest_snapshot
                        abilities = snap.get("players", {}).get(self.client.my_player_id, {}).get("abilities", [])
                        ab        = abilities[self._entity_target_mode] if self._entity_target_mode < len(abilities) else None
                        cast_range  = ab.get("cast_range", 500) if ab else 500
                        ally_mode   = ab.get("is_ally_targeted", False) if ab else False
                        my_pos      = self.client.get_interpolated_pos("players", self.client.my_player_id)
                        for pid, p_data in snap.get("players", {}).items():
                            if pid == self.client.my_player_id or p_data.get("is_dead"):
                                continue
                            same_team = p_data.get("team") == self.client.my_team
                            if ally_mode != same_team:   # ally mode → need same team; enemy mode → need diff team
                                continue
                            pos = self.client.get_interpolated_pos("players", pid)
                            if not pos:
                                continue
                            ddx, ddy = wx - pos[0], wy - pos[1]
                            if ddx*ddx + ddy*ddy > 256:   # 16px hit radius
                                continue
                            if my_pos:
                                rdx, rdy = pos[0] - my_pos[0], pos[1] - my_pos[1]
                                if rdx*rdx + rdy*rdy > cast_range**2:
                                    continue
                            self._pending_ability    = self._entity_target_mode
                            self._ability_target_id  = pid
                            self._entity_target_mode = None
                            break
                    elif self._placement_mode is not None:
                        if self._clamped_placement_pos is not None:
                            wx, wy = self._clamped_placement_pos
                        else:
                            wx = sx / _SCALE_X + self.cam_x
                            wy = sy / _SCALE_Y + self.cam_y
                        self._pending_ability = self._placement_mode
                        self._ability_target  = (wx, wy)
                        self._placement_mode  = None
                    elif self._shop_open and any(r.collidepoint(sx, sy) for r in self.hud.shop_btn_rects):
                        for idx, r in enumerate(self.hud.shop_btn_rects):
                            if r.collidepoint(sx, sy):
                                asyncio.create_task(self.client.send_buy_item(ITEM_KEYS[idx]))
                                break
                    elif self.hud.geometry["shop_rect"].collidepoint(sx, sy):
                        self._shop_open = not self._shop_open
                    elif mini_rect_screen.collidepoint(sx, sy):
                        self._handle_minimap_click(sx - 8, sy - (_SCREEN_H - MINI_H - 8))
                    else:
                        self._handle_click((sx / _SCALE_X, sy / _SCALE_Y))
            if event.type == pygame.KEYDOWN:
                match event.key:
                    case pygame.K_q:      self._handle_ability_key(0)
                    case pygame.K_e:      self._handle_ability_key(1)
                    case pygame.K_r:      self._handle_ability_key(2)
                    case pygame.K_b:      self._handle_ability_key(3)
                    case pygame.K_c:      self._show_range = not self._show_range
                    case pygame.K_h:      self._show_debug = not self._show_debug
                    case pygame.K_SPACE:  self._cam_locked = True
                    case pygame.K_ESCAPE:
                        if self._placement_mode is not None or self._entity_target_mode is not None:
                            self._placement_mode     = None
                            self._entity_target_mode = None
                        else:
                            self.next_scene = None

    def _handle_minimap_click(self, rel_x, rel_y):
        world_x = rel_x / MINI_SX
        world_y = rel_y / MINI_SY
        self.cam_x = max(0.0, min(world_x - VIEWPORT_W / 2, MAP_W - VIEWPORT_W))
        self.cam_y = max(0.0, min(world_y - VIEWPORT_H / 2, MAP_H - VIEWPORT_H))
        self._cam_locked = False

    def _handle_ability_key(self, slot):
        snap      = self.client.latest_snapshot
        my_data   = snap.get("players", {}).get(self.client.my_player_id, {})
        abilities  = my_data.get("abilities", [])
        ability    = abilities[slot] if slot < len(abilities) else None
        if not ability:
            return
        if ability.get("is_placement"):
            self._placement_mode     = None if self._placement_mode == slot else slot
            self._entity_target_mode = None
        elif ability.get("is_targeted"):
            self._entity_target_mode = None if self._entity_target_mode == slot else slot
            self._placement_mode     = None
        else:
            self._pending_ability = slot

    def _is_visible(self, x, y, entity_id=None):
        node = self.map_system.get_node_from_pos(x, y)
        if node.discovered or node.building_vision:
            return True
        if entity_id is not None:
            my_data = self.client.latest_snapshot.get("players", {}).get(self.client.my_player_id, {})
            for ab in my_data.get("abilities", []):
                if ab and ab.get("true_sight_timer", 0) > 0 and str(ab.get("target_id")) == str(entity_id):
                    return True
        return False

    def _set_attack_target(self, target_type, target_id):
        self._pending_attack      = (target_type, target_id)
        self._local_attack_target = (target_type, target_id)

    def _handle_click(self, viewport_pos):
        snap = self.client.latest_snapshot
        wx = viewport_pos[0] + self.cam_x
        wy = viewport_pos[1] + self.cam_y

        for bid, b in snap.get("buildings", {}).items():
            if b.get("is_destroyed") or b.get("team") == 0 or b.get("team") == self.client.my_team:
                continue
            if not self._is_visible(b["x"], b["y"]):
                continue
            if pygame.Rect(b["x"], b["y"], b["size"], b["size"]).collidepoint(wx, wy):
                self._set_attack_target("building", bid)
                return

        for pid, p in snap.get("players", {}).items():
            if pid == self.client.my_player_id:
                continue
            pos = self.client.get_interpolated_pos("players", pid)
            if pos:
                if not self._is_visible(pos[0], pos[1]):
                    continue
                if p.get("is_invisible") and not p.get("revealed_timer", 0) > 0:
                    continue
                dx, dy = wx - pos[0], wy - pos[1]
                if dx*dx + dy*dy <= 64:
                    self._set_attack_target("player", pid)
                    return

        for tid, t in snap.get("turrets", {}).items():
            if t.get("is_destroyed") or t.get("team") == self.client.my_team:
                continue
            if not self._is_visible(t["x"], t["y"]):
                continue
            half = t.get("size", 20) / 2
            dx, dy = wx - t["x"], wy - t["y"]
            if abs(dx) <= half and abs(dy) <= half:
                self._set_attack_target("turret", tid)
                return

        for bid, b in snap.get("banners", {}).items():
            if b.get("is_destroyed") or b.get("team") == self.client.my_team:
                continue
            if not self._is_visible(b["x"], b["y"]):
                continue
            half = b.get("size", 20) / 2
            dx, dy = wx - b["x"], wy - b["y"]
            if abs(dx) <= half and abs(dy) <= half:
                self._set_attack_target("banner", bid)
                return

    def update(self, dt):
        super().update(dt)
        self.input_send_timer += dt
        if self.input_send_timer >= CLIENT_INPUT_INTERVAL:
            self.input_send_timer = 0.0
            attack             = self._pending_attack
            ability            = self._pending_ability
            ability_target     = self._ability_target
            ability_target_id  = self._ability_target_id
            self._pending_attack    = None
            self._pending_ability   = None
            self._ability_target    = None
            self._ability_target_id = None
            # Mirror server's movement-cancels-attack rule so the indicator clears too
            if attack is None and (self.dx != 0 or self.dy != 0):
                self._local_attack_target = None
            asyncio.create_task(
                self.client.send_input(self.dx, self.dy, attack, ability, ability_target, ability_target_id)
            )

        snap = self.client.latest_snapshot
        buildings = snap.get("buildings", {})
        for bid, b in buildings.items():
            state = (b.get("is_destroyed"), b.get("team"))
            if self._prev_building_states.get(bid) != state:
                self._building_vision_dirty = True
                self._prev_building_states[bid] = state

        if self._building_vision_dirty:
            my_team = self.client.my_team
            sources = []
            for b in buildings.values():
                if not b.get("is_destroyed") and b.get("team") == my_team:
                    node = self.map_system.get_node_from_pos(b["x"], b["y"])
                    vision = VISION_BY_TYPE.get(b.get("type"), BASE_VISION)
                    sources.append((node, vision))
            self.map_system.compute_building_vision(sources)
            self._building_vision_dirty = False
            self.hud.mark_fog_dirty()

        my_team = self.client.my_team
        all_sources = []
        for pid in self.client.get_entity_ids("players"):
            p_data = snap.get("players", {}).get(pid, {})
            if p_data.get("team") != my_team:
                continue
            pos = self.client.get_interpolated_pos("players", pid)
            if pos and not p_data.get("is_dead"):
                node = self.map_system.get_node_from_pos(pos[0], pos[1])
                all_sources.append((node, p_data.get("vision", 150)))

        for t in snap.get("turrets", {}).values():
            if t.get("team") == my_team and not t.get("is_destroyed"):
                node = self.map_system.get_node_from_pos(t["x"], t["y"])
                all_sources.append((node, t.get("vision", 240)))

        for bn in snap.get("banners", {}).values():
            if bn.get("team") == my_team and not bn.get("is_destroyed"):
                node = self.map_system.get_node_from_pos(bn["x"], bn["y"])
                all_sources.append((node, bn.get("vision", 130)))

        fog_key = [(id(node), vision) for node, vision in all_sources]
        if fog_key != self._last_fog_key:
            self.map_system.handle_fog(all_sources)
            self._last_fog_key = fog_key
            self.hud.mark_fog_dirty()

        self.hud.rebuild_fog_if_dirty(self.map_system)

        # Edge scroll
        smx, smy = pygame.mouse.get_pos()
        mx = smx / _SCALE_X
        my = smy / _SCALE_Y
        scrolling = False
        if mx < _EDGE_ZONE:
            self.cam_x -= _EDGE_SPEED * dt; scrolling = True
        elif mx > VIEWPORT_W - _EDGE_ZONE:
            self.cam_x += _EDGE_SPEED * dt; scrolling = True
        if my < _EDGE_ZONE:
            self.cam_y -= _EDGE_SPEED * dt; scrolling = True
        elif my > VIEWPORT_H - _EDGE_ZONE:
            self.cam_y += _EDGE_SPEED * dt; scrolling = True

        if scrolling:
            self._cam_locked = False
            self.cam_x = max(0.0, min(self.cam_x, MAP_W - VIEWPORT_W))
            self.cam_y = max(0.0, min(self.cam_y, MAP_H - VIEWPORT_H))
        elif self._cam_locked:
            my_pos = self.client.get_interpolated_pos("players", self.client.my_player_id)
            if my_pos:
                self.cam_x = max(0.0, min(my_pos[0] - VIEWPORT_W / 2, MAP_W - VIEWPORT_W))
                self.cam_y = max(0.0, min(my_pos[1] - VIEWPORT_H / 2, MAP_H - VIEWPORT_H))

        # Process new snapshot for HP/gold diffs
        if self.client.last_snapshot_time != self._last_proc_snap:
            self._last_proc_snap = self.client.last_snapshot_time
            self.effects.process_snapshot(snap, self.client.my_player_id, self.client.my_team,
                                          self._is_visible, self._is_on_screen)

        # Clear indicator if the target has died or been destroyed
        if self._local_attack_target:
            ttype, tid = self._local_attack_target
            if target_is_gone(ttype, tid, snap):
                self._local_attack_target = None

        self.effects.tick(dt)
        self._vfx_time += dt

    def _get_hero_image(self, hero_name):
        if hero_name not in self._hero_images:
            path = HERO_ASSET_MAP.get(hero_name)
            if path and os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self._hero_images[hero_name] = pygame.transform.smoothscale(img, (32, 32))
            else:
                self._hero_images[hero_name] = None
        return self._hero_images[hero_name]

    def render(self, screen):
        screen.blit(self.map_bg, (-int(self.cam_x), -int(self.cam_y)))

        snap    = self.client.latest_snapshot
        my_team = self.client.my_team
        my_data = snap.get("players", {}).get(self.client.my_player_id, {})

        for b in snap.get("buildings", {}).values():
            if b.get("is_destroyed"):
                continue
            btype = b.get("type", "")
            bx, by, bs = b["x"], b["y"], b["size"]
            if btype == "CapturePoint":
                self._draw_capture_point(screen, b)
                continue
            if b.get("team") != my_team and not self._is_visible(bx, by):
                continue
            sx, sy = self._w2s(bx, by)
            hq_img = self._hq_imgs.get(b.get("team")) if btype == "BuildingHeadquarter" else None
            if hq_img:
                screen.blit(hq_img, (sx, sy))
            else:
                depleted = b.get("mineral_pool", 1) == 0
                col = (80, 80, 80) if depleted else TEAM_COLOURS.get(b["team"], (180, 180, 180))
                pygame.draw.rect(screen, col, (sx, sy, bs, bs))
            if b["hp"] < b["max_hp"]:
                self._draw_hp_bar(screen, sx, sy - 8, bs, b["hp"], b["max_hp"])

        # ── Attrition rune ───────────────────────────────────────────────────
        rune = snap.get("rune", {})
        rune_state = rune.get("state", "inactive")
        if rune_state != "inactive":
            rx, ry = self._w2s(RUNE_X, RUNE_Y)
            if rune_state == "cooldown":
                pygame.draw.circle(screen, (60, 55, 80), (rx, ry), 14, 2)
                cd_s = self._font_label.render(f"{rune.get('respawn_timer', 0):.0f}s", True, (130, 120, 160))
                screen.blit(cd_s, cd_s.get_rect(centerx=rx, top=ry + 17))
            else:
                pygame.draw.circle(screen, (140, 60, 200), (rx, ry), 16, 3)
                pygame.draw.circle(screen, (200, 130, 255), (rx, ry), 7)
                if rune_state == "capturing":
                    t       = rune.get("capture_timer", 0)
                    prog    = min(t / max(RUNE_CAPTURE_TIME, 0.001), 1.0)
                    c_team  = rune.get("capturer_team")
                    arc_col = TEAM_COLOURS.get(c_team, (200, 200, 200))
                    start_a = math.pi / 2
                    end_a   = start_a - prog * 2 * math.pi
                    pygame.draw.arc(screen, arc_col,
                                    pygame.Rect(rx - 22, ry - 22, 44, 44),
                                    min(start_a, end_a), max(start_a, end_a), 3)
            lbl_s = self._font_label.render("RUNE", True, (180, 120, 230))
            screen.blit(lbl_s, lbl_s.get_rect(centerx=rx, bottom=ry - 18))

        # ── Bushes ───────────────────────────────────────────────────────────
        for bush in BUSHES:
            bsx, bsy = self._w2s(bush.x, bush.y)
            bsw, bsh = bush.width, bush.height
            _b = pygame.Surface((bsw, bsh), pygame.SRCALPHA)
            _b.fill((30, 110, 30, 120))
            screen.blit(_b, (bsx, bsy))
            pygame.draw.rect(screen, (20, 80, 20), (bsx, bsy, bsw, bsh), 2)

        for pid in self.client.get_entity_ids("players"):
            pos = self.client.get_interpolated_pos("players", pid)
            if not pos:
                continue
            p_data = snap.get("players", {}).get(pid, {})
            if p_data.get("is_dead"):
                continue
            if p_data.get("team") != my_team and not self._is_visible(pos[0], pos[1], entity_id=pid):
                continue
            is_invisible  = p_data.get("is_invisible", False)
            is_revealed   = p_data.get("revealed_timer", 0) > 0
            enemy         = p_data.get("team") != my_team
            # Hidden from enemies unless revealed by true sight
            if is_invisible and enemy and not is_revealed:
                continue
            # Bush vision — enemies in a bush are hidden unless we share that bush
            if enemy and not is_revealed:
                enemy_bush = p_data.get("bush_idx", -1)
                my_bush    = my_data.get("bush_idx", -1)
                if enemy_bush >= 0 and enemy_bush != my_bush:
                    continue
            sx, sy = self._w2s(pos[0], pos[1])
            abilities = p_data.get("abilities", [])
            # Fade own-team invisible players to 50% alpha
            if is_invisible and not enemy:
                _ghost = pygame.Surface((32, 32), pygame.SRCALPHA)
                _ghost.fill((150, 100, 200, 110))
                screen.blit(_ghost, (sx - 16, sy - 16))

            #Spin aura (below hero so it renders behind the sprite)
            spinning = any(ab and ab.get("name") == "Spin" and ab.get("is_spinning") for ab in abilities)
            if spinning:
                slam_r = next((ab.get("slam_radius", 80) for ab in abilities if ab and ab.get("name") == "Spin"), 80)
                if self._spin_aura_img:
                    angle   = (self._vfx_time * 60) % 360
                    scale   = slam_r / 80.0
                    rotated = pygame.transform.rotozoom(self._spin_aura_img, angle, scale)
                    rw, rh  = rotated.get_size()
                    screen.blit(rotated, (sx - rw // 2, sy - rh // 2))
                else:
                    pygame.draw.circle(screen, (220, 180, 40), (sx, sy), slam_r, 2)
                    spin_surf = pygame.Surface((slam_r * 2, slam_r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(spin_surf, (220, 180, 40, 30), (slam_r, slam_r), slam_r)
                    screen.blit(spin_surf, (sx - slam_r, sy - slam_r))

            #Fortify aura
            fortified = any(ab and ab.get("name") == "Fortify" and ab.get("is_active") for ab in abilities)
            if fortified:
                pygame.draw.circle(screen, (80, 160, 220), (sx, sy), 18, 2)

            #Teleport pulse ring — expands outward after teleport
            tele_ab_pulse = next((ab for ab in abilities
                                  if ab and ab.get("name") == "Teleport"
                                  and ab.get("pulse_active")), None)
            if tele_ab_pulse:
                pr    = int(tele_ab_pulse["pulse_radius"])
                px, py = self._w2s(tele_ab_pulse["pulse_x"], tele_ab_pulse["pulse_y"])
                if pr > 1:
                    pulse_surf = pygame.Surface((pr * 2 + 4, pr * 2 + 4), pygame.SRCALPHA)
                    alpha      = int(220 * (1.0 - tele_ab_pulse["pulse_radius"] / 150.0))
                    pygame.draw.circle(pulse_surf, (180, 120, 255, alpha),
                                       (pr + 2, pr + 2), pr, 3)
                    screen.blit(pulse_surf, (px - pr - 2, py - pr - 2))

            #GroundSlam ring — expands outward from slam origin
            slam_ab = next((ab for ab in abilities
                            if ab and ab.get("name") == "GroundSlam"
                            and ab.get("ring_active")), None)
            if slam_ab:
                sr     = int(slam_ab["ring_radius"])
                sr_max = slam_ab.get("slam_radius", 100)
                sx2, sy2 = self._w2s(slam_ab["ring_x"], slam_ab["ring_y"])
                if sr > 1:
                    ring_surf = pygame.Surface((sr * 2 + 6, sr * 2 + 6), pygame.SRCALPHA)
                    alpha     = int(255 * (1.0 - sr / max(sr_max, 1)))
                    pygame.draw.circle(ring_surf, (255, 200, 60, alpha),
                                       (sr + 3, sr + 3), sr, 4)
                    screen.blit(ring_surf, (sx2 - sr - 3, sy2 - sr - 3))

            #Teleport channel arc — shrinks as channel completes
            tele_ab = next((ab for ab in abilities
                            if ab and ab.get("name") == "Teleport" and ab.get("is_channeling")), None)
            if tele_ab:
                progress  = tele_ab["channel_timer"] / max(tele_ab["channel_time"], 0.001)
                arc_angle = 2 * math.pi * progress
                r = 20
                pygame.draw.circle(screen, (40, 40, 90), (sx, sy), r, 1)
                if arc_angle > 0.05:
                    pygame.draw.arc(screen, (160, 200, 255),
                                    pygame.Rect(sx - r, sy - r, r * 2, r * 2),
                                    math.pi / 2, math.pi / 2 + arc_angle, 3)

            #Recall channel arc — fills clockwise from top as channel completes
            recall_ab = next((ab for ab in abilities
                              if ab and ab.get("is_recall") and ab.get("is_channeling")), None)
            if recall_ab:
                elapsed   = recall_ab["channel_time"] - recall_ab["channel_timer"]
                progress  = elapsed / max(recall_ab["channel_time"], 0.001)
                arc_angle = 2 * math.pi * progress
                r = 22
                pygame.draw.circle(screen, (10, 40, 80), (sx, sy), r, 1)
                if arc_angle > 0.05:
                    end_a = math.pi / 2
                    pygame.draw.arc(screen, (80, 180, 255),
                                    pygame.Rect(sx - r, sy - r, r * 2, r * 2),
                                    end_a - arc_angle, end_a, 3)

            #Hero sprite
            hero = p_data.get("hero", "Player")
            img  = self._get_hero_image(hero)
            if img:
                screen.blit(img, (sx - 16, sy - 16))
            else:
                pygame.draw.circle(screen, TEAM_COLOURS.get(p_data.get("team"), (255, 255, 255)), (sx, sy), 8)

            self.effects.draw_hit_flash(screen, pid, sx, sy)

            self._draw_hp_bar(screen, sx - 15, sy - 20, 30, p_data.get("hp", 1), p_data.get("max_hp", 1))

            #Class label above HP bar
            lbl_surf = self._font_label.render(hero[:3].upper(), True,
                                               TEAM_COLOURS.get(p_data.get("team"), (200, 200, 200)))
            screen.blit(lbl_surf, lbl_surf.get_rect(centerx=sx, bottom=sy - 22))

            #Status icons (stun / slow) above the name label
            icon_x = sx - 6
            if p_data.get("stun_timer", 0) > 0:
                if self._stun_icon_img:
                    screen.blit(self._stun_icon_img, (icon_x, sy - 36))
                    icon_x += 13
                else:
                    pygame.draw.circle(screen, (240, 200, 40), (sx, sy), 20, 2)
            if p_data.get("slow_timer", 0) > 0:
                if self._slow_icon_img:
                    screen.blit(self._slow_icon_img, (icon_x, sy - 36))
                    icon_x += 13
                else:
                    pygame.draw.circle(screen, (60, 180, 220), (sx, sy), 20, 1)
            if p_data.get("root_timer", 0) > 0:
                pygame.draw.circle(screen, (80, 200, 80), (sx, sy), 20, 2)
            if p_data.get("bleed_timer", 0) > 0:
                pygame.draw.circle(screen, (200, 30, 30), (sx, sy - 4), 3)

        for t in snap.get("turrets", {}).values():
            if t.get("is_destroyed"):
                continue
            tx, ty = t["x"], t["y"]
            if t.get("team") != my_team and not self._is_visible(tx, ty):
                continue
            tsx, tsy = self._w2s(tx, ty)
            sz = t.get("size", 20)
            if self._turret_img:
                screen.blit(self._turret_img, (tsx - sz // 2, tsy - sz // 2))
            else:
                col = TEAM_COLOURS.get(t.get("team"), (180, 180, 180))
                pts = [
                    (tsx,          tsy - sz // 2),
                    (tsx + sz // 2, tsy),
                    (tsx,          tsy + sz // 2),
                    (tsx - sz // 2, tsy),
                ]
                pygame.draw.polygon(screen, col, pts)
                pygame.draw.polygon(screen, (200, 200, 210), pts, 1)
            if t.get("hp", t.get("max_hp", 1)) < t.get("max_hp", 1):
                self._draw_hp_bar(screen, tsx - sz // 2, tsy - sz // 2 - 6, sz, t.get("hp", 0), t.get("max_hp", 1))

        for shop in snap.get("shops", {}).values():
            sx, sy = self._w2s(shop["x"], shop["y"])
            sz = shop["size"]
            pygame.draw.rect(screen, (140, 105, 20), (sx, sy, sz, sz))
            pygame.draw.rect(screen, (220, 180, 50), (sx, sy, sz, sz), 2)
            lbl = self._font_label.render("$", True, (255, 230, 80))
            screen.blit(lbl, lbl.get_rect(center=(sx + sz // 2, sy + sz // 2)))

        for pid, proj in snap.get("projectiles", {}).items():
            pos = self.client.get_interpolated_xy("projectiles", pid)
            if pos is None:
                continue
            sx, sy = self._w2s(pos[0], pos[1])
            if self._bullet_img:
                screen.blit(self._bullet_img, (sx - 3, sy - 3))
            else:
                col = TEAM_COLOURS.get(proj.get("owner_team"), (255, 255, 200))
                pygame.draw.rect(screen, col, (sx - 2, sy - 2, 4, 4))

        for pid, fp in snap.get("fireball_projectiles", {}).items():
            pos = self.client.get_interpolated_xy("fireball_projectiles", pid)
            if pos is None:
                continue
            sx, sy = self._w2s(pos[0], pos[1])
            if self._fireball_img:
                screen.blit(self._fireball_img, self._fireball_img.get_rect(center=(sx, sy)))
            else:
                pygame.draw.circle(screen, (255, 140, 20), (sx, sy), 5)
                pygame.draw.circle(screen, (255, 220, 80), (sx, sy), 2)

        for ba in snap.get("burning_areas", {}).values():
            half = ba["size"] // 2
            bx, by = self._w2s(ba["x"] - half, ba["y"] - half)
            sz = ba["size"]
            if self._burn_area_img:
                scaled = pygame.transform.smoothscale(self._burn_area_img, (sz, sz))
                screen.blit(scaled, (bx, by))
            else:
                fire_surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
                fire_surf.fill((220, 70, 10, 100))
                screen.blit(fire_surf, (bx, by))
                pygame.draw.rect(screen, (255, 120, 30), (bx, by, sz, sz), 1)

        for bn in snap.get("banners", {}).values():
            if bn.get("is_destroyed"):
                continue
            bx, by = bn["x"], bn["y"]
            if bn.get("team") != my_team and not self._is_visible(bx, by):
                continue
            sx, sy = self._w2s(bx, by)
            team_col = TEAM_COLOURS.get(bn.get("team"), (180, 180, 180))
            #Friendly banners show heal aura
            if bn.get("team") == my_team:
                heal_r    = 100
                aura_surf = pygame.Surface((heal_r * 2, heal_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(aura_surf, (60, 220, 100, 28), (heal_r, heal_r), heal_r)
                screen.blit(aura_surf, (sx - heal_r, sy - heal_r))
                pygame.draw.circle(screen, (60, 220, 100), (sx, sy), heal_r, 1)
            #Banner sprite or shape fallback
            if self._banner_img:
                bw, bh = self._banner_img.get_size()
                screen.blit(self._banner_img, (sx - bw // 2, sy - bh + 8))
                #Small team-color stripe over the flag area
                pygame.draw.rect(screen, team_col, (sx, sy - bh + 8, 7, 5))
            else:
                pygame.draw.line(screen, (180, 160, 120), (sx, sy + 8), (sx, sy - 16), 2)
                pygame.draw.polygon(screen, team_col, [(sx, sy - 16), (sx + 10, sy - 11), (sx, sy - 6)])
                pygame.draw.polygon(screen, (200, 200, 200), [(sx, sy - 16), (sx + 10, sy - 11), (sx, sy - 6)], 1)
            #Duration timer
            dur_s = self._font_label.render(f"{bn.get('duration', 0):.0f}s", True, (200, 230, 200))
            screen.blit(dur_s, dur_s.get_rect(centerx=sx, bottom=sy + 8))

        #Traps — only render allied traps
        for trap in snap.get("traps", {}).values():
            if trap.get("team") != my_team:
                continue
            tx, ty = self._w2s(trap["x"], trap["y"])
            half = trap.get("size", 16) // 2
            if self._trap_img:
                screen.blit(self._trap_img, (tx - half, ty - half))
            else:
                pygame.draw.rect(screen, (160, 120, 20), (tx - half, ty - half, half * 2, half * 2))
                pygame.draw.rect(screen, (220, 180, 40), (tx - half, ty - half, half * 2, half * 2), 1)

        #Bolt projectiles — slow rotating sprite
        for bp in snap.get("bolt_projectiles", {}).values():
            bx, by = self._w2s(bp["x"], bp["y"])
            angle  = bp.get("angle", 0)
            if self._bolt_img:
                rotated = pygame.transform.rotate(self._bolt_img, angle)
                screen.blit(rotated, rotated.get_rect(center=(bx, by)))
            else:
                team_col = TEAM_COLOURS.get(bp.get("owner_team"), (200, 200, 100))
                pygame.draw.rect(screen, team_col, (bx - 10, by - 2, 20, 4))

        # Turret placement mode overlay
        if self._placement_mode is not None:
            snap      = self.client.latest_snapshot
            my_data   = snap.get("players", {}).get(self.client.my_player_id, {})
            abilities  = my_data.get("abilities", [])
            ability    = abilities[self._placement_mode] if self._placement_mode < len(abilities) else None
            place_range = ability.get("place_range", 50) if ability else 50

            my_pos = self.client.get_interpolated_pos("players", self.client.my_player_id)
            smx, smy = pygame.mouse.get_pos()
            wx = smx / _SCALE_X + self.cam_x
            wy = smy / _SCALE_Y + self.cam_y

            # Clamp world cursor to place_range radius
            if my_pos:
                ddx = wx - my_pos[0]
                ddy = wy - my_pos[1]
                dist_sq = ddx * ddx + ddy * ddy
                if dist_sq > place_range ** 2:
                    dist = math.sqrt(dist_sq)
                    wx = my_pos[0] + ddx / dist * place_range
                    wy = my_pos[1] + ddy / dist * place_range
            self._clamped_placement_pos = (wx, wy)

            cx, cy = self._w2s(wx, wy)

            if my_pos:
                px_v, py_v = self._w2s(my_pos[0], my_pos[1])
                pygame.draw.circle(screen, (80, 80, 90), (px_v, py_v), int(place_range), 1)

            aoe_size = ability.get("aoe_size") if ability else None
            if aoe_size:
                half = aoe_size // 2
                aoe_surf = pygame.Surface((aoe_size, aoe_size), pygame.SRCALPHA)
                aoe_surf.fill((220, 90, 20, 70))
                screen.blit(aoe_surf, (cx - half, cy - half))
                pygame.draw.rect(screen, (255, 140, 30), (cx - half, cy - half, aoe_size, aoe_size), 2)
            else:
                # PlaceTurret: attack range ring + diamond indicator
                pygame.draw.circle(screen, (60, 200, 80), (cx, cy), 150, 1)
                half = 8
                pts  = [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)]
                pygame.draw.polygon(screen, (60, 200, 80), pts, 2)
        else:
            self._clamped_placement_pos = None

        # Entity targeting mode overlay (Snipe = enemy, Mend = ally)
        if self._entity_target_mode is not None:
            abilities  = snap.get("players", {}).get(self.client.my_player_id, {}).get("abilities", [])
            ab         = abilities[self._entity_target_mode] if self._entity_target_mode < len(abilities) else None
            cast_range = ab.get("cast_range", 500) if ab else 500
            ally_mode  = ab.get("is_ally_targeted", False) if ab else False
            my_pos     = self.client.get_interpolated_pos("players", self.client.my_player_id)

            ring_col = (60, 90, 60) if ally_mode else (90, 60, 60)
            if my_pos:
                px_v, py_v = self._w2s(my_pos[0], my_pos[1])
                pygame.draw.circle(screen, ring_col, (px_v, py_v), int(cast_range), 1)

            for pid, p_data in snap.get("players", {}).items():
                if pid == self.client.my_player_id or p_data.get("is_dead"):
                    continue
                same_team = p_data.get("team") == my_team
                if ally_mode != same_team:
                    continue
                pos = self.client.get_interpolated_pos("players", pid)
                if not pos:
                    continue
                if not ally_mode and not self._is_visible(pos[0], pos[1], entity_id=pid):
                    continue
                if my_pos:
                    ddx, ddy = pos[0] - my_pos[0], pos[1] - my_pos[1]
                    in_range = ddx*ddx + ddy*ddy <= cast_range**2
                else:
                    in_range = True
                if ally_mode:
                    col = (50, 220, 100) if in_range else (30, 100, 50)
                else:
                    col = (220, 50, 50) if in_range else (100, 50, 50)
                ex, ey = self._w2s(pos[0], pos[1])
                pygame.draw.circle(screen, col, (ex, ey), 14, 2)
                pygame.draw.line(screen, col, (ex - 18, ey), (ex - 10, ey), 1)
                pygame.draw.line(screen, col, (ex + 10, ey), (ex + 18, ey), 1)
                pygame.draw.line(screen, col, (ex, ey - 18), (ex, ey - 10), 1)
                pygame.draw.line(screen, col, (ex, ey + 10), (ex, ey + 18), 1)

        # Crosshair on own hero when being targeted by an enemy Snipe
        if my_data.get("is_targeted"):
            my_pos = self.client.get_interpolated_pos("players", self.client.my_player_id)
            if my_pos and not my_data.get("is_dead"):
                tx, ty = self._w2s(my_pos[0], my_pos[1])
                pygame.draw.circle(screen, (220, 50, 50), (tx, ty), 14, 2)
                pygame.draw.line(screen, (220, 50, 50), (tx - 18, ty), (tx - 10, ty), 1)
                pygame.draw.line(screen, (220, 50, 50), (tx + 10, ty), (tx + 18, ty), 1)
                pygame.draw.line(screen, (220, 50, 50), (tx, ty - 18), (tx, ty - 10), 1)
                pygame.draw.line(screen, (220, 50, 50), (tx, ty + 10), (tx, ty + 18), 1)

        if self._show_range:
            my_id = self.client.my_player_id
            pos   = self.client.get_interpolated_pos("players", my_id)
            rng   = snap.get("players", {}).get(my_id, {}).get("attack_range", 300)
            if pos:
                sx, sy = self._w2s(pos[0], pos[1])
                pygame.draw.circle(screen, (200, 200, 80), (sx, sy), int(rng), 1)

        # Attack target indicator — pulsing ring on current auto-attack target
        if self._local_attack_target:
            ttype, tid = self._local_attack_target
            self.effects.draw_attack_indicator(
                screen, ttype, tid, snap, self.client, self._vfx_time, self._w2s,
            )

        self.effects.draw_world_effects(screen, self._w2s, self._is_on_screen)

        # ── H key debug overlay ───────────────────────────────────────────────
        if self._show_debug:
            dbg_font = pygame.font.SysFont("monospace", 11, bold=True)
            for obs in OBSTACLES:
                ox, oy = self._w2s(obs.x, obs.y)
                ow, oh = obs.width, obs.height
                _s = pygame.Surface((ow, oh), pygame.SRCALPHA)
                _s.fill((200, 30, 30, 80))
                screen.blit(_s, (ox, oy))
                pygame.draw.rect(screen, (220, 50, 50), (ox, oy, ow, oh), 1)
                lbl = dbg_font.render("W", True, (255, 100, 100))
                screen.blit(lbl, (ox + 1, oy + 1))
            for bush in BUSHES:
                bx2, by2 = self._w2s(bush.x, bush.y)
                bw2, bh2 = bush.width, bush.height
                _s = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                _s.fill((30, 200, 30, 80))
                screen.blit(_s, (bx2, by2))
                pygame.draw.rect(screen, (50, 220, 50), (bx2, by2, bw2, bh2), 2)
                lbl = dbg_font.render("B", True, (80, 255, 80))
                screen.blit(lbl, (bx2 + 1, by2 + 1))
            for (czx, czy) in CAPTURE_ZONES:
                cx2, cy2 = self._w2s(czx + 16, czy + 16)
                pygame.draw.circle(screen, (255, 220, 0), (cx2, cy2), 14, 2)
                lbl = dbg_font.render("C", True, (255, 220, 0))
                screen.blit(lbl, lbl.get_rect(center=(cx2, cy2)))
        self.map_system.draw(screen, self.cam_x, self.cam_y)

    def render_ui(self, ui_surf):
        snap    = self.client.latest_snapshot
        my_data = snap.get("players", {}).get(self.client.my_player_id, {})
        self.hud.render(
            ui_surf, snap, self.client, my_data,
            shop_open=self._shop_open,
            my_ready=self._my_ready,
            cam_x=self.cam_x,
            cam_y=self.cam_y,
            cam_locked=self._cam_locked,
            placement_mode=self._placement_mode,
            is_visible_fn=self._is_visible,
        )

    def _draw_capture_point(self, screen, b):
        bx, by, bs = b["x"], b["y"], b["size"]
        sx, sy = self._w2s(bx, by)
        cx, cy = sx + bs // 2, sy + bs // 2
        team = b.get("team", 0)
        if team != 0:
            cp_img = self._hq_imgs_cp.get(team)
            if cp_img:
                screen.blit(cp_img, (sx, sy))
            else:
                col = TEAM_COLOURS.get(team, (160, 160, 160))
                pygame.draw.rect(screen, col, (sx, sy, bs, bs))
        elif self._capture_img:
            screen.blit(self._capture_img, (sx, sy))
        else:
            col = TEAM_COLOURS.get(0, (160, 160, 160))
            pygame.draw.circle(screen, col, (cx, cy), bs // 2)
            pygame.draw.circle(screen, (220, 220, 220), (cx, cy), bs // 2, 2)

        cap_timer = b.get("capture_timer", 0)
        cap_time  = b.get("capture_time",  5)
        cont_team = b.get("capturing_team")
        if cont_team and cap_timer > 0:
            cont_col = TEAM_COLOURS.get(cont_team, (200, 200, 200))
            bar_w    = bs + 16
            fill     = int(bar_w * (cap_timer / cap_time))
            pygame.draw.rect(screen, (40, 40, 40), (cx - bar_w // 2, sy - 10, bar_w, 5))
            pygame.draw.rect(screen, cont_col,     (cx - bar_w // 2, sy - 10, fill,  5))

    def _draw_hp_bar(self, screen, x, y, width, hp, max_hp):
        if max_hp <= 0:
            return
        pygame.draw.rect(screen, (80, 0, 0), (x, y, width, 4))
        pygame.draw.rect(screen, (0, 200, 80), (x, y, int(width * hp / max_hp), 4))
