# Scene classes: SceneMenu, SceneConnecting, SceneTest (the main gameplay scene)
import os
import math
import random
import pygame
import asyncio

from client.net import NetworkClient, ping_server
from client.map_system import MapSystem
from client.effects import EffectsSystem, target_is_gone
from client.status_effects import StatusEffectRenderer
from client.hud import HudRenderer, TEAM_COLOURS, MINI_W, MINI_H, MINI_SX, MINI_SY, _build_item_icons
from shared.constants import (
    CLIENT_INPUT_INTERVAL,
    CLIENT_DEFAULT_HOST, SERVER_PORT, SNAPSHOT_INTERVAL,
    MAP_W, MAP_H,
    RUNE_X, RUNE_Y, RUNE_RADIUS, RUNE_CAPTURE_TIME,
    OFFICIAL_SERVER_HOST, OFFICIAL_SERVER_PORT,
)
from shared.map_data import OBSTACLES, SPAWN_ZONES, BUSHES, CAPTURE_ZONES
from shared.items import ITEMS, ITEM_KEYS
from shared.heroes import HERO_STATS as _HERO_DATA

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
    "Watcher": os.path.join(_ROOT, "asset", "watcher.png"),
    "Player":  os.path.join(_ROOT, "asset", "default_player.png"),
}


_HERO_CARDS = [
    {
        "name":      name,
        "desc":      data['desc'],
        "stats":     {
            "HP":     data['hp'],
            "Damage": data['attack_damage'],
            "Range":  data['attack_range'],
            "Speed":  data['speed'],
            "Armor":  data['armor'],
        },
        "abilities": data['ability_descs'],
    }
    for name, data in _HERO_DATA.items()
]


async def _do_ping_idx(scene, idx):
    srv    = scene._servers[idx]
    result = await ping_server(srv["host"], srv["port"])
    scene._server_infos[idx] = result


#-------------------------------------------------------------------------------------------------------------------Menu
class SceneMenu:
    _PING_INTERVAL = 10.0

    def __init__(self):
        self.next_scene      = self
        self._chosen         = "Soldier"
        self._servers        = [
            {"name": "Official Server", "addr": f"{OFFICIAL_SERVER_HOST}:{OFFICIAL_SERVER_PORT}",
             "host": OFFICIAL_SERVER_HOST, "port": OFFICIAL_SERVER_PORT},
            {"name": "Local Server",    "addr": f"{CLIENT_DEFAULT_HOST}:{SERVER_PORT}",
             "host": CLIENT_DEFAULT_HOST, "port": SERVER_PORT},
        ]
        self._server_infos   = [{"online": None} for _ in self._servers]
        self._sel_server     = 0
        self._ping_timer     = 0.0
        self._hovered_row    = None

        sw, sh = _SCREEN_W, _SCREEN_H

        self._L       = int(sw * 0.23)
        self._M       = int(sw * 0.43)
        self._title_h = int(sh * 0.11)

        row_h   = int(sh * 0.10)
        row_gap = int(sh * 0.014)
        row_x   = int(self._L * 0.05)
        row_w   = int(self._L * 0.90)
        start_y = self._title_h + int(sh * 0.05)
        self._hero_rows = [
            pygame.Rect(row_x, start_y + i * (row_h + row_gap), row_w, row_h)
            for i in range(len(_HERO_CARDS))
        ]

        right_x  = self._L + self._M
        right_w  = sw - right_x
        btn_w    = int(right_w * 0.72)
        btn_h    = int(sh * 0.058)
        self._connect_rect  = pygame.Rect(
            right_x + (right_w - btn_w) // 2, int(sh * 0.87), btn_w, btn_h
        )
        # Server card rects (precomputed for click detection)
        pad_r    = int(right_w * 0.07)
        srv_rx   = right_x + pad_r
        srv_rw   = right_w - 2 * pad_r
        hdr_approx = int(sh * 0.019) + int(sh * 0.018)
        card_rh  = int(sh * 0.22)
        card_rg  = int(sh * 0.014)
        cards_y  = self._title_h + int(sh * 0.025) + hdr_approx
        self._server_card_rects = [
            pygame.Rect(srv_rx, cards_y + i * (card_rh + card_rg), srv_rw, card_rh)
            for i in range(len(self._servers))
        ]

        port_sm = int(sh * 0.072)
        port_lg = int(sh * 0.21)
        self._portraits_sm = {}
        self._portraits_lg = {}
        for card in _HERO_CARDS:
            path = HERO_ASSET_MAP.get(card["name"])
            if path and os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self._portraits_sm[card["name"]] = pygame.transform.smoothscale(img, (port_sm, port_sm))
                self._portraits_lg[card["name"]] = pygame.transform.smoothscale(img, (port_lg, port_lg))

        self._item_icons      = _build_item_icons(28)
        self._sel_item        = None
        self._item_card_rects = {}

        self._f_title     = pygame.font.SysFont("arial", int(sh * 0.046), bold=True)
        self._f_phdr      = pygame.font.SysFont("arial", int(sh * 0.019), bold=True)
        self._f_row       = pygame.font.SysFont("arial", int(sh * 0.021), bold=True)
        self._f_det_name  = pygame.font.SysFont("arial", int(sh * 0.030), bold=True)
        self._f_det_desc  = pygame.font.SysFont("arial", int(sh * 0.015))
        self._f_stat_lbl  = pygame.font.SysFont("arial", int(sh * 0.016))
        self._f_stat_val  = pygame.font.SysFont("arial", int(sh * 0.016), bold=True)
        self._f_ab_key    = pygame.font.SysFont("arial", int(sh * 0.014), bold=True)
        self._f_ab_name   = pygame.font.SysFont("arial", int(sh * 0.015), bold=True)
        self._f_ab_desc   = pygame.font.SysFont("arial", int(sh * 0.014))
        self._f_ab_hdr    = pygame.font.SysFont("arial", int(sh * 0.015), bold=True)
        self._f_btn       = pygame.font.SysFont("arial", int(sh * 0.026), bold=True)
        self._f_srv       = pygame.font.SysFont("arial", int(sh * 0.017))
        self._f_srv_sm    = pygame.font.SysFont("arial", int(sh * 0.014))

    def process_input(self, events):
        mx, my = pygame.mouse.get_pos()
        self._hovered_row = None
        for i, r in enumerate(self._hero_rows):
            if r.collidepoint(mx, my):
                self._hovered_row = i

        for event in events:
            if event.type == pygame.QUIT:
                self.next_scene = None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.next_scene = None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                ex, ey = event.pos
                for i, r in enumerate(self._hero_rows):
                    if r.collidepoint(ex, ey):
                        self._chosen = _HERO_CARDS[i]["name"]
                for key, r in self._item_card_rects.items():
                    if r.collidepoint(ex, ey):
                        self._sel_item = key if self._sel_item != key else None
                for i, r in enumerate(self._server_card_rects):
                    if r.collidepoint(ex, ey):
                        self._sel_server = i
                if self._connect_rect.collidepoint(ex, ey) \
                        and self._server_infos[self._sel_server].get("online"):
                    srv = self._servers[self._sel_server]
                    self.next_scene = SceneConnecting(srv["host"], srv["port"], self._chosen)
    def update(self, dt):
        self._ping_timer -= dt
        if self._ping_timer <= 0:
            self._ping_timer = self._PING_INTERVAL
            for i in range(len(self._servers)):
                asyncio.create_task(_do_ping_idx(self, i))

    def render(self, screen):
        screen.fill((20, 14, 4))

    def render_ui(self, ui_surf):
        sw, sh  = _SCREEN_W, _SCREEN_H
        mx, my  = pygame.mouse.get_pos()
        L       = self._L
        M       = self._M
        mid_x   = L
        right_x = L + M
        right_w = sw - right_x
        title_h = self._title_h

        # ── Background + panel fills ───────────────────────────────────────
        ui_surf.fill((20, 14, 4))

        # Title bar — slightly lighter warm strip
        tb = pygame.Surface((sw, title_h), pygame.SRCALPHA)
        tb.fill((32, 24, 8, 250))
        ui_surf.blit(tb, (0, 0))

        # Three panel backgrounds — left/right slightly warmer than centre
        for bx, bw, col in (
            (0,       L,       (28, 21, 8,  210)),
            (L,       M,       (22, 16, 5,  210)),
            (right_x, right_w, (28, 21, 8,  210)),
        ):
            ps = pygame.Surface((bw, sh - title_h), pygame.SRCALPHA)
            ps.fill(col)
            ui_surf.blit(ps, (bx, title_h))

        # Outer frame + dividers — all in warm amber/gold
        pygame.draw.rect(ui_surf, (95, 72, 18), pygame.Rect(0, 0, sw, sh), 1)
        pygame.draw.line(ui_surf, (95, 72, 18), (0,       title_h), (sw,      title_h), 1)
        pygame.draw.line(ui_surf, (65, 50, 12), (L,       title_h), (L,       sh - 1),  1)
        pygame.draw.line(ui_surf, (65, 50, 12), (right_x, title_h), (right_x, sh - 1),  1)

        # ── Title ─────────────────────────────────────────────────────────
        t_s = self._f_title.render("GLORY DAY", True, (240, 200, 55))
        ui_surf.blit(t_s, t_s.get_rect(centerx=sw // 2, centery=title_h // 2))

        # ── Left panel: hero list ──────────────────────────────────────────
        hdr = self._f_phdr.render("HEROES", True, (185, 148, 45))
        ui_surf.blit(hdr, hdr.get_rect(centerx=L // 2, top=title_h + int(sh * 0.016)))

        for i, (card, row_r) in enumerate(zip(_HERO_CARDS, self._hero_rows)):
            is_sel = self._chosen == card["name"]
            is_hov = self._hovered_row == i
            bg = pygame.Surface((row_r.w, row_r.h), pygame.SRCALPHA)
            if is_sel:
                bg.fill((105, 80, 18, 225))
            elif is_hov:
                bg.fill((58, 44, 14, 190))
            else:
                bg.fill((35, 26, 8,  165))
            ui_surf.blit(bg, row_r.topleft)
            brd = (220, 175, 38) if is_sel else (90, 70, 18) if is_hov else (58, 44, 12)
            pygame.draw.rect(ui_surf, brd, row_r, 2 if is_sel else 1, border_radius=6)
            portrait = self._portraits_sm.get(card["name"])
            txt_x = row_r.x + 8
            if portrait:
                py = row_r.y + (row_r.h - portrait.get_height()) // 2
                ui_surf.blit(portrait, (txt_x, py))
                txt_x += portrait.get_width() + 8
            name_col = (240, 200, 55) if is_sel else (215, 195, 148)
            n_s = self._f_row.render(card["name"].upper(), True, name_col)
            ui_surf.blit(n_s, n_s.get_rect(midleft=(txt_x, row_r.centery)))

        # ── Middle panel: hero detail ──────────────────────────────────────
        pad   = int(M * 0.06)
        det_x = mid_x + pad
        det_w = M - 2 * pad
        y     = title_h + int(sh * 0.025)

        hdr = self._f_phdr.render("HERO DETAIL", True, (185, 148, 45))
        ui_surf.blit(hdr, (det_x, y))
        y += hdr.get_height() + int(sh * 0.015)

        card = next(c for c in _HERO_CARDS if c["name"] == self._chosen)

        portrait = self._portraits_lg.get(self._chosen)
        if portrait:
            px = mid_x + (M - portrait.get_width()) // 2
            # Warm backdrop so sprites read against the dark bg
            back = pygame.Surface((portrait.get_width() + 12, portrait.get_height() + 12), pygame.SRCALPHA)
            back.fill((45, 34, 10, 160))
            ui_surf.blit(back, (px - 6, y - 6))
            ui_surf.blit(portrait, (px, y))
            y += portrait.get_height() + int(sh * 0.012)

        n_s = self._f_det_name.render(card["name"].upper(), True, (240, 200, 55))
        ui_surf.blit(n_s, n_s.get_rect(centerx=mid_x + M // 2, top=y))
        y += n_s.get_height() + 4

        d_s = self._f_det_desc.render(card["desc"], True, (165, 148, 105))
        ui_surf.blit(d_s, d_s.get_rect(centerx=mid_x + M // 2, top=y))
        y += d_s.get_height() + int(sh * 0.012)

        pygame.draw.line(ui_surf, (78, 58, 14), (det_x, y), (det_x + det_w, y))
        y += int(sh * 0.01)

        stat_items = list(card["stats"].items())
        col_w = det_w // 2
        for idx, (lbl, val) in enumerate(stat_items):
            col_i = idx % 2
            row_i = idx // 2
            sx = det_x + col_i * col_w
            sy = y + row_i * int(sh * 0.026)
            l_s = self._f_stat_lbl.render(f"{lbl}:", True, (148, 128, 72))
            v_s = self._f_stat_val.render(str(val), True, (228, 212, 158))
            ui_surf.blit(l_s, (sx, sy))
            ui_surf.blit(v_s, (sx + l_s.get_width() + 4, sy))
        y += ((len(stat_items) + 1) // 2) * int(sh * 0.026) + int(sh * 0.012)

        pygame.draw.line(ui_surf, (78, 58, 14), (det_x, y), (det_x + det_w, y))
        y += int(sh * 0.01)

        ab_hdr = self._f_ab_hdr.render("ABILITIES", True, (185, 148, 45))
        ui_surf.blit(ab_hdr, ab_hdr.get_rect(centerx=mid_x + M // 2, top=y))
        y += ab_hdr.get_height() + int(sh * 0.008)

        for key, name, desc in card["abilities"]:
            key_sz = int(sh * 0.024)
            key_r  = pygame.Rect(det_x, y + 2, key_sz, key_sz)
            pygame.draw.rect(ui_surf, (52, 38, 10), key_r, border_radius=4)
            pygame.draw.rect(ui_surf, (118, 90, 22), key_r, 1, border_radius=4)
            k_s = self._f_ab_key.render(key, True, (235, 200, 80))
            ui_surf.blit(k_s, k_s.get_rect(center=key_r.center))
            n_s = self._f_ab_name.render(name, True, (215, 185, 95))
            ui_surf.blit(n_s, (det_x + key_sz + 6, y + 2))
            d_s = self._f_ab_desc.render(desc, True, (148, 132, 88))
            ui_surf.blit(d_s, (det_x + key_sz + 6, y + 2 + n_s.get_height() + 2))
            y += int(sh * 0.044)

        # ── Items section ──────────────────────────────────────────────────
        pygame.draw.line(ui_surf, (78, 58, 14), (det_x, y), (det_x + det_w, y))
        y += int(sh * 0.010)

        itm_hdr = self._f_ab_hdr.render("ITEMS", True, (185, 148, 45))
        ui_surf.blit(itm_hdr, itm_hdr.get_rect(centerx=mid_x + M // 2, top=y))
        y += itm_hdr.get_height() + int(sh * 0.010)

        icon_sz  = 28
        crd_gap  = int(det_w * 0.025)
        icrd_w   = (det_w - 2 * crd_gap) // 3
        icrd_h   = icon_sz + int(sh * 0.016)
        row_gap  = int(sh * 0.007)

        for idx, ikey in enumerate(ITEM_KEYS):
            col    = idx % 3
            row    = idx // 3
            icrd_x = det_x + col * (icrd_w + crd_gap)
            icrd_y = y + row * (icrd_h + row_gap)
            icrd_r = pygame.Rect(icrd_x, icrd_y, icrd_w, icrd_h)
            self._item_card_rects[ikey] = icrd_r

            is_itm_sel = self._sel_item == ikey
            is_itm_hov = icrd_r.collidepoint(mx, my)

            ibg = pygame.Surface((icrd_w, icrd_h), pygame.SRCALPHA)
            if is_itm_sel:
                ibg.fill((100, 76, 18, 225))
            elif is_itm_hov:
                ibg.fill((56, 42, 12, 190))
            else:
                ibg.fill((36, 27, 8,  165))
            ui_surf.blit(ibg, icrd_r.topleft)
            ibrd = (220, 175, 38) if is_itm_sel else (95, 72, 18) if is_itm_hov else (65, 50, 14)
            pygame.draw.rect(ui_surf, ibrd, icrd_r, 2 if is_itm_sel else 1, border_radius=4)

            icon = self._item_icons.get(ikey)
            ix   = icrd_x + 5
            iy   = icrd_y + (icrd_h - icon_sz) // 2
            if icon:
                ui_surf.blit(icon, (ix, iy))
            tx    = ix + icon_sz + 5
            nc    = (240, 200, 55) if is_itm_sel else (215, 192, 138)
            nm_s  = self._f_srv_sm.render(ikey, True, nc)
            cst_s = self._f_srv_sm.render(f"{ITEMS[ikey]['cost']}g", True, (145, 125, 68))
            mid_y = icrd_y + icrd_h // 2
            ui_surf.blit(nm_s,  (tx, mid_y - nm_s.get_height() - 1))
            ui_surf.blit(cst_s, (tx, mid_y + 1))

        rows_n = (len(ITEM_KEYS) + 2) // 3
        y += rows_n * (icrd_h + row_gap) + int(sh * 0.010)

        # Selected item detail
        if self._sel_item:
            item = ITEMS[self._sel_item]
            pygame.draw.line(ui_surf, (78, 58, 14), (det_x, y), (det_x + det_w, y))
            y += int(sh * 0.008)
            sel_nm  = self._f_ab_name.render(self._sel_item, True, (240, 200, 55))
            sel_cst = self._f_srv_sm.render(f"{item['cost']}g", True, (165, 148, 88))
            ui_surf.blit(sel_nm,  (det_x, y))
            ui_surf.blit(sel_cst, (det_x + det_w - sel_cst.get_width(), y))
            y += sel_nm.get_height() + int(sh * 0.005)
            dsc_s = self._f_ab_desc.render(item["desc"], True, (148, 132, 88))
            ui_surf.blit(dsc_s, (det_x, y))

        # ── Right panel: servers ───────────────────────────────────────────
        pad_r = int(right_w * 0.07)
        srv_x = right_x + pad_r
        yr    = title_h + int(sh * 0.025)

        hdr = self._f_phdr.render("SERVERS", True, (185, 148, 45))
        ui_surf.blit(hdr, (srv_x, yr))

        for i, (srv, card_r) in enumerate(zip(self._servers, self._server_card_rects)):
            info   = self._server_infos[i]
            online = info.get("online")
            is_sel = self._sel_server == i
            is_hov = card_r.collidepoint(mx, my)

            if is_sel:
                bg_col  = (80, 60, 14, 225)
                brd_col = (220, 175, 38)
            elif is_hov:
                bg_col  = (50, 38, 11, 200)
                brd_col = (100, 76, 20)
            else:
                bg_col  = (32, 24, 7,  200)
                brd_col = (68, 52, 14)
            card_surf = pygame.Surface((card_r.w, card_r.h), pygame.SRCALPHA)
            card_surf.fill(bg_col)
            ui_surf.blit(card_surf, card_r.topleft)
            pygame.draw.rect(ui_surf, brd_col, card_r, 2 if is_sel else 1, border_radius=6)

            inner_x = card_r.x + int(right_w * 0.07)
            dot_cy  = card_r.y + int(sh * 0.024)

            if online is None:
                dot_col = (100, 88, 48)
            elif online:
                phase   = info.get("game_phase", "waiting")
                dot_col = (55, 210, 80) if phase == "waiting" else (215, 175, 40)
            else:
                dot_col = (205, 55, 55)
            pygame.draw.circle(ui_surf, dot_col, (inner_x, dot_cy + 7), 6)

            name_col = (240, 200, 55) if is_sel else (210, 192, 142)
            srv_n = self._f_srv.render(srv["name"], True, name_col)
            ui_surf.blit(srv_n, (inner_x + 16, dot_cy))

            ping_ms = info.get("ping_ms")
            if online and ping_ms is not None:
                if ping_ms < 50:
                    ping_col = (60, 220, 90)
                elif ping_ms < 100:
                    ping_col = (220, 210, 60)
                elif ping_ms < 150:
                    ping_col = (225, 145, 40)
                else:
                    ping_col = (215, 60, 60)
                ping_s = self._f_srv_sm.render(f"{ping_ms} ms", True, ping_col)
                ui_surf.blit(ping_s, ping_s.get_rect(right=card_r.right - int(right_w * 0.07),
                                                      centery=dot_cy + srv_n.get_height() // 2))

            cy = dot_cy + srv_n.get_height() + int(sh * 0.012)

            addr_s = self._f_srv_sm.render(srv["addr"], True, (118, 100, 55))
            ui_surf.blit(addr_s, (inner_x, cy))
            cy += addr_s.get_height() + int(sh * 0.010)

            if online is None:
                st_txt = "Checking..."
                st_col = (118, 105, 62)
            elif online:
                pc    = info.get("player_count", 0)
                max_p = info.get("max_players", 6)
                phase = info.get("game_phase", "waiting")
                pc_s  = self._f_srv.render(f"{pc} / {max_p} players", True, (192, 172, 118))
                ui_surf.blit(pc_s, (inner_x, cy))
                cy   += pc_s.get_height() + int(sh * 0.005)
                st_txt = phase.upper()
                st_col = (80, 195, 90) if phase == "waiting" else (205, 168, 45)
            else:
                st_txt = "OFFLINE"
                st_col = (200, 68, 68)
            st_s = self._f_srv.render(st_txt, True, st_col)
            ui_surf.blit(st_s, (inner_x, cy))

        # CONNECT button
        sel_online  = self._server_infos[self._sel_server].get("online")
        can_connect = sel_online is True
        btn_r       = self._connect_rect
        is_hov_btn  = btn_r.collidepoint(mx, my)
        if can_connect:
            btn_bg  = (175, 132, 22) if is_hov_btn else (148, 110, 16)
            btn_brd = (235, 192, 48)
            btn_tc  = (255, 245, 185)
        else:
            btn_bg  = (30, 22, 6)
            btn_brd = (65, 50, 14)
            btn_tc  = (88, 74, 32)
        pygame.draw.rect(ui_surf, btn_bg,  btn_r, border_radius=8)
        pygame.draw.rect(ui_surf, btn_brd, btn_r, 2, border_radius=8)
        btn_s = self._f_btn.render("CONNECT", True, btn_tc)
        ui_surf.blit(btn_s, btn_s.get_rect(center=btn_r.center))


#-------------------------------------------------------------------------------------------------------------------Connecting
class SceneConnecting:
    def __init__(self, host, port, hero_name):
        self.next_scene = self
        self._hero_name = hero_name
        self._host      = host
        self._port      = port
        self._font      = pygame.font.SysFont("arial", 22)
        self._error     = None
        asyncio.create_task(self._connect())

    async def _connect(self):
        try:
            client = NetworkClient(self._host, self._port, SNAPSHOT_INTERVAL)
            await client.connect()
            await client.send_hero_select(self._hero_name)
            asyncio.create_task(client.receive_loop())
            ok = await client.wait_for_welcome()
            if not ok:
                err = client.latest_snapshot
                if err.get("type") == "error":
                    self._error = err.get("msg", "Connection rejected by server.")
                else:
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
                self.next_scene = SceneMenu()

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



#-------------------------------------------------------------------------------------------------------------------Game
class SceneTest(SceneBase):
    def __init__(self, client):
        super().__init__(client)
        self.dx = 0
        self.dy = 0
        self.input_send_timer  = 0.0
        self._last_sent_input  = (0, 0)
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
        self._shop_sel  = None

        # End-of-game auto-return timer
        self._end_timer   = None
        # Quit confirmation overlay
        self._quit_confirm = False

        # Clamped placement cursor (world pos), set each render frame, read in process_input
        self._clamped_placement_pos = None

        # World sprites (pre-scaled to actual in-game sizes)
        self._turret_img  = self._load_asset("turret.png",       (32, 32))
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
        self._bolt_img      = self._load_asset("bolt.png",       (20, 5))
        self.status_fx      = StatusEffectRenderer(self._load_asset)
        self._trap_img      = self._load_asset("trap.png",       (16, 16))

        # Lobby / ready state
        self._my_ready = False

        self._font_floater   = pygame.font.SysFont("consolas", 14, bold=True)
        self._font_label     = pygame.font.SysFont("consolas", 10)
        self._font_timer     = pygame.font.SysFont("consolas", 28, bold=True)
        self._font_kda       = pygame.font.SysFont("consolas", 18, bold=True)
        self._font_kda_sm    = pygame.font.SysFont("consolas", 11)
        self._font_score_hdr = pygame.font.SysFont("consolas", 16, bold=True)
        self._font_score_row = pygame.font.SysFont("consolas", 13)

        # Scoreboard
        self._scoreboard_open = False

        # Visual effects
        self.effects              = EffectsSystem(self._font_floater)
        self._last_proc_snap      = 0.0
        self._local_attack_target = None   # (target_type, target_id) — drives indicator ring
        self._hovered_target      = None   # (target_type, target_id) — enemy under cursor
        self._vfx_time            = 0.0    # monotonic clock for pulsing animations

        #Screen shake
        self._shake_timer     = 0.0
        self._shake_duration  = 0.3
        self._shake_intensity = 0.0
        self._shake_ox        = 0
        self._shake_oy        = 0

        #Stealth shimmer transitions  pid -> countdown timer
        self._stealth_shimmer = {}
        self._prev_invisible  = {}

        #Ground Slam onset tracking (to fire shake on first ring frame)
        self._prev_slam_active = set()

        #Projectile trail history  (type_str, pid) -> list[(wx, wy)]
        self._proj_trails  = {}
        self._trail_surf   = pygame.Surface((VIEWPORT_W, VIEWPORT_H), pygame.SRCALPHA)

    def _load_asset(self, filename, size=None):
        path = os.path.join(_ROOT, "asset", filename)
        if not os.path.exists(path):
            return None
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        return img

    def _w2s(self, wx, wy):
        return int(wx - self.cam_x + self._shake_ox), int(wy - self.cam_y + self._shake_oy)

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
                    # Right-click on shop icon → buy instantly
                    _shop_bought = False
                    if self._shop_open:
                        for _ikey, _ir in self.hud.shop_icon_rects:
                            if _ir.collidepoint(sx, sy):
                                asyncio.create_task(self.client.send_buy_item(_ikey))
                                _shop_bought = True
                                break
                    if not _shop_bought:
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
                    elif self._shop_open:
                        # Check icon grid selection
                        _icon_hit = False
                        for _ikey, _ir in self.hud.shop_icon_rects:
                            if _ir.collidepoint(sx, sy):
                                self._shop_sel = _ikey
                                _icon_hit = True
                                break
                        # Check BUY button
                        if not _icon_hit and self.hud.shop_buy_rect and self.hud.shop_buy_rect.collidepoint(sx, sy):
                            if self._shop_sel:
                                asyncio.create_task(self.client.send_buy_item(self._shop_sel))
                            _icon_hit = True
                        # Click outside panel closes shop
                        if not _icon_hit:
                            self._shop_open = False
                            self._shop_sel  = None
                    elif self.hud.geometry["shop_rect"].collidepoint(sx, sy):
                        self._shop_open = not self._shop_open
                        if not self._shop_open:
                            self._shop_sel = None
                    elif mini_rect_screen.collidepoint(sx, sy):
                        self._handle_minimap_click(sx - 8, sy - (_SCREEN_H - MINI_H - 8))
                    else:
                        self._handle_click((sx / _SCALE_X, sy / _SCALE_Y))
            if event.type == pygame.KEYDOWN:
                # Quit-confirm overlay intercepts all keys when active
                if self._quit_confirm:
                    if event.key == pygame.K_y:
                        self.next_scene = None
                    elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                        self._quit_confirm = False
                    continue

                # Return-to-menu key on winner screen
                _snap_check = self.client.latest_snapshot
                if _snap_check.get("winner") is not None and event.key == pygame.K_m:
                    self.next_scene = SceneMenu()
                    continue

                match event.key:
                    case pygame.K_q:      self._handle_ability_key(0)
                    case pygame.K_e:      self._handle_ability_key(1)
                    case pygame.K_r:      self._handle_ability_key(2)
                    case pygame.K_b:      self._handle_ability_key(3)
                    case pygame.K_c:      self._show_range = not self._show_range
                    case pygame.K_h:      self._show_debug = not self._show_debug
                    case pygame.K_SPACE:  self._cam_locked = True
                    case pygame.K_TAB:    self._scoreboard_open = not self._scoreboard_open
                    case pygame.K_ESCAPE:
                        if self._shop_open:
                            self._shop_open = False
                            self._shop_sel  = None
                        elif self._placement_mode is not None or self._entity_target_mode is not None:
                            self._placement_mode     = None
                            self._entity_target_mode = None
                        else:
                            self._quit_confirm = True

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
        if ability.get("is_on_cooldown"):
            return
        if ability.get("is_placement") or ability.get("is_point_cast"):
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
                if dx*dx + dy*dy <= 400:
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

        for tid, t in snap.get("traps", {}).items():
            if t.get("team") == self.client.my_team:
                continue
            if t.get("revealed_timer", 0) <= 0:
                continue
            half = t.get("size", 16) / 2
            dx, dy = wx - t["x"], wy - t["y"]
            if abs(dx) <= half + 4 and abs(dy) <= half + 4:
                self._set_attack_target("trap", tid)
                return

    def update(self, dt):
        super().update(dt)

        # Return to menu when server closes the connection
        if not self.client.is_connected:
            self.next_scene = SceneMenu()
            return

        # Auto-return to menu 8 s after game ends
        snap_early = self.client.latest_snapshot
        if snap_early.get("winner") is not None:
            if self._end_timer is None:
                self._end_timer = 8.0
            self._end_timer -= dt
            if self._end_timer <= 0:
                self.next_scene = SceneMenu()
                return

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
            has_event        = attack is not None or ability is not None or ability_target is not None or ability_target_id is not None
            movement_changed = (self.dx, self.dy) != self._last_sent_input
            if has_event or movement_changed:
                self._last_sent_input = (self.dx, self.dy)
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
                    vision = b.get("vision", 0)
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
            for ev in self.effects.process_snapshot(snap, self.client.my_player_id, self.client.my_team,
                                                    self._is_visible, self._is_on_screen):
                if ev["type"] == "death":
                    self._trigger_shake(3.0, 0.3)

        # Clear indicator if the target has died or been destroyed
        if self._local_attack_target:
            ttype, tid = self._local_attack_target
            if target_is_gone(ttype, tid, snap):
                self._local_attack_target = None

        # Hover detection — enemy under mouse cursor
        mx_raw, my_raw = pygame.mouse.get_pos()
        mx_vp = mx_raw / _SCALE_X
        my_vp = my_raw / _SCALE_Y
        wx_h  = mx_vp + self.cam_x
        wy_h  = my_vp + self.cam_y
        self._hovered_target = None
        my_bush = snap.get("players", {}).get(self.client.my_player_id, {}).get("bush_idx", -1)
        for pid, p_data in snap.get("players", {}).items():
            if pid == self.client.my_player_id:
                continue
            if p_data.get("is_dead"):
                continue
            if p_data.get("is_invisible") and not p_data.get("revealed_timer", 0) > 0:
                continue
            enemy_bush = p_data.get("bush_idx", -1)
            if enemy_bush >= 0 and enemy_bush != my_bush:
                continue
            pos = self.client.get_interpolated_pos("players", pid)
            if pos and self._is_visible(pos[0], pos[1]):
                dx, dy = wx_h - pos[0], wy_h - pos[1]
                if dx*dx + dy*dy <= 400:
                    self._hovered_target = ("player", pid)
                    break

        self.effects.tick(dt)
        self._vfx_time += dt

        # Screen shake decay
        if self._shake_timer > 0:
            self._shake_timer = max(0.0, self._shake_timer - dt)
            frac = self._shake_timer / self._shake_duration
            amp  = self._shake_intensity * frac
            self._shake_ox = int(amp * math.sin(self._vfx_time * 43))
            self._shake_oy = int(amp * math.cos(self._vfx_time * 37))
        else:
            self._shake_ox = 0
            self._shake_oy = 0

        # Stealth shimmer transitions
        for pid, p_data in snap.get("players", {}).items():
            curr_invis = p_data.get("is_invisible", False)
            if self._prev_invisible.get(pid) != curr_invis:
                self._stealth_shimmer[pid] = 0.4
            self._prev_invisible[pid] = curr_invis
        self._stealth_shimmer = {pid: t - dt for pid, t in self._stealth_shimmer.items() if t - dt > 0}

        # Ground Slam shake — trigger on the first frame ring becomes active
        curr_slam = {pid for pid, p in snap.get("players", {}).items()
                     if any(ab and ab.get("name") == "GroundSlam" and ab.get("ring_active")
                            for ab in p.get("abilities", []))}
        if curr_slam - self._prev_slam_active:
            self._trigger_shake(2.0, 0.25)
        self._prev_slam_active = curr_slam

    def _draw_proj_trail(self, key, wx, wy, color, dot_size, max_len):
        """Append (wx, wy) to the trail for key and draw past positions to self._trail_surf."""
        trail = self._proj_trails.setdefault(key, [])
        trail.append((wx, wy))
        if len(trail) > max_len:
            del trail[0]
        n = len(trail)
        if n < 2:
            return
        r, g, b = color
        for i, (twx, twy) in enumerate(trail[:-1]):
            frac = (i + 1) / n
            alpha = int(170 * frac)
            size  = max(1, int(dot_size * frac))
            tsx, tsy = self._w2s(twx, twy)
            if 0 <= tsx < VIEWPORT_W and 0 <= tsy < VIEWPORT_H:
                pygame.draw.circle(self._trail_surf, (r, g, b, alpha), (tsx, tsy), size)

    def _trigger_shake(self, intensity, duration):
        """Start a screen shake if the new shake would be stronger than the current one."""
        curr_strength = self._shake_intensity * (self._shake_timer / max(self._shake_duration, 0.001))
        if intensity > curr_strength:
            self._shake_intensity = intensity
            self._shake_duration  = duration
            self._shake_timer     = duration

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
        screen.blit(self.map_bg, (-int(self.cam_x) + self._shake_ox, -int(self.cam_y) + self._shake_oy))

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
            if btype == "Tower":
                col = TEAM_COLOURS.get(b.get("team"), (180, 180, 180))
                pygame.draw.rect(screen, col, (sx, sy, bs, bs))
                inner = max(4, bs // 3)
                offset = (bs - inner) // 2
                pygame.draw.rect(screen, (20, 20, 20), (sx + offset, sy + offset, inner, inner))
                if b["hp"] < b["max_hp"]:
                    self._draw_hp_bar(screen, sx, sy - 8, bs, b["hp"], b["max_hp"])
                continue
            hq_img = self._hq_imgs.get(b.get("team")) if btype == "BuildingHeadquarter" else None
            if hq_img:
                screen.blit(hq_img, (sx, sy))
            if b.get("is_invulnerable"):
                pygame.draw.rect(screen, (255, 220, 60), (sx - 3, sy - 3, bs + 6, bs + 6), 2)
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
                pulse    = 0.5 + 0.5 * math.sin(self._vfx_time * 3.5)
                inner_r  = int(6 + pulse * 2)
                out_surf = pygame.Surface((38, 38), pygame.SRCALPHA)
                pygame.draw.circle(out_surf, (140, 60, 200, int(120 + 80 * pulse)), (19, 19), 16, 3)
                screen.blit(out_surf, (rx - 19, ry - 19))
                pygame.draw.circle(screen, (200, 130, 255), (rx, ry), inner_r)
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

            #Hook channel — pulsing orange ring that fills as channel completes
            hook_ab = next((ab for ab in abilities
                            if ab and ab.get("name") == "Hook" and ab.get("is_channeling")), None)
            if hook_ab:
                elapsed   = hook_ab["channel_time"] - hook_ab["channel_timer"]
                progress  = elapsed / max(hook_ab["channel_time"], 0.001)
                arc_angle = 2 * math.pi * progress
                r = 20
                pygame.draw.circle(screen, (80, 40, 10), (sx, sy), r, 1)
                if arc_angle > 0.05:
                    pygame.draw.arc(screen, (255, 160, 40),
                                    pygame.Rect(sx - r, sy - r, r * 2, r * 2),
                                    math.pi / 2, math.pi / 2 + arc_angle, 3)

            #Hero sprite — with stealth transparency and shimmer transition
            hero = p_data.get("hero", "Player")
            img  = self._get_hero_image(hero)
            if img:
                shimmer_t = self._stealth_shimmer.get(pid, 0)
                if shimmer_t > 0:
                    flicker = abs(math.sin(shimmer_t * 28))
                    s_copy  = img.copy()
                    s_copy.set_alpha(int(55 + 200 * flicker))
                    screen.blit(s_copy, (sx - 16, sy - 16))
                    _shim = pygame.Surface((32, 32), pygame.SRCALPHA)
                    _shim.fill((180, 140, 255, int(100 * flicker)))
                    screen.blit(_shim, (sx - 16, sy - 16))
                elif is_invisible and not enemy:
                    s_copy = img.copy()
                    s_copy.set_alpha(80)
                    screen.blit(s_copy, (sx - 16, sy - 16))
                else:
                    screen.blit(img, (sx - 16, sy - 16))
            else:
                pygame.draw.circle(screen, TEAM_COLOURS.get(p_data.get("team"), (255, 255, 255)), (sx, sy), 8)

            self.effects.draw_hit_flash(screen, pid, sx, sy)

            self._draw_hp_bar(screen, sx - 15, sy - 20, 30, p_data.get("hp", 1), p_data.get("max_hp", 1))

            #Class label above HP bar
            lbl_surf = self._font_label.render(hero[:3].upper(), True,
                                               TEAM_COLOURS.get(p_data.get("team"), (200, 200, 200)))
            screen.blit(lbl_surf, lbl_surf.get_rect(centerx=sx, bottom=sy - 22))

            self.status_fx.draw(screen, p_data, sx, sy, self._vfx_time)

        for t in snap.get("turrets", {}).values():
            if t.get("is_destroyed"):
                continue
            tx, ty = t["x"], t["y"]
            if t.get("team") != my_team and not self._is_visible(tx, ty):
                continue
            tsx, tsy = self._w2s(tx, ty)
            sz = t.get("size", 20)
            if self._turret_img:
                screen.blit(self._turret_img, (tsx, tsy))
            else:
                col = TEAM_COLOURS.get(t.get("team"), (180, 180, 180))
                cx2, cy2 = tsx + sz // 2, tsy + sz // 2
                pts = [
                    (cx2,          tsy),
                    (tsx + sz,     cy2),
                    (cx2,          tsy + sz),
                    (tsx,          cy2),
                ]
                pygame.draw.polygon(screen, col, pts)
                pygame.draw.polygon(screen, (200, 200, 210), pts, 1)
            if t.get("hp", t.get("max_hp", 1)) < t.get("max_hp", 1):
                self._draw_hp_bar(screen, tsx, tsy - 6, sz, t.get("hp", 0), t.get("max_hp", 1))


        # ── Projectile trails pass — draw all trails to trail_surf first ────────
        self._trail_surf.fill((0, 0, 0, 0))
        active_trail_keys = set()

        for pid, proj in snap.get("projectiles", {}).items():
            pos = self.client.get_interpolated_xy("projectiles", pid)
            if pos is None:
                continue
            key = ("proj", pid)
            active_trail_keys.add(key)
            if proj.get("is_fated_missile"):
                self._draw_proj_trail(key, pos[0], pos[1], (160, 60, 220), 3, 8)
            elif proj.get("is_net") and not proj.get("is_landed"):
                self._draw_proj_trail(key, pos[0], pos[1], (80, 200, 100), 3, 6)
            else:
                self._draw_proj_trail(key, pos[0], pos[1], (220, 220, 200), 2, 5)

        for pid, fp in snap.get("fireball_projectiles", {}).items():
            pos = self.client.get_interpolated_xy("fireball_projectiles", pid)
            if pos is None:
                continue
            key = ("fb", pid)
            active_trail_keys.add(key)
            self._draw_proj_trail(key, pos[0], pos[1], (255, 140, 20), 4, 8)

        for pid, bp in snap.get("bolt_projectiles", {}).items():
            key = ("bolt", pid)
            active_trail_keys.add(key)
            self._draw_proj_trail(key, bp["x"], bp["y"], (200, 200, 230), 2, 6)

        for pid, hp in snap.get("hook_projectiles", {}).items():
            key = ("hook", pid)
            active_trail_keys.add(key)
            self._draw_proj_trail(key, hp["x"], hp["y"], (210, 110, 20), 2, 5)

        screen.blit(self._trail_surf, (0, 0))
        self._proj_trails = {k: v for k, v in self._proj_trails.items() if k in active_trail_keys}

        # ── Projectile sprites ───────────────────────────────────────────────
        for pid, proj in snap.get("projectiles", {}).items():
            pos = self.client.get_interpolated_xy("projectiles", pid)
            if pos is None:
                continue
            sx, sy = self._w2s(pos[0], pos[1])
            if proj.get("is_net"):
                r = proj.get("radius", 40)
                if proj.get("is_landed"):
                    net_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(net_surf, (60, 180, 80, 80), (r + 2, r + 2), r)
                    pygame.draw.circle(net_surf, (100, 230, 120), (r + 2, r + 2), r, 2)
                    screen.blit(net_surf, (sx - r - 2, sy - r - 2))
                else:
                    pygame.draw.circle(screen, (60, 160, 70), (sx, sy), 7)
                    pygame.draw.circle(screen, (120, 240, 140), (sx, sy), 7, 2)
            elif proj.get("is_fated_missile"):
                pygame.draw.circle(screen, (100, 20, 180), (sx, sy), 6)
                pygame.draw.circle(screen, (210, 130, 255), (sx, sy), 6, 2)
            elif self._bullet_img:
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

        #Traps — allied always visible; enemy traps visible when revealed by Eagle Eye
        for trap in snap.get("traps", {}).values():
            is_allied   = trap.get("team") == my_team
            is_revealed = trap.get("revealed_timer", 0) > 0
            if not is_allied and not is_revealed:
                continue
            tx, ty = self._w2s(trap["x"], trap["y"])
            half = trap.get("size", 16) // 2
            if self._trap_img:
                screen.blit(self._trap_img, (tx - half, ty - half))
            else:
                col = (160, 120, 20) if is_allied else (180, 40, 40)
                pygame.draw.rect(screen, col, (tx - half, ty - half, half * 2, half * 2))
            if not is_allied:
                pygame.draw.rect(screen, (255, 80, 80), (tx - half - 1, ty - half - 1, half * 2 + 2, half * 2 + 2), 1)

        #Bolt projectiles — slow rotating sprite
        for pid, bp in snap.get("bolt_projectiles", {}).items():
            bx, by = self._w2s(bp["x"], bp["y"])
            angle  = bp.get("angle", 0)
            if self._bolt_img:
                rotated = pygame.transform.rotate(self._bolt_img, angle)
                screen.blit(rotated, rotated.get_rect(center=(bx, by)))
            else:
                team_col = TEAM_COLOURS.get(bp.get("owner_team"), (200, 200, 100))
                pygame.draw.rect(screen, team_col, (bx - 10, by - 2, 20, 4))

        #Hook projectiles — orange circle
        for pid, hp in snap.get("hook_projectiles", {}).items():
            hx, hy = self._w2s(hp["x"], hp["y"])
            pygame.draw.circle(screen, (210, 110, 20), (hx, hy), 5)
            pygame.draw.circle(screen, (255, 190, 60), (hx, hy), 5, 2)

        # Placement / point-cast aim overlay
        if self._placement_mode is not None:
            snap      = self.client.latest_snapshot
            my_data   = snap.get("players", {}).get(self.client.my_player_id, {})
            abilities  = my_data.get("abilities", [])
            ability    = abilities[self._placement_mode] if self._placement_mode < len(abilities) else None
            is_point_cast = ability.get("is_point_cast", False) if ability else False
            aim_range = (ability.get("cast_range") or ability.get("place_range") or 50) if ability else 50

            my_pos = self.client.get_interpolated_pos("players", self.client.my_player_id)
            smx, smy = pygame.mouse.get_pos()
            wx = smx / _SCALE_X + self.cam_x
            wy = smy / _SCALE_Y + self.cam_y

            # Clamp world cursor to aim_range radius
            if my_pos:
                ddx = wx - my_pos[0]
                ddy = wy - my_pos[1]
                dist_sq = ddx * ddx + ddy * ddy
                if dist_sq > aim_range ** 2:
                    dist = math.sqrt(dist_sq)
                    wx = my_pos[0] + ddx / dist * aim_range
                    wy = my_pos[1] + ddy / dist * aim_range
            self._clamped_placement_pos = (wx, wy)

            cx, cy = self._w2s(wx, wy)

            if my_pos:
                px_v, py_v = self._w2s(my_pos[0], my_pos[1])

                if is_point_cast:
                    # Hook: range ring + aim line from player to cursor
                    pygame.draw.circle(screen, (200, 140, 30), (px_v, py_v), int(aim_range), 1)
                    pygame.draw.line(screen, (220, 160, 40), (px_v, py_v), (cx, cy), 2)
                    pygame.draw.circle(screen, (220, 160, 40), (cx, cy), 5, 2)
                else:
                    pygame.draw.circle(screen, (80, 80, 90), (px_v, py_v), int(aim_range), 1)

            if not is_point_cast:
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

        # Hover ring — white circle on enemy under cursor
        if self._hovered_target and self._hovered_target != self._local_attack_target:
            _ht, _hid = self._hovered_target
            _hpos = self.client.get_interpolated_pos("players", _hid) if _ht == "player" else None
            if _hpos:
                _hsx, _hsy = self._w2s(_hpos[0], _hpos[1])
                pygame.draw.circle(screen, (220, 220, 220), (_hsx, _hsy), 18, 1)

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
            shop_sel=self._shop_sel,
            end_countdown=self._end_timer,
            quit_confirm=self._quit_confirm,
        )

        game_phase = snap.get("game_phase", "live")
        if game_phase == "live":
            self._render_timer(ui_surf, snap)
            self._render_own_kda(ui_surf, my_data)

        if self._scoreboard_open:
            self._render_scoreboard(ui_surf, snap)

    def _render_timer(self, ui_surf, snap):
        t       = int(snap.get("match_time", 0))
        t_str   = f"{t // 60:02d}:{t % 60:02d}"
        t_surf  = self._font_timer.render(t_str, True, (230, 220, 190))
        t_rect  = t_surf.get_rect(centerx=_SCREEN_W // 2, top=10)
        bg      = pygame.Surface((t_rect.w + 20, t_rect.h + 8), pygame.SRCALPHA)
        bg.fill((8, 8, 18, 170))
        pygame.draw.rect(bg, (60, 56, 44, 200), (0, 0, bg.get_width(), bg.get_height()), 1)
        ui_surf.blit(bg, (t_rect.x - 10, t_rect.y - 4))
        ui_surf.blit(t_surf, t_rect)

    def _render_own_kda(self, ui_surf, my_data):
        k = my_data.get("kills",   0)
        d = my_data.get("deaths",  0)
        a = my_data.get("assists", 0)
        kda_surf  = self._font_kda.render(f"{k}  /  {d}  /  {a}", True, (225, 215, 185))
        lbl_surf  = self._font_kda_sm.render("K   /   D   /   A", True, (130, 122, 95))
        pad = 16
        kda_rect  = kda_surf.get_rect(right=_SCREEN_W - pad, top=12)
        lbl_rect  = lbl_surf.get_rect(right=_SCREEN_W - pad, top=kda_rect.bottom + 3)
        bg_w  = max(kda_rect.w, lbl_rect.w) + 20
        bg_h  = lbl_rect.bottom - kda_rect.top + 8
        bg    = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        bg.fill((8, 8, 18, 170))
        pygame.draw.rect(bg, (60, 56, 44, 200), (0, 0, bg_w, bg_h), 1)
        ui_surf.blit(bg, (_SCREEN_W - pad - bg_w + 10, kda_rect.top - 4))
        ui_surf.blit(kda_surf, kda_rect)
        ui_surf.blit(lbl_surf, lbl_rect)

    def _render_scoreboard(self, ui_surf, snap):
        players_data = snap.get("players", {})
        team_1 = [(pid, pd) for pid, pd in players_data.items() if pd.get("team") == 1]
        team_2 = [(pid, pd) for pid, pd in players_data.items() if pd.get("team") == 2]

        ov_w, ov_h = 740, 380
        ov_x = _SCREEN_W // 2 - ov_w // 2
        ov_y = _SCREEN_H // 2 - ov_h // 2

        ov = pygame.Surface((ov_w, ov_h), pygame.SRCALPHA)
        ov.fill((8, 10, 22, 225))
        pygame.draw.rect(ov, (55, 52, 75, 255), (0, 0, ov_w, ov_h), 2)

        title = self._font_score_hdr.render("SCOREBOARD", True, (215, 205, 175))
        ov.blit(title, title.get_rect(centerx=ov_w // 2, top=10))

        col_x = {"hero": 12, "k": 200, "d": 256, "a": 312, "items": 370}
        hdr_y = 36
        for lbl, cx in [("Hero", col_x["hero"]), ("K", col_x["k"]),
                         ("D", col_x["d"]), ("A", col_x["a"]), ("Items", col_x["items"])]:
            s = self._font_score_row.render(lbl, True, (145, 135, 105))
            ov.blit(s, (cx, hdr_y))
        pygame.draw.line(ov, (55, 52, 75), (10, hdr_y + 16), (ov_w - 10, hdr_y + 16), 1)

        y = hdr_y + 22

        def _draw_row(pid, pd, name_col):
            nonlocal y
            hero = pd.get("hero", "?")
            k    = pd.get("kills",   0)
            d    = pd.get("deaths",  0)
            a    = pd.get("assists", 0)
            if pid == self.client.my_player_id:
                hl = pygame.Surface((ov_w - 4, 22), pygame.SRCALPHA)
                hl.fill((50, 80, 130, 90))
                ov.blit(hl, (2, y - 2))
            hero_s = self._font_score_row.render(hero[:16], True, name_col)
            ov.blit(hero_s, (col_x["hero"], y))
            for val, cx in [(k, col_x["k"]), (d, col_x["d"]), (a, col_x["a"])]:
                vs = self._font_score_row.render(str(val), True, (200, 200, 200))
                ov.blit(vs, (cx, y))
            inv = pd.get("inventory", [])
            ix  = col_x["items"]
            for item in inv[:6]:
                if item:
                    icon = self.hud._item_icons.get(item)
                    if icon:
                        ov.blit(pygame.transform.scale(icon, (18, 18)), (ix, y - 1))
                    else:
                        pygame.draw.rect(ov, (90, 90, 90), (ix, y - 1, 18, 18))
                else:
                    pygame.draw.rect(ov, (28, 30, 42), (ix, y - 1, 18, 18), 1)
                ix += 22
            y += 28

        t1_lbl = self._font_score_hdr.render("BLUE TEAM", True, (80, 130, 225))
        ov.blit(t1_lbl, (col_x["hero"], y))
        y += 22
        for pid, pd in team_1:
            _draw_row(pid, pd, (185, 200, 235))

        y += 10
        pygame.draw.line(ov, (40, 40, 60), (10, y), (ov_w - 10, y), 1)
        y += 10

        t2_lbl = self._font_score_hdr.render("RED TEAM", True, (225, 80, 80))
        ov.blit(t2_lbl, (col_x["hero"], y))
        y += 22
        for pid, pd in team_2:
            _draw_row(pid, pd, (235, 185, 185))

        hint = self._font_score_row.render("[TAB] close", True, (90, 88, 110))
        ov.blit(hint, hint.get_rect(centerx=ov_w // 2, bottom=ov_h - 8))

        ui_surf.blit(ov, (ov_x, ov_y))

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
            pulse   = 0.5 + 0.5 * math.sin(self._vfx_time * 2.5 + bx * 0.02)
            ring_r  = bs // 2 + 3 + int(pulse * 2)
            rsurf   = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(rsurf, (160, 120, 220, int(55 + 40 * pulse)),
                               (ring_r + 2, ring_r + 2), ring_r, 2)
            screen.blit(rsurf, (cx - ring_r - 2, cy - ring_r - 2))
        else:
            col = TEAM_COLOURS.get(0, (160, 160, 160))
            pygame.draw.circle(screen, col, (cx, cy), bs // 2)
            pygame.draw.circle(screen, (220, 220, 220), (cx, cy), bs // 2, 2)

        # HP bar — shown when owned and damaged (must destroy to flip)
        hp     = b.get("hp",     1)
        max_hp = b.get("max_hp", 1)
        if team != 0 and hp < max_hp:
            self._draw_hp_bar(screen, cx - (bs + 16) // 2, sy - 10, bs + 16, hp, max_hp)

        cap_timer = b.get("capture_timer", 0)
        cap_time  = b.get("capture_time",  5)
        cont_team = b.get("capturing_team")
        if cont_team and cap_timer > 0:
            cont_col = TEAM_COLOURS.get(cont_team, (200, 200, 200))
            bar_w    = bs + 16
            fill     = int(bar_w * (cap_timer / cap_time))
            bar_y    = sy - 17 if (team != 0 and hp < max_hp) else sy - 10
            pygame.draw.rect(screen, (40, 40, 40), (cx - bar_w // 2, bar_y, bar_w, 5))
            pygame.draw.rect(screen, cont_col,     (cx - bar_w // 2, bar_y, fill,  5))

    def _draw_hp_bar(self, screen, x, y, width, hp, max_hp):
        if max_hp <= 0:
            return
        pygame.draw.rect(screen, (80, 0, 0), (x, y, width, 4))
        pygame.draw.rect(screen, (0, 200, 80), (x, y, int(width * hp / max_hp), 4))
