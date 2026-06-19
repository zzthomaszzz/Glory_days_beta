import os
import math
import pygame
import asyncio

from client.net import NetworkClient
from client.map_system import MapSystem
from shared.constants import (
    CLIENT_INPUT_INTERVAL, BASE_VISION, TURRET_VISION,
    CLIENT_DEFAULT_HOST, SERVER_PORT, SNAPSHOT_INTERVAL,
    MAP_W, MAP_H,
    RUNE_X, RUNE_Y, RUNE_RADIUS, RUNE_CAPTURE_TIME,
)
from shared.map_data import OBSTACLES, SPAWN_ZONES
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

# Native-res minimap (UI layer, bottom-left)
_MINI_W_UI = 240
_MINI_H_UI = 150
_MINI_SX   = _MINI_W_UI / MAP_W
_MINI_SY   = _MINI_H_UI / MAP_H

# Camera edge scroll
_EDGE_ZONE  = 15
_EDGE_SPEED = 220

HERO_ASSET_MAP = {
    "Soldier": os.path.join(_ROOT, "asset", "soldier.png"),
    "Mage":    os.path.join(_ROOT, "asset", "mage.png"),
    "Hunter":  os.path.join(_ROOT, "asset", "hunter.png"),
    "Samurai": os.path.join(_ROOT, "asset", "samurai.png"),
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
        asyncio.create_task(self._connect())

    async def _connect(self):
        client = NetworkClient(self._host, self._port, SNAPSHOT_INTERVAL)
        await client.connect()
        asyncio.create_task(client.receive_loop())
        await client.send_hero_select(self._hero_name)
        self.next_scene = SceneTest(client)

    def process_input(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                self.next_scene = None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.next_scene = None

    def update(self, dt): pass

    def render(self, screen):
        screen.fill((8, 10, 18))

    def render_ui(self, ui_surf):
        text = self._font.render(f"Connecting to {self._host}:{self._port}...", True, (180, 180, 200))
        ui_surf.blit(text, text.get_rect(center=(_SCREEN_W // 2, _SCREEN_H // 2)))


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


TEAM_COLOURS = {
    1: (60, 100, 220),
    2: (220, 60, 60),
}

VISION_BY_TYPE = {
    "BuildingHeadquarter": BASE_VISION,
    "CapturePoint":        BASE_VISION,
    "Turret":              TURRET_VISION,
}

_ABILITY_KEYS = ["Q", "E", "R"]


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
        self._hero_images = {}

        # Camera
        self.cam_x = 0.0
        self.cam_y = 0.0
        self._cam_locked = True

        # Minimap surfaces (240x150)
        self._mini_terrain = self._build_mini_terrain()
        self._mini_fog_surf = pygame.Surface((_MINI_W_UI, _MINI_H_UI), pygame.SRCALPHA)
        self._mini_fog_surf.fill((0, 0, 0, 200))
        self._mini_fog_dirty = True

        # HUD geometry — compact floating panel
        self._hud = self._build_hud_geometry(_SCREEN_W, _SCREEN_H)

        # Monospace fonts so numbers and labels feel intentional
        self._font_cd       = pygame.font.SysFont("consolas", 20, bold=True)
        self._font_slot_sm  = pygame.font.SysFont("consolas", 11)
        self._font_key_lbl  = pygame.font.SysFont("consolas", 12)
        self._font_mini_lbl = pygame.font.SysFont("consolas", 11)
        self._font_gold_lbl = pygame.font.SysFont("consolas", 10)
        self._font_gold_val = pygame.font.SysFont("consolas", 18, bold=True)
        self._font_bar_txt  = pygame.font.SysFont("consolas", 10)
        self._font_shop     = pygame.font.SysFont("consolas", 10)

        # Turret placement mode
        self._placement_mode   = None   # ability slot index while in placement, else None
        self._ability_target   = None   # (world_x, world_y) pending send

        # Entity targeting mode (e.g. Snipe)
        self._entity_target_mode = None   # ability slot index while selecting target, else None
        self._ability_target_id  = None   # str player_id pending send

        # Shop
        self._shop_open      = False
        self._shop_btn_rects = []   # rebuilt each render_ui when shop panel is open

        # Clamped placement cursor (world pos), set each render frame, read in process_input
        self._clamped_placement_pos = None

        # World sprites (pre-scaled to actual in-game sizes)
        self._turret_img  = self._load_asset("turret.png",       (20, 20))
        self._capture_img = self._load_asset("capture_point.png", (32, 32))
        self._hq_imgs     = {
            1: self._load_asset("hq_t1.png", (48, 48)),
            2: self._load_asset("hq_t2.png", (48, 48)),
        }
        # HQ images scaled to capture point size (32x32) for captured zones
        self._hq_imgs_cp  = {
            1: self._load_asset("hq_t1.png", (32, 32)),
            2: self._load_asset("hq_t2.png", (32, 32)),
        }

        # Ability icons keyed by server-side class name
        _icon_map = {
            "Snipe":       "icon_snipe.png",
            "PlaceTurret": "icon_turret.png",
        }
        _icon_sz = self._hud["ability_rects"][0].h - 8
        self._ability_icons = {
            name: self._load_asset(fname, (_icon_sz, _icon_sz))
            for name, fname in _icon_map.items()
        }

        # Gold icon
        self._icon_gold = self._load_asset("icon_gold.png", (14, 14))

        # Lobby state
        self._my_ready          = False
        self._ready_btn_rect    = None   # rebuilt each render_ui when visible
        self._force_start_rect  = None
        self._font_lobby_title  = pygame.font.SysFont("arial", 28, bold=True)
        self._font_lobby_body   = pygame.font.SysFont("consolas", 16)
        self._font_lobby_cd     = pygame.font.SysFont("arial", 72, bold=True)
        self._font_dead_big     = pygame.font.SysFont("arial", 48, bold=True)
        self._font_dead_sub     = pygame.font.SysFont("consolas", 20)

        # Visual effects
        self._floaters       = []   # [{wx, wy, text, color, timer, duration}]
        self._hit_flash      = {}   # pid -> remaining seconds
        self._death_effects  = []   # [{wx, wy, timer, duration}]
        self._prev_hp        = {}   # pid -> last known hp
        self._prev_is_dead   = {}   # pid -> bool
        self._prev_gold      = None
        self._last_proc_snap = 0.0
        self._font_floater   = pygame.font.SysFont("consolas", 14, bold=True)
        self._font_label     = pygame.font.SysFont("consolas", 10)

    def _build_hud_geometry(self, sw, sh):
        A    = 72   # ability slot size
        I    = 58   # inventory slot size
        GA   = 6    # gap between ability slots
        GI   = 6    # gap between inventory slots
        SEP  = 14   # gap between ability and inventory sections
        GW   = 76   # gold section width
        GGAP = 12   # gap between gold section and ability slots
        PX   = 14   # outer horizontal padding
        PT   = 10   # top padding
        KB   = 18   # bottom key-label row height

        # HP / mana bar heights (sit above the panel)
        HP_H     = 12
        MP_H     = 7
        BAR_GAP  = 3
        BAR_BOT  = 5   # gap between mana bar bottom and panel top

        panel_w  = PX + GW + GGAP + 3*A + 2*GA + SEP + 3*I + 2*GI + PX
        bars_h   = HP_H + BAR_GAP + MP_H + BAR_BOT
        panel_h  = PT + A + KB
        panel_x  = sw // 2 - panel_w // 2
        panel_y  = sh - panel_h

        slot_y   = panel_y + PT
        key_y    = slot_y + A + 4

        gold_x   = panel_x + PX
        a_start  = gold_x + GW + GGAP
        ability_rects = [pygame.Rect(a_start + i*(A+GA), slot_y, A, A) for i in range(3)]

        i_start = a_start + 3*A + 2*GA + SEP
        inv_y   = slot_y + (A - I) // 2
        inventory_rects = [pygame.Rect(i_start + i*(I+GI), inv_y, I, I) for i in range(3)]

        div_gold = gold_x + GW + GGAP // 2
        div_inv  = i_start - SEP // 2

        # HP and mana bar rects (spanning full panel width, above panel)
        bar_x  = panel_x
        bar_w  = panel_w
        hp_bar = pygame.Rect(bar_x, panel_y - bars_h, bar_w, HP_H)
        mp_bar = pygame.Rect(bar_x, panel_y - bars_h + HP_H + BAR_GAP, bar_w, MP_H)
        bars_bg = pygame.Rect(bar_x, panel_y - bars_h, bar_w, bars_h)

        # Shop button — below inventory slots, inside panel bottom padding
        inv_bottom = inv_y + I
        shop_rect  = pygame.Rect(i_start, inv_bottom + 4, 3*I + 2*GI, 14)

        return {
            "panel_x":         panel_x,
            "panel_y":         panel_y,
            "panel_w":         panel_w,
            "panel_h":         panel_h,
            "slot_y":          slot_y,
            "key_y":           key_y,
            "gold_x":          gold_x,
            "gold_w":          GW,
            "ability_rects":   ability_rects,
            "inventory_rects": inventory_rects,
            "div_gold":        div_gold,
            "div_inv":         div_inv,
            "hp_bar":          hp_bar,
            "mp_bar":          mp_bar,
            "bars_bg":         bars_bg,
            "shop_rect":       shop_rect,
        }

    def _load_asset(self, filename, size=None):
        path = os.path.join(_ROOT, "asset", filename)
        if not os.path.exists(path):
            return None
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        return img

    def _build_mini_terrain(self):
        surf = pygame.Surface((_MINI_W_UI, _MINI_H_UI))
        surf.fill((30, 35, 40))
        for obs in OBSTACLES:
            ox = int(obs.x      * _MINI_SX)
            oy = int(obs.y      * _MINI_SY)
            ow = max(1, int(obs.width  * _MINI_SX))
            oh = max(1, int(obs.height * _MINI_SY))
            pygame.draw.rect(surf, (12, 14, 18), (ox, oy, ow, oh))
        return surf

    def _rebuild_mini_fog(self):
        self._mini_fog_surf.fill((0, 0, 0, 200))
        ns = self.map_system.size
        nw = max(1, int(ns * _MINI_SX))
        nh = max(1, int(ns * _MINI_SY))
        for node in self.map_system.discovered_nodes:
            mx = int(node.rect.x * _MINI_SX)
            my = int(node.rect.y * _MINI_SY)
            self._mini_fog_surf.fill((0, 0, 0, 0), (mx, my, nw, nh))
        for node in self.map_system.building_vision_nodes:
            mx = int(node.rect.x * _MINI_SX)
            my = int(node.rect.y * _MINI_SY)
            self._mini_fog_surf.fill((0, 0, 0, 0), (mx, my, nw, nh))

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

        mini_rect_screen = pygame.Rect(8, _SCREEN_H - _MINI_H_UI - 8, _MINI_W_UI, _MINI_H_UI)

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                sx, sy = event.pos
                if event.button == 3:
                    # Right-click on an inventory slot sells the item
                    _inv_data = self.client.latest_snapshot.get("players", {}).get(
                        self.client.my_player_id, {}).get("inventory", [])
                    _sold = False
                    for _i, _r in enumerate(self._hud["inventory_rects"]):
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
                        if self._ready_btn_rect and self._ready_btn_rect.collidepoint(sx, sy) and not self._my_ready:
                            self._my_ready = True
                            asyncio.create_task(self.client.send_ready())
                            continue
                        if self._force_start_rect and self._force_start_rect.collidepoint(sx, sy):
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
                    elif self._shop_open and any(r.collidepoint(sx, sy) for r in self._shop_btn_rects):
                        for idx, r in enumerate(self._shop_btn_rects):
                            if r.collidepoint(sx, sy):
                                asyncio.create_task(self.client.send_buy_item(ITEM_KEYS[idx]))
                                break
                    elif self._hud["shop_rect"].collidepoint(sx, sy):
                        self._shop_open = not self._shop_open
                    elif mini_rect_screen.collidepoint(sx, sy):
                        self._handle_minimap_click(sx - 8, sy - (_SCREEN_H - _MINI_H_UI - 8))
                    else:
                        self._handle_click((sx / _SCALE_X, sy / _SCALE_Y))
            if event.type == pygame.KEYDOWN:
                match event.key:
                    case pygame.K_q:      self._handle_ability_key(0)
                    case pygame.K_e:      self._handle_ability_key(1)
                    case pygame.K_r:      self._handle_ability_key(2)
                    case pygame.K_c:      self._show_range = not self._show_range
                    case pygame.K_SPACE:  self._cam_locked = True
                    case pygame.K_ESCAPE:
                        if self._placement_mode is not None or self._entity_target_mode is not None:
                            self._placement_mode     = None
                            self._entity_target_mode = None
                        else:
                            self.next_scene = None

    def _handle_minimap_click(self, rel_x, rel_y):
        world_x = rel_x / _MINI_SX
        world_y = rel_y / _MINI_SY
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

    def _process_snapshot_changes(self, snap):
        my_id   = self.client.my_player_id
        my_team = self.client.my_team
        for pid, p in snap.get("players", {}).items():
            curr_hp   = p.get("hp", 0)
            curr_dead = p.get("is_dead", False)
            prev_hp   = self._prev_hp.get(pid)
            prev_dead = self._prev_is_dead.get(pid, False)
            wx, wy    = p["pos"]

            is_self = pid == my_id
            visible = is_self or self._is_visible(wx, wy, entity_id=pid)

            if visible and prev_hp is not None and curr_hp < prev_hp and not curr_dead:
                dmg = round(prev_hp - curr_hp)
                col = (255, 80, 80) if p.get("team") != my_team else (255, 160, 60)
                self._floaters.append({
                    "wx": wx, "wy": wy - 18,
                    "text": f"-{dmg}",
                    "color": col,
                    "timer": 0.85, "duration": 0.85,
                })
                self._hit_flash[pid] = 0.15

            if not prev_dead and curr_dead:
                self._death_effects.append({
                    "wx": wx, "wy": wy,
                    "timer": 0.6, "duration": 0.6,
                })

            self._prev_hp[pid]      = curr_hp
            self._prev_is_dead[pid] = curr_dead

        # Gold gain floater — only emit when our HQ is on screen
        my_p      = snap.get("players", {}).get(my_id, {})
        curr_gold = my_p.get("gold", 0)
        if self._prev_gold is not None and curr_gold > self._prev_gold:
            gain = curr_gold - self._prev_gold
            for b in snap.get("buildings", {}).values():
                if b.get("type") == "BuildingHeadquarter" and b.get("team") == my_team:
                    bx, by = b["x"], b["y"]
                    if self._is_on_screen(bx, by):
                        self._floaters.append({
                            "wx": bx, "wy": by - 30,
                            "text": f"+{gain}g",
                            "color": (220, 185, 40),
                            "timer": 1.1, "duration": 1.1,
                        })
                    break
        self._prev_gold = curr_gold

    def _is_near_shop(self, snap):
        my_pos = self.client.get_interpolated_pos("players", self.client.my_player_id)
        if not my_pos:
            return False
        for shop in snap.get("shops", {}).values():
            cx = shop["x"] + shop["size"] // 2
            cy = shop["y"] + shop["size"] // 2
            r  = shop.get("range", 120)
            dx, dy = my_pos[0] - cx, my_pos[1] - cy
            if dx * dx + dy * dy <= r * r:
                return True
        return False

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
                self._pending_attack = ("building", bid)
                return

        for pid, p in snap.get("players", {}).items():
            if pid == self.client.my_player_id:
                continue
            pos = self.client.get_interpolated_pos("players", pid)
            if pos:
                if not self._is_visible(pos[0], pos[1]):
                    continue
                dx, dy = wx - pos[0], wy - pos[1]
                if dx*dx + dy*dy <= 64:
                    self._pending_attack = ("player", pid)
                    return

        for tid, t in snap.get("turrets", {}).items():
            if t.get("is_destroyed") or t.get("team") == self.client.my_team:
                continue
            if not self._is_visible(t["x"], t["y"]):
                continue
            half = t.get("size", 20) / 2
            dx, dy = wx - t["x"], wy - t["y"]
            if abs(dx) <= half and abs(dy) <= half:
                self._pending_attack = ("turret", tid)
                return

        for bid, b in snap.get("banners", {}).items():
            if b.get("is_destroyed") or b.get("team") == self.client.my_team:
                continue
            if not self._is_visible(b["x"], b["y"]):
                continue
            half = b.get("size", 20) / 2
            dx, dy = wx - b["x"], wy - b["y"]
            if abs(dx) <= half and abs(dy) <= half:
                self._pending_attack = ("banner", bid)
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
            self._mini_fog_dirty = True

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
            self._mini_fog_dirty = True

        if self._mini_fog_dirty:
            self._rebuild_mini_fog()
            self._mini_fog_dirty = False

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
            self._process_snapshot_changes(snap)

        # Tick and cull effects
        for f in self._floaters:
            f["timer"] -= dt
        for e in self._death_effects:
            e["timer"] -= dt
        self._floaters      = [f for f in self._floaters      if f["timer"] > 0]
        self._death_effects = [e for e in self._death_effects if e["timer"] > 0]
        self._hit_flash     = {pid: t - dt for pid, t in self._hit_flash.items() if t - dt > 0}

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

        for pid in self.client.get_entity_ids("players"):
            pos = self.client.get_interpolated_pos("players", pid)
            if not pos:
                continue
            p_data = snap.get("players", {}).get(pid, {})
            if p_data.get("is_dead"):
                continue
            if p_data.get("team") != my_team and not self._is_visible(pos[0], pos[1], entity_id=pid):
                continue
            sx, sy = self._w2s(pos[0], pos[1])
            abilities = p_data.get("abilities", [])
            spinning = any(ab and ab.get("name") == "Spin" and ab.get("is_spinning") for ab in abilities)
            if spinning:
                slam_r = next((ab.get("slam_radius", 80) for ab in abilities if ab and ab.get("name") == "Spin"), 80)
                pygame.draw.circle(screen, (220, 180, 40), (sx, sy), slam_r, 2)
                spin_surf = pygame.Surface((slam_r * 2, slam_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(spin_surf, (220, 180, 40, 30), (slam_r, slam_r), slam_r)
                screen.blit(spin_surf, (sx - slam_r, sy - slam_r))
            fortified = any(ab and ab.get("name") == "Fortify" and ab.get("is_active") for ab in abilities)
            if fortified:
                pygame.draw.circle(screen, (80, 160, 220), (sx, sy), 18, 2)
            if p_data.get("slow_timer", 0) > 0:
                pygame.draw.circle(screen, (60, 180, 220), (sx, sy), 20, 1)
            if p_data.get("stun_timer", 0) > 0:
                pygame.draw.circle(screen, (240, 200, 40), (sx, sy), 20, 2)

            # Teleport channel arc — shrinks as channel completes
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

            hero = p_data.get("hero", "Player")
            img  = self._get_hero_image(hero)
            if img:
                screen.blit(img, (sx - 16, sy - 16))
            else:
                pygame.draw.circle(screen, TEAM_COLOURS.get(p_data.get("team"), (255, 255, 255)), (sx, sy), 8)

            # Hit flash overlay
            flash_t = self._hit_flash.get(pid, 0)
            if flash_t > 0:
                alpha      = int(200 * flash_t / 0.15)
                flash_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
                flash_surf.fill((255, 255, 255, alpha))
                screen.blit(flash_surf, (sx - 16, sy - 16))

            self._draw_hp_bar(screen, sx - 15, sy - 20, 30, p_data.get("hp", 1), p_data.get("max_hp", 1))

            # Class label above HP bar
            lbl_surf = self._font_label.render(hero[:3].upper(), True,
                                               TEAM_COLOURS.get(p_data.get("team"), (200, 200, 200)))
            screen.blit(lbl_surf, lbl_surf.get_rect(centerx=sx, bottom=sy - 22))

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
            lbl = self._font_slot_sm.render("$", True, (255, 230, 80))
            screen.blit(lbl, lbl.get_rect(center=(sx + sz // 2, sy + sz // 2)))

        for pid, proj in snap.get("projectiles", {}).items():
            pos = self.client.get_interpolated_xy("projectiles", pid)
            if pos is None:
                continue
            sx, sy = self._w2s(pos[0], pos[1])
            col = TEAM_COLOURS.get(proj.get("owner_team"), (255, 255, 200))
            pygame.draw.rect(screen, col, (sx - 2, sy - 2, 4, 4))

        for pid, fp in snap.get("fireball_projectiles", {}).items():
            pos = self.client.get_interpolated_xy("fireball_projectiles", pid)
            if pos is None:
                continue
            sx, sy = self._w2s(pos[0], pos[1])
            pygame.draw.circle(screen, (255, 140, 20), (sx, sy), 5)
            pygame.draw.circle(screen, (255, 220, 80), (sx, sy), 2)

        for ba in snap.get("burning_areas", {}).values():
            half = ba["size"] // 2
            bx, by = self._w2s(ba["x"] - half, ba["y"] - half)
            sz = ba["size"]
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
            # Friendly banners show heal aura
            if bn.get("team") == my_team:
                heal_r = 100
                aura_surf = pygame.Surface((heal_r * 2, heal_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(aura_surf, (60, 220, 100, 28), (heal_r, heal_r), heal_r)
                screen.blit(aura_surf, (sx - heal_r, sy - heal_r))
                pygame.draw.circle(screen, (60, 220, 100), (sx, sy), heal_r, 1)
            # Pole
            pygame.draw.line(screen, (180, 160, 120), (sx, sy + 8), (sx, sy - 16), 2)
            # Flag
            flag_col = team_col
            pygame.draw.polygon(screen, flag_col, [(sx, sy - 16), (sx + 10, sy - 11), (sx, sy - 6)])
            pygame.draw.polygon(screen, (200, 200, 200), [(sx, sy - 16), (sx + 10, sy - 11), (sx, sy - 6)], 1)
            # Duration timer
            dur_s = self._font_label.render(f"{bn.get('duration', 0):.0f}s", True, (200, 230, 200))
            screen.blit(dur_s, dur_s.get_rect(centerx=sx, bottom=sy + 8))

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

        # Death effects — expanding red ring at last known position
        for eff in self._death_effects:
            t_frac = 1.0 - (eff["timer"] / eff["duration"])
            radius = int(10 + t_frac * 22)
            alpha  = int(200 * (1.0 - t_frac))
            ex, ey = self._w2s(eff["wx"], eff["wy"])
            if radius > 0 and self._is_on_screen(eff["wx"], eff["wy"]):
                ring = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ring, (210, 55, 55, alpha), (radius + 2, radius + 2), radius, 2)
                screen.blit(ring, (ex - radius - 2, ey - radius - 2))

        # Floating text (damage numbers + gold gains)
        for f in self._floaters:
            if not self._is_on_screen(f["wx"], f["wy"]):
                continue
            elapsed = f["duration"] - f["timer"]
            fx, fy  = self._w2s(f["wx"], f["wy"])
            fy     -= int(elapsed * 38)     # float upward
            alpha   = int(255 * (f["timer"] / f["duration"]))
            txt     = self._font_floater.render(f["text"], True, f["color"])
            txt.set_alpha(alpha)
            screen.blit(txt, txt.get_rect(centerx=fx, centery=fy))

        self.map_system.draw(screen, self.cam_x, self.cam_y)

    def render_ui(self, ui_surf):
        snap    = self.client.latest_snapshot
        my_team = self.client.my_team
        my_data = snap.get("players", {}).get(self.client.my_player_id, {})
        hud     = self._hud

        mx_ui, my_ui = pygame.mouse.get_pos()   # native-res mouse for hover checks

        # ── HP / Mana bars above panel ───────────────────────────────────────
        hp      = my_data.get("hp",       0)
        max_hp  = max(1, my_data.get("max_hp",   1))
        mana    = my_data.get("mana",     0)
        max_mana = max(1, my_data.get("max_mana", 1))

        bg_r  = hud["bars_bg"]
        hp_r  = hud["hp_bar"]
        mp_r  = hud["mp_bar"]

        # Background strip behind bars (same shade as panel so they feel attached)
        pygame.draw.rect(ui_surf, (10, 11, 20), bg_r)

        # HP bar
        hp_fill = int(hp_r.w * hp / max_hp)
        pygame.draw.rect(ui_surf, (40, 14, 14), hp_r)
        if hp_fill > 0:
            pygame.draw.rect(ui_surf, (38, 168, 58), (hp_r.x, hp_r.y, hp_fill, hp_r.h))
        hp_txt = self._font_bar_txt.render(f"{hp} / {max_hp}", True, (200, 235, 200))
        ui_surf.blit(hp_txt, hp_txt.get_rect(centerx=hp_r.centerx, centery=hp_r.centery))

        # Mana bar
        mp_fill = int(mp_r.w * mana / max_mana)
        pygame.draw.rect(ui_surf, (10, 18, 55), mp_r)
        if mp_fill > 0:
            pygame.draw.rect(ui_surf, (32, 98, 215), (mp_r.x, mp_r.y, mp_fill, mp_r.h))

        # ── Channel bar (appears when channeling an ability) ─────────────────
        for ab in my_data.get("abilities", []):
            if ab and ab.get("is_channeling"):
                ct  = ab.get("channel_timer", 0)
                cm  = max(0.001, ab.get("channel_time", 1.5))
                bw  = 200
                bh  = 10
                bx  = _SCREEN_W // 2 - bw // 2
                by  = hud["bars_bg"].top - 26
                pygame.draw.rect(ui_surf, (18, 18, 28), (bx - 2, by - 14, bw + 4, bh + 16))
                lbl = self._font_bar_txt.render("CHARGING", True, (200, 160, 40))
                ui_surf.blit(lbl, lbl.get_rect(centerx=_SCREEN_W // 2, bottom=by - 1))
                pygame.draw.rect(ui_surf, (35, 28, 10), (bx, by, bw, bh))
                fill = int(bw * ct / cm)
                if fill > 0:
                    pygame.draw.rect(ui_surf, (210, 150, 30), (bx, by, fill, bh))
                pygame.draw.rect(ui_surf, (130, 100, 20), (bx, by, bw, bh), 1)
                break

        # ── Compact floating HUD panel ───────────────────────────────────────
        px, py = hud["panel_x"], hud["panel_y"]
        pw, ph = hud["panel_w"], hud["panel_h"]

        pygame.draw.rect(ui_surf, (10, 11, 20), (px, py, pw, ph))
        pygame.draw.line(ui_surf, (55, 65, 98), (px, py), (px + pw - 1, py), 1)
        pygame.draw.rect(ui_surf, (24, 26, 42), (px, py, pw, ph), 1)

        slot_y = hud["slot_y"]
        key_y  = hud["key_y"]

        # ── Gold section (left of abilities) ─────────────────────────────────
        gold   = my_data.get("gold", 0)
        gx     = hud["gold_x"]
        if self._icon_gold:
            ui_surf.blit(self._icon_gold, (gx, slot_y + 16))
        else:
            gl_s = self._font_gold_lbl.render("GOLD", True, (72, 62, 30))
            ui_surf.blit(gl_s, (gx, slot_y + 18))
        gv_s = self._font_gold_val.render(str(gold), True, (188, 158, 48))
        ui_surf.blit(gv_s, (gx, slot_y + 32))

        # Thin divider after gold section
        pygame.draw.line(
            ui_surf, (30, 33, 52),
            (hud["div_gold"], slot_y + 6),
            (hud["div_gold"], slot_y + 58), 1,
        )

        abilities = my_data.get("abilities", [])

        # ── Ability slots (Q / E / R) ────────────────────────────────────────
        for i, rect in enumerate(hud["ability_rects"]):
            ability    = abilities[i] if i < len(abilities) else None
            on_cd      = bool(ability and ability.get("is_on_cooldown"))
            in_place   = self._placement_mode == i
            ab_active  = bool(ability and ability.get("is_active"))   # Fortify buff
            ab_spinning = bool(ability and ability.get("is_spinning"))  # Samurai Spin
            ab_passive  = bool(ability and ability.get("is_passive"))   # Bushido

            pygame.draw.rect(ui_surf, (16, 17, 28), rect)

            if ab_passive:
                pygame.draw.rect(ui_surf, (85, 70, 35), rect, 1)
                ns = self._font_slot_sm.render("PASSIVE", True, (160, 140, 80))
                ui_surf.blit(ns, ns.get_rect(centerx=rect.centerx, centery=rect.centery - 6))
                crit_s = self._font_slot_sm.render("25% CRIT", True, (220, 185, 60))
                ui_surf.blit(crit_s, crit_s.get_rect(centerx=rect.centerx, centery=rect.centery + 7))

            elif ab_spinning:
                pygame.draw.rect(ui_surf, (200, 160, 30), rect, 2)
                spin_t   = ability.get("spin_timer", 0)
                spin_max = max(0.001, ability.get("spin_duration", 5.0))
                bar_w    = int(rect.w * spin_t / spin_max)
                pygame.draw.rect(ui_surf, (60, 48, 8), (rect.x, rect.y, rect.w, 3))
                if bar_w > 0:
                    pygame.draw.rect(ui_surf, (255, 200, 40), (rect.x, rect.y, bar_w, 3))
                name_s = self._font_slot_sm.render("SPIN", True, (255, 210, 60))
                ui_surf.blit(name_s, name_s.get_rect(centerx=rect.centerx, centery=rect.centery))

            elif ab_active and not on_cd:
                # Draw active buff glow border + duration drain bar at top
                pygame.draw.rect(ui_surf, (60, 140, 210), rect, 2)
                dur_t   = ability.get("duration_timer", 0)
                dur_max = max(0.001, ability.get("duration", 10))
                bar_w   = int(rect.w * dur_t / dur_max)
                pygame.draw.rect(ui_surf, (30, 80, 130), (rect.x, rect.y, rect.w, 3))
                if bar_w > 0:
                    pygame.draw.rect(ui_surf, (80, 180, 255), (rect.x, rect.y, bar_w, 3))
                name_s = self._font_slot_sm.render(ability.get("name", "")[:6].upper(), True, (100, 190, 255))
                ui_surf.blit(name_s, name_s.get_rect(centerx=rect.centerx, centery=rect.centery))

            elif in_place:
                # Active placement mode — highlight the slot
                pygame.draw.rect(ui_surf, (55, 160, 70), rect, 2)
                ns = self._font_slot_sm.render("PLACE", True, (80, 200, 100))
                ui_surf.blit(ns, ns.get_rect(centerx=rect.centerx, centery=rect.centery))

            elif on_cd:
                icon = self._ability_icons.get(ability.get("name", ""))
                if icon:
                    iw, ih = icon.get_size()
                    ui_surf.blit(icon, (rect.x + (rect.w - iw) // 2, rect.y + (rect.h - ih) // 2))
                cd_t   = ability.get("cooldown_timer", 0)
                cd_max = max(0.001, ability.get("cooldown", 1))
                overlay_h = int(rect.h * (cd_t / cd_max))
                if overlay_h > 0:
                    cd_s = pygame.Surface((rect.w, overlay_h), pygame.SRCALPHA)
                    cd_s.fill((0, 0, 0, 178))
                    ui_surf.blit(cd_s, (rect.x, rect.y))
                pygame.draw.rect(ui_surf, (30, 32, 50), rect, 1)
                num = self._font_cd.render(str(math.ceil(cd_t)), True, (210, 210, 222))
                ui_surf.blit(num, num.get_rect(center=rect.center))

            elif ability:
                icon = self._ability_icons.get(ability.get("name", ""))
                if icon:
                    iw, ih = icon.get_size()
                    ui_surf.blit(icon, (rect.x + (rect.w - iw) // 2, rect.y + (rect.h - ih) // 2))
                    pygame.draw.rect(ui_surf, (105, 84, 26), rect, 1)
                else:
                    pygame.draw.rect(ui_surf, (105, 84, 26), rect, 1)
                    name = ability.get("name", "")[:9].upper()
                    ns   = self._font_slot_sm.render(name, True, (148, 138, 90))
                    ui_surf.blit(ns, ns.get_rect(centerx=rect.centerx, centery=rect.centery))

            else:
                pygame.draw.rect(ui_surf, (20, 22, 36), rect, 1)

            ks = self._font_key_lbl.render(_ABILITY_KEYS[i], True, (62, 58, 34))
            ui_surf.blit(ks, ks.get_rect(centerx=rect.centerx, top=key_y))

        # ── Vertical divider between abilities and inventory ──────────────────
        pygame.draw.line(
            ui_surf, (30, 33, 52),
            (hud["div_inv"], slot_y + 6),
            (hud["div_inv"], slot_y + 58), 1,
        )

        # ── Inventory slots ──────────────────────────────────────────────────
        inventory = my_data.get("inventory", [])[:3]

        for i, rect in enumerate(hud["inventory_rects"]):
            pygame.draw.rect(ui_surf, (12, 13, 22), rect)
            item = inventory[i] if i < len(inventory) else None
            if item:
                inner = rect.inflate(-6, -6)
                pygame.draw.rect(ui_surf, (98, 78, 30), inner)
                hovering = rect.collidepoint(mx_ui, my_ui)
                if hovering:
                    hover_ov = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                    hover_ov.fill((0, 0, 0, 110))
                    ui_surf.blit(hover_ov, rect.topleft)
                    refund = ITEMS.get(item, {}).get("cost", 0) // 2
                    sell_s = self._font_slot_sm.render(f"SELL {refund}g", True, (210, 130, 50))
                    ui_surf.blit(sell_s, sell_s.get_rect(center=rect.center))
                else:
                    lbl = ITEMS.get(item, {}).get("label", item[:3])
                    lbl_s = self._font_slot_sm.render(lbl, True, (230, 205, 120))
                    ui_surf.blit(lbl_s, lbl_s.get_rect(center=rect.center))
            pygame.draw.rect(ui_surf, (22, 24, 40), rect, 1)

        # ── Shop button (below inventory slots) ──────────────────────────────
        sr = hud["shop_rect"]
        shop_hover = sr.collidepoint(mx_ui, my_ui)
        if self._shop_open:
            shop_bg  = (28, 36, 55)
            shop_brd = (55, 75, 120)
            shop_txt_col = (130, 165, 215)
        elif shop_hover:
            shop_bg  = (18, 20, 34)
            shop_brd = (40, 46, 70)
            shop_txt_col = (100, 110, 150)
        else:
            shop_bg  = (12, 13, 24)
            shop_brd = (28, 32, 50)
            shop_txt_col = (65, 72, 100)
        pygame.draw.rect(ui_surf, shop_bg, sr)
        pygame.draw.rect(ui_surf, shop_brd, sr, 1)
        st = self._font_shop.render("SHOP", True, shop_txt_col)
        ui_surf.blit(st, st.get_rect(center=sr.center))

        # ── Shop panel (above HUD when open) ────────────────────────────────
        self._shop_btn_rects = []
        if self._shop_open:
            self._render_shop_panel(ui_surf, snap, my_data, hud)

        # ── Minimap (bottom-left) ────────────────────────────────────────────
        sh     = _SCREEN_H
        mini_x = 8
        mini_y = sh - _MINI_H_UI - 8

        ui_surf.blit(self._mini_terrain, (mini_x, mini_y))
        ui_surf.blit(self._mini_fog_surf, (mini_x, mini_y))

        for b in snap.get("buildings", {}).values():
            if b.get("is_destroyed"):
                continue
            btype = b.get("type")
            team  = b.get("team", 0)
            col   = TEAM_COLOURS.get(team, (110, 110, 110))
            bx = mini_x + int(b["x"] * _MINI_SX)
            by = mini_y + int(b["y"] * _MINI_SY)
            size = 6 if btype == "BuildingHeadquarter" else 3
            pygame.draw.rect(ui_surf, col, (bx, by, size, size))

        for shop in snap.get("shops", {}).values():
            sx_m = mini_x + int(shop["x"] * _MINI_SX)
            sy_m = mini_y + int(shop["y"] * _MINI_SY)
            pygame.draw.rect(ui_surf, (200, 170, 40), (sx_m, sy_m, 4, 4))

        for t in snap.get("turrets", {}).values():
            if t.get("is_destroyed"):
                continue
            team = t.get("team", 0)
            col  = TEAM_COLOURS.get(team, (150, 150, 150))
            tx   = mini_x + int(t["x"] * _MINI_SX)
            ty_m = mini_y + int(t["y"] * _MINI_SY)
            pygame.draw.rect(ui_surf, col, (tx - 2, ty_m - 2, 4, 4))

        for bn in snap.get("banners", {}).values():
            if bn.get("is_destroyed"):
                continue
            if bn.get("team") != my_team and not self._is_visible(bn["x"], bn["y"]):
                continue
            bx_m = mini_x + int(bn["x"] * _MINI_SX)
            by_m = mini_y + int(bn["y"] * _MINI_SY)
            pygame.draw.circle(ui_surf, (60, 220, 100), (bx_m, by_m), 3)

        rune_mini = snap.get("rune", {})
        if rune_mini.get("state") not in ("inactive", "cooldown"):
            rmx = mini_x + int(RUNE_X * _MINI_SX)
            rmy = mini_y + int(RUNE_Y * _MINI_SY)
            pygame.draw.circle(ui_surf, (180, 80, 240), (rmx, rmy), 4)

        for pid in self.client.get_entity_ids("players"):
            p_data = snap.get("players", {}).get(pid, {})
            if p_data.get("is_dead"):
                continue
            pos = self.client.get_interpolated_pos("players", pid)
            if not pos:
                continue
            team = p_data.get("team")
            if team != my_team and not self._is_visible(pos[0], pos[1]):
                continue
            col  = TEAM_COLOURS.get(team, (255, 255, 255))
            pmx  = mini_x + int(pos[0] * _MINI_SX)
            pmy  = mini_y + int(pos[1] * _MINI_SY)
            pygame.draw.circle(ui_surf, col, (pmx, pmy), 3)

        vx = mini_x + int(self.cam_x * _MINI_SX)
        vy = mini_y + int(self.cam_y * _MINI_SY)
        vw = max(1, int(VIEWPORT_W * _MINI_SX))
        vh = max(1, int(VIEWPORT_H * _MINI_SY))
        pygame.draw.rect(ui_surf, (200, 200, 200), (vx, vy, vw, vh), 1)
        pygame.draw.rect(ui_surf, (38, 44, 64), (mini_x, mini_y, _MINI_W_UI, _MINI_H_UI), 1)

        label     = "CAM" if self._cam_locked else "FREE"
        label_col = (80, 160, 80) if self._cam_locked else (160, 120, 50)
        lock_s    = self._font_mini_lbl.render(label, True, label_col)
        ui_surf.blit(lock_s, (mini_x + _MINI_W_UI - lock_s.get_width() - 4, mini_y - lock_s.get_height() - 3))

        # ── Lobby overlay (waiting / countdown) ──────────────────────────────
        game_phase = snap.get("game_phase", "live")
        if game_phase in ("waiting", "countdown"):
            self._render_lobby_overlay(ui_surf, snap, game_phase)

        # ── Death / respawn overlay ──────────────────────────────────────────
        if my_data.get("is_dead") and snap.get("game_phase") == "live":
            exhausted = snap.get("minerals_exhausted", False)
            ov = pygame.Surface((_SCREEN_W, _SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 80))
            ui_surf.blit(ov, (0, 0))
            if exhausted:
                msg = self._font_dead_big.render("ELIMINATED", True, (200, 60, 60))
                sub = self._font_dead_sub.render("No respawns — minerals exhausted", True, (180, 120, 120))
            else:
                timer = max(0, my_data.get("respawn_timer", 0))
                msg = self._font_dead_big.render("YOU DIED", True, (200, 60, 60))
                sub = self._font_dead_sub.render(f"Respawning in {timer:.1f}s", True, (180, 160, 160))
            ui_surf.blit(msg, msg.get_rect(centerx=_SCREEN_W // 2, centery=_SCREEN_H // 2 - 30))
            ui_surf.blit(sub, sub.get_rect(centerx=_SCREEN_W // 2, centery=_SCREEN_H // 2 + 26))

        # ── Victory / Defeat overlay ─────────────────────────────────────────
        winner = snap.get("winner")
        if winner is not None:
            ov = pygame.Surface((_SCREEN_W, _SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160))
            ui_surf.blit(ov, (0, 0))
            my_win = winner == self.client.my_team
            big_font = pygame.font.SysFont("arial", 80, bold=True)
            sub_font = pygame.font.SysFont("arial", 24)
            if my_win:
                main_s = big_font.render("VICTORY", True, (230, 195, 50))
            else:
                main_s = big_font.render("DEFEAT",  True, (170, 50, 50))
            ui_surf.blit(main_s, main_s.get_rect(centerx=_SCREEN_W // 2, centery=_SCREEN_H // 2 - 50))
            hint_s = sub_font.render("Press ESC to exit", True, (160, 160, 180))
            ui_surf.blit(hint_s, hint_s.get_rect(centerx=_SCREEN_W // 2, centery=_SCREEN_H // 2 + 40))

    def _render_lobby_overlay(self, ui_surf, snap, game_phase):
        sw, sh   = _SCREEN_W, _SCREEN_H
        players  = snap.get("players", {})
        mx, my   = pygame.mouse.get_pos()

        self._ready_btn_rect   = None
        self._force_start_rect = None

        if game_phase == "countdown":
            # Fullscreen dark flash + big countdown number
            cd = max(0, snap.get("countdown_timer", 3.0))
            ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 120))
            ui_surf.blit(ov, (0, 0))
            cd_s = self._font_lobby_cd.render(str(math.ceil(cd)), True, (255, 230, 80))
            ui_surf.blit(cd_s, cd_s.get_rect(centerx=sw // 2, centery=sh // 2 - 20))
            lbl = self._font_lobby_body.render("GET READY", True, (200, 200, 220))
            ui_surf.blit(lbl, lbl.get_rect(centerx=sw // 2, centery=sh // 2 + 60))
            return

        # ── Waiting panel ────────────────────────────────────────────────────
        pw   = int(sw * 0.30)
        ph   = int(sh * 0.38)
        px   = (sw - pw) // 2
        py   = int(sh * 0.18)

        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((8, 10, 22, 220))
        ui_surf.blit(panel, (px, py))
        pygame.draw.rect(ui_surf, (50, 65, 110), (px, py, pw, ph), 2, border_radius=8)

        title = self._font_lobby_title.render("WAITING FOR PLAYERS", True, (200, 200, 230))
        ui_surf.blit(title, title.get_rect(centerx=px + pw // 2, top=py + 14))

        # Divider
        pygame.draw.line(ui_surf, (40, 50, 80), (px + 16, py + 52), (px + pw - 16, py + 52))

        # Team columns
        col_w    = pw // 2
        row_h    = 26
        text_top = py + 62

        for team in (1, 2):
            cx = px + (col_w * (team - 1)) + col_w // 2
            team_s = self._font_lobby_body.render(f"TEAM {team}", True, TEAM_COLOURS.get(team, (200, 200, 200)))
            ui_surf.blit(team_s, team_s.get_rect(centerx=cx, top=text_top))
            row = text_top + row_h
            for p in players.values():
                if p.get("team") != team:
                    continue
                hero  = p.get("hero", "?")[:3].upper()
                ready = p.get("is_ready", False)
                mark  = "✓" if ready else "·"
                col   = (80, 210, 100) if ready else (160, 160, 180)
                line  = self._font_lobby_body.render(f"{mark} {hero}", True, col)
                ui_surf.blit(line, line.get_rect(centerx=cx, top=row))
                row  += row_h

        # READY button (only if I haven't readied yet)
        btn_y = py + ph - int(ph * 0.28)
        if not self._my_ready:
            btn_w  = int(pw * 0.42)
            btn_h  = int(sh * 0.046)
            btn_x  = px + (pw - btn_w) // 2
            btn_r  = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            hov    = btn_r.collidepoint(mx, my)
            pygame.draw.rect(ui_surf, (30, 140, 60) if hov else (20, 105, 45), btn_r, border_radius=8)
            pygame.draw.rect(ui_surf, (60, 220, 100), btn_r, 2, border_radius=8)
            lbl = self._font_lobby_title.render("READY", True, (255, 255, 255))
            ui_surf.blit(lbl, lbl.get_rect(center=btn_r.center))
            self._ready_btn_rect = btn_r
        else:
            wait_s = self._font_lobby_body.render("Waiting for others...", True, (100, 200, 120))
            ui_surf.blit(wait_s, wait_s.get_rect(centerx=px + pw // 2, top=btn_y + 6))

        # Force-start button (unlocks after 90 s)
        wait_elapsed = snap.get("wait_elapsed", 0)
        if wait_elapsed >= 90:
            fs_w  = int(pw * 0.52)
            fs_h  = int(sh * 0.036)
            fs_x  = px + (pw - fs_w) // 2
            fs_y  = py + ph - int(sh * 0.038)
            fs_r  = pygame.Rect(fs_x, fs_y, fs_w, fs_h)
            hov   = fs_r.collidepoint(mx, my)
            pygame.draw.rect(ui_surf, (120, 60, 20) if hov else (90, 40, 10), fs_r, border_radius=6)
            pygame.draw.rect(ui_surf, (200, 120, 40), fs_r, 1, border_radius=6)
            lbl = self._font_lobby_body.render("FORCE START", True, (230, 160, 60))
            ui_surf.blit(lbl, lbl.get_rect(center=fs_r.center))
            self._force_start_rect = fs_r

    def _render_shop_panel(self, ui_surf, snap, my_data, hud):
        ITEM_ROW_H  = 46
        HEADER_H    = 28
        PANEL_W     = 560
        PANEL_H     = HEADER_H + len(ITEM_KEYS) * ITEM_ROW_H + 10
        panel_x     = _SCREEN_W // 2 - PANEL_W // 2
        panel_y     = hud["bars_bg"].top - PANEL_H - 6

        pygame.draw.rect(ui_surf, (10, 11, 20), (panel_x, panel_y, PANEL_W, PANEL_H))
        pygame.draw.rect(ui_surf, (50, 60, 90), (panel_x, panel_y, PANEL_W, PANEL_H), 1)

        title = self._font_slot_sm.render("SHOP", True, (180, 160, 60))
        ui_surf.blit(title, title.get_rect(centerx=panel_x + PANEL_W // 2, top=panel_y + 6))

        near = self._is_near_shop(snap)
        if not near:
            msg = self._font_slot_sm.render("Move closer to a shop ($) to buy", True, (160, 120, 60))
            ui_surf.blit(msg, msg.get_rect(centerx=panel_x + PANEL_W // 2,
                                           centery=panel_y + HEADER_H + PANEL_H // 2))
            return

        gold      = my_data.get("gold", 0)
        inventory = my_data.get("inventory", [None] * 3)
        inv_full  = all(s is not None for s in inventory[:3])

        mx_ui, my_ui = pygame.mouse.get_pos()

        for idx, key in enumerate(ITEM_KEYS):
            item   = ITEMS[key]
            row_y  = panel_y + HEADER_H + idx * ITEM_ROW_H
            can_buy = gold >= item["cost"] and not inv_full

            # Row background
            row_col = (16, 17, 28) if idx % 2 == 0 else (13, 14, 24)
            pygame.draw.rect(ui_surf, row_col, (panel_x, row_y, PANEL_W, ITEM_ROW_H))

            # Item name
            name_col = (215, 195, 120) if can_buy else (100, 90, 60)
            name_s   = self._font_slot_sm.render(key, True, name_col)
            ui_surf.blit(name_s, (panel_x + 8, row_y + ITEM_ROW_H // 2 - name_s.get_height() // 2))

            # Stats description
            desc_s = self._font_slot_sm.render(item["desc"], True, (120, 130, 150))
            ui_surf.blit(desc_s, (panel_x + 148, row_y + ITEM_ROW_H // 2 - desc_s.get_height() // 2))

            # Cost
            cost_col = (200, 170, 50) if gold >= item["cost"] else (120, 80, 40)
            cost_s   = self._font_slot_sm.render(f"{item['cost']}g", True, cost_col)
            ui_surf.blit(cost_s, (panel_x + PANEL_W - 86, row_y + ITEM_ROW_H // 2 - cost_s.get_height() // 2))

            # BUY button
            btn_rect = pygame.Rect(panel_x + PANEL_W - 58, row_y + 8, 52, 30)
            self._shop_btn_rects.append(btn_rect)
            hovered  = btn_rect.collidepoint(mx_ui, my_ui)
            if can_buy:
                btn_bg  = (40, 120, 50) if hovered else (25, 80, 35)
                btn_brd = (70, 180, 80)
                btn_tc  = (220, 255, 220)
            else:
                btn_bg  = (30, 30, 40)
                btn_brd = (45, 45, 60)
                btn_tc  = (70, 70, 90)
            pygame.draw.rect(ui_surf, btn_bg,  btn_rect, border_radius=4)
            pygame.draw.rect(ui_surf, btn_brd, btn_rect, 1, border_radius=4)
            buy_s = self._font_slot_sm.render("BUY", True, btn_tc)
            ui_surf.blit(buy_s, buy_s.get_rect(center=btn_rect.center))

        if inv_full:
            msg = self._font_slot_sm.render("Inventory full", True, (180, 80, 60))
            ui_surf.blit(msg, msg.get_rect(right=panel_x + PANEL_W - 8, top=panel_y + 4))

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
