import math
import pygame

from shared.constants import MAP_W, MAP_H, RUNE_X, RUNE_Y
from shared.items import ITEMS, ITEM_KEYS

#Minimap dimensions (native UI pixels)
MINI_W = 240
MINI_H = 150
MINI_SX = MINI_W / MAP_W
MINI_SY = MINI_H / MAP_H

TEAM_COLOURS = {
    1: (60, 100, 220),
    2: (220, 60, 60),
}

_ABILITY_KEYS = ["Q", "E", "R"]


#---------------------------------------------------------------------------------------------------
def build_hud_geometry(sw, sh):
    A    = 72    # ability slot size
    I    = 58    # inventory slot size
    GA   = 6     # gap between ability slots
    GI   = 6     # gap between inventory slots
    SEP  = 14    # gap between ability and inventory sections
    GW   = 76    # gold section width
    GGAP = 12    # gap between gold section and ability slots
    PX   = 14    # outer horizontal padding
    PT   = 10    # top padding
    KB   = 18    # bottom key-label row height

    HP_H    = 12
    MP_H    = 7
    BAR_GAP = 3
    BAR_BOT = 5

    RA  = A // 4      # recall mini-slot size
    RAG = 8           # gap between inventory and recall slot
    panel_w = PX + GW + GGAP + 3*A + 2*GA + SEP + 3*I + 2*GI + RAG + RA + PX
    bars_h  = HP_H + BAR_GAP + MP_H + BAR_BOT
    panel_h = PT + A + KB
    panel_x = sw // 2 - panel_w // 2
    panel_y = sh - panel_h

    slot_y = panel_y + PT
    key_y  = slot_y + A + 4

    gold_x = panel_x + PX
    a_start = gold_x + GW + GGAP
    ability_rects = [pygame.Rect(a_start + i*(A+GA), slot_y, A, A) for i in range(3)]

    i_start = a_start + 3*A + 2*GA + SEP
    inv_y   = slot_y + (A - I) // 2
    inventory_rects = [pygame.Rect(i_start + i*(I+GI), inv_y, I, I) for i in range(3)]

    div_gold = gold_x + GW + GGAP // 2
    div_inv  = i_start - SEP // 2

    bar_x   = panel_x
    bar_w   = panel_w
    hp_bar  = pygame.Rect(bar_x, panel_y - bars_h, bar_w, HP_H)
    mp_bar  = pygame.Rect(bar_x, panel_y - bars_h + HP_H + BAR_GAP, bar_w, MP_H)
    bars_bg = pygame.Rect(bar_x, panel_y - bars_h, bar_w, bars_h)

    inv_bottom  = inv_y + I
    shop_rect   = pygame.Rect(i_start, inv_bottom + 4, 3*I + 2*GI, 14)

    recall_x    = i_start + 3*I + 2*GI + RAG
    recall_y    = slot_y + (A - RA) // 2
    recall_rect = pygame.Rect(recall_x, recall_y, RA, RA)

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
        "recall_rect":     recall_rect,
    }


#---------------------------------------------------------------------------------------------------
class HudRenderer:
    def __init__(self, screen_w, screen_h, load_asset_fn, obstacles):
        self._sw = screen_w
        self._sh = screen_h

        #Geometry
        self.geometry = build_hud_geometry(screen_w, screen_h)

        #Minimap surfaces
        self._mini_terrain  = self._build_mini_terrain(obstacles)
        self._mini_fog_surf = pygame.Surface((MINI_W, MINI_H), pygame.SRCALPHA)
        self._mini_fog_surf.fill((0, 0, 0, 200))
        self._is_fog_dirty  = True

        #Game HUD fonts
        self._font_cd       = pygame.font.SysFont("consolas", 20, bold=True)
        self._font_slot_sm  = pygame.font.SysFont("consolas", 11)
        self._font_key_lbl  = pygame.font.SysFont("consolas", 12)
        self._font_mini_lbl = pygame.font.SysFont("consolas", 11)
        self._font_gold_lbl = pygame.font.SysFont("consolas", 10)
        self._font_gold_val = pygame.font.SysFont("consolas", 18, bold=True)
        self._font_bar_txt  = pygame.font.SysFont("consolas", 10)
        self._font_shop     = pygame.font.SysFont("consolas", 10)

        #Overlay fonts
        self._font_lobby_title = pygame.font.SysFont("arial", 28, bold=True)
        self._font_lobby_body  = pygame.font.SysFont("consolas", 16)
        self._font_lobby_cd    = pygame.font.SysFont("arial", 72, bold=True)
        self._font_dead_big    = pygame.font.SysFont("arial", 48, bold=True)
        self._font_dead_sub    = pygame.font.SysFont("consolas", 20)

        #Assets
        self._icon_gold = load_asset_fn("icon_gold.png", (14, 14))

        _icon_map = {
            "Snipe":       "icon_snipe.png",
            "PlaceTurret": "icon_turret.png",
        }
        _icon_sz = self.geometry["ability_rects"][0].h - 8
        self._ability_icons = {
            name: load_asset_fn(fname, (_icon_sz, _icon_sz))
            for name, fname in _icon_map.items()
        }

        #Mutable output — read by scene for click handling
        self.shop_btn_rects   = []
        self.ready_btn_rect   = None
        self.force_start_rect = None

    # ── Fog ─────────────────────────────────────────────────────────────────

    def mark_fog_dirty(self):
        self._is_fog_dirty = True

    def rebuild_fog_if_dirty(self, map_system):
        if not self._is_fog_dirty:
            return
        self._rebuild_fog(map_system)
        self._is_fog_dirty = False

    def _rebuild_fog(self, map_system):
        self._mini_fog_surf.fill((0, 0, 0, 200))
        ns = map_system.size
        nw = max(1, int(ns * MINI_SX))
        nh = max(1, int(ns * MINI_SY))
        for node in map_system.discovered_nodes:
            self._mini_fog_surf.fill((0, 0, 0, 0),
                                     (int(node.rect.x * MINI_SX), int(node.rect.y * MINI_SY), nw, nh))
        for node in map_system.building_vision_nodes:
            self._mini_fog_surf.fill((0, 0, 0, 0),
                                     (int(node.rect.x * MINI_SX), int(node.rect.y * MINI_SY), nw, nh))

    # ── Main render entry ────────────────────────────────────────────────────

    def render(self, ui_surf, snap, client, my_data,
               shop_open, my_ready, cam_x, cam_y, cam_locked, placement_mode, is_visible_fn):
        mx_ui, my_ui = pygame.mouse.get_pos()
        hud          = self.geometry
        my_pos       = client.get_interpolated_pos("players", client.my_player_id)

        self._render_vitals(ui_surf, my_data, hud)
        self._render_channel_bar(ui_surf, my_data, hud)
        self._render_panel(ui_surf, hud)
        self._render_gold(ui_surf, my_data, hud)
        self._render_ability_slots(ui_surf, my_data.get("abilities", []), hud, placement_mode, mx_ui, my_ui)
        self._render_inventory(ui_surf, my_data, hud, mx_ui, my_ui)
        self._render_recall_slot(ui_surf, my_data.get("abilities", []), hud)
        self._render_shop_button(ui_surf, hud, shop_open, mx_ui, my_ui)

        self.shop_btn_rects = []
        if shop_open:
            self._render_shop_panel(ui_surf, snap, my_data, hud, my_pos)

        self._render_minimap(ui_surf, snap, client, cam_x, cam_y, cam_locked, is_visible_fn)

        game_phase = snap.get("game_phase", "live")
        if game_phase in ("waiting", "countdown"):
            self._render_lobby_overlay(ui_surf, snap, game_phase, my_ready, mx_ui, my_ui)

        if my_data.get("is_dead") and game_phase == "live":
            self._render_dead_overlay(ui_surf, my_data, snap)

        winner = snap.get("winner")
        if winner is not None:
            self._render_victory_overlay(ui_surf, winner, client.my_team)

    # ── Vitals (HP / mana bars) ──────────────────────────────────────────────

    def _render_vitals(self, ui_surf, my_data, hud):
        hp      = my_data.get("hp", 0)
        max_hp  = max(1, my_data.get("max_hp", 1))
        mana    = my_data.get("mana", 0)
        max_mana = max(1, my_data.get("max_mana", 1))

        pygame.draw.rect(ui_surf, (10, 11, 20), hud["bars_bg"])

        hp_r     = hud["hp_bar"]
        hp_fill  = int(hp_r.w * hp / max_hp)
        pygame.draw.rect(ui_surf, (40, 14, 14), hp_r)
        if hp_fill > 0:
            pygame.draw.rect(ui_surf, (38, 168, 58), (hp_r.x, hp_r.y, hp_fill, hp_r.h))
        hp_txt = self._font_bar_txt.render(f"{hp} / {max_hp}", True, (200, 235, 200))
        ui_surf.blit(hp_txt, hp_txt.get_rect(centerx=hp_r.centerx, centery=hp_r.centery))

        mp_r    = hud["mp_bar"]
        mp_fill = int(mp_r.w * mana / max_mana)
        pygame.draw.rect(ui_surf, (10, 18, 55), mp_r)
        if mp_fill > 0:
            pygame.draw.rect(ui_surf, (32, 98, 215), (mp_r.x, mp_r.y, mp_fill, mp_r.h))

    def _render_channel_bar(self, ui_surf, my_data, hud):
        for ab in my_data.get("abilities", []):
            if not (ab and ab.get("is_channeling")):
                continue
            ct  = ab.get("channel_timer", 0)
            cm  = max(0.001, ab.get("channel_time", 1.5))
            bw  = 200
            bh  = 10
            bx  = self._sw // 2 - bw // 2
            by  = hud["bars_bg"].top - 26
            is_recall  = ab.get("is_recall", False)
            if is_recall:
                bg_col   = (10, 30, 50)
                bar_bg   = (8, 20, 35)
                bar_fill = (40, 160, 255)
                bar_rim  = (20, 90, 180)
                lbl_txt  = "RECALLING..."
                lbl_col  = (120, 200, 255)
            else:
                bg_col   = (18, 18, 28)
                bar_bg   = (35, 28, 10)
                bar_fill = (210, 150, 30)
                bar_rim  = (130, 100, 20)
                lbl_txt  = "CHARGING"
                lbl_col  = (200, 160, 40)
            pygame.draw.rect(ui_surf, bg_col, (bx - 2, by - 14, bw + 4, bh + 16))
            lbl = self._font_bar_txt.render(lbl_txt, True, lbl_col)
            ui_surf.blit(lbl, lbl.get_rect(centerx=self._sw // 2, bottom=by - 1))
            pygame.draw.rect(ui_surf, bar_bg, (bx, by, bw, bh))
            fill = int(bw * ct / cm)
            if fill > 0:
                pygame.draw.rect(ui_surf, bar_fill, (bx, by, fill, bh))
            pygame.draw.rect(ui_surf, bar_rim, (bx, by, bw, bh), 1)
            break

    # ── Panel background ─────────────────────────────────────────────────────

    def _render_panel(self, ui_surf, hud):
        px, py = hud["panel_x"], hud["panel_y"]
        pw, ph = hud["panel_w"], hud["panel_h"]
        pygame.draw.rect(ui_surf, (10, 11, 20), (px, py, pw, ph))
        pygame.draw.line(ui_surf, (55, 65, 98), (px, py), (px + pw - 1, py), 1)
        pygame.draw.rect(ui_surf, (24, 26, 42), (px, py, pw, ph), 1)

    # ── Gold section ─────────────────────────────────────────────────────────

    def _render_gold(self, ui_surf, my_data, hud):
        gold   = my_data.get("gold", 0)
        gx     = hud["gold_x"]
        slot_y = hud["slot_y"]
        if self._icon_gold:
            ui_surf.blit(self._icon_gold, (gx, slot_y + 16))
        else:
            gl_s = self._font_gold_lbl.render("GOLD", True, (72, 62, 30))
            ui_surf.blit(gl_s, (gx, slot_y + 18))
        gv_s = self._font_gold_val.render(str(gold), True, (188, 158, 48))
        ui_surf.blit(gv_s, (gx, slot_y + 32))
        pygame.draw.line(ui_surf, (30, 33, 52),
                         (hud["div_gold"], slot_y + 6),
                         (hud["div_gold"], slot_y + 58), 1)

    # ── Ability slots ────────────────────────────────────────────────────────

    def _render_ability_slots(self, ui_surf, abilities, hud, placement_mode, mx_ui, my_ui):
        slot_y = hud["slot_y"]
        key_y  = hud["key_y"]
        for i, rect in enumerate(hud["ability_rects"]):
            ability     = abilities[i] if i < len(abilities) else None
            on_cd       = bool(ability and ability.get("is_on_cooldown"))
            in_place    = placement_mode == i
            ab_active   = bool(ability and ability.get("is_active"))
            ab_spinning = bool(ability and ability.get("is_spinning"))
            ab_passive  = bool(ability and ability.get("is_passive"))

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

            elif ab_active:
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
                pygame.draw.rect(ui_surf, (55, 160, 70), rect, 2)
                ns = self._font_slot_sm.render("PLACE", True, (80, 200, 100))
                ui_surf.blit(ns, ns.get_rect(centerx=rect.centerx, centery=rect.centery))

            elif on_cd:
                icon = self._ability_icons.get(ability.get("name", ""))
                if icon:
                    iw, ih = icon.get_size()
                    ui_surf.blit(icon, (rect.x + (rect.w - iw) // 2, rect.y + (rect.h - ih) // 2))
                cd_t      = ability.get("cooldown_timer", 0)
                cd_max    = max(0.001, ability.get("cooldown", 1))
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

        pygame.draw.line(ui_surf, (30, 33, 52),
                         (hud["div_inv"], hud["slot_y"] + 6),
                         (hud["div_inv"], hud["slot_y"] + 58), 1)

    # ── Recall mini-slot ─────────────────────────────────────────────────────

    def _render_recall_slot(self, ui_surf, abilities, hud):
        rect      = hud["recall_rect"]
        ability   = abilities[3] if len(abilities) > 3 else None
        if not ability:
            return
        on_cd       = ability.get("is_on_cooldown", False)
        channeling  = ability.get("is_channeling", False)

        pygame.draw.rect(ui_surf, (14, 22, 38), rect)

        if channeling:
            ct       = ability.get("channel_timer", 0)
            cm       = max(0.001, ability.get("channel_time", 4.0))
            elapsed  = (cm - ct) / cm
            fill_h   = int(rect.h * elapsed)
            if fill_h > 0:
                pygame.draw.rect(ui_surf, (30, 100, 200),
                                 (rect.x, rect.bottom - fill_h, rect.w, fill_h))
            pygame.draw.rect(ui_surf, (80, 180, 255), rect, 1)
        elif on_cd:
            cd_t   = ability.get("cooldown_timer", 0)
            cd_max = max(0.001, ability.get("cooldown", 8.0))
            ov_h   = int(rect.h * cd_t / cd_max)
            if ov_h > 0:
                cd_s = pygame.Surface((rect.w, ov_h), pygame.SRCALPHA)
                cd_s.fill((0, 0, 0, 178))
                ui_surf.blit(cd_s, (rect.x, rect.y))
            pygame.draw.rect(ui_surf, (30, 32, 50), rect, 1)
        else:
            pygame.draw.rect(ui_surf, (40, 80, 140), rect, 1)

        ks = self._font_key_lbl.render("B", True, (80, 150, 255))
        ui_surf.blit(ks, ks.get_rect(centerx=rect.centerx, bottom=rect.top - 2))

    # ── Inventory ────────────────────────────────────────────────────────────

    def _render_inventory(self, ui_surf, my_data, hud, mx_ui, my_ui):
        inventory = my_data.get("inventory", [])[:3]
        for i, rect in enumerate(hud["inventory_rects"]):
            pygame.draw.rect(ui_surf, (12, 13, 22), rect)
            item = inventory[i] if i < len(inventory) else None
            if item:
                pygame.draw.rect(ui_surf, (98, 78, 30), rect.inflate(-6, -6))
                if rect.collidepoint(mx_ui, my_ui):
                    hover_ov = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                    hover_ov.fill((0, 0, 0, 110))
                    ui_surf.blit(hover_ov, rect.topleft)
                    refund = ITEMS.get(item, {}).get("cost", 0) // 2
                    sell_s = self._font_slot_sm.render(f"SELL {refund}g", True, (210, 130, 50))
                    ui_surf.blit(sell_s, sell_s.get_rect(center=rect.center))
                else:
                    lbl   = ITEMS.get(item, {}).get("label", item[:3])
                    lbl_s = self._font_slot_sm.render(lbl, True, (230, 205, 120))
                    ui_surf.blit(lbl_s, lbl_s.get_rect(center=rect.center))
            pygame.draw.rect(ui_surf, (22, 24, 40), rect, 1)

    # ── Shop button ──────────────────────────────────────────────────────────

    def _render_shop_button(self, ui_surf, hud, shop_open, mx_ui, my_ui):
        sr         = hud["shop_rect"]
        shop_hover = sr.collidepoint(mx_ui, my_ui)
        if shop_open:
            bg, brd, tc = (28, 36, 55), (55, 75, 120), (130, 165, 215)
        elif shop_hover:
            bg, brd, tc = (18, 20, 34), (40, 46, 70), (100, 110, 150)
        else:
            bg, brd, tc = (12, 13, 24), (28, 32, 50), (65, 72, 100)
        pygame.draw.rect(ui_surf, bg,  sr)
        pygame.draw.rect(ui_surf, brd, sr, 1)
        st = self._font_shop.render("SHOP", True, tc)
        ui_surf.blit(st, st.get_rect(center=sr.center))

    # ── Shop panel ───────────────────────────────────────────────────────────

    def _render_shop_panel(self, ui_surf, snap, my_data, hud, my_pos):
        ITEM_ROW_H = 46
        HEADER_H   = 28
        PANEL_W    = 560
        PANEL_H    = HEADER_H + len(ITEM_KEYS) * ITEM_ROW_H + 10
        panel_x    = self._sw // 2 - PANEL_W // 2
        panel_y    = hud["bars_bg"].top - PANEL_H - 6

        pygame.draw.rect(ui_surf, (10, 11, 20), (panel_x, panel_y, PANEL_W, PANEL_H))
        pygame.draw.rect(ui_surf, (50, 60, 90), (panel_x, panel_y, PANEL_W, PANEL_H), 1)
        title = self._font_slot_sm.render("SHOP", True, (180, 160, 60))
        ui_surf.blit(title, title.get_rect(centerx=panel_x + PANEL_W // 2, top=panel_y + 6))

        if not _check_near_shop(snap, my_pos):
            msg = self._font_slot_sm.render("Move closer to a shop ($) to buy", True, (160, 120, 60))
            ui_surf.blit(msg, msg.get_rect(centerx=panel_x + PANEL_W // 2,
                                           centery=panel_y + HEADER_H + PANEL_H // 2))
            return

        gold      = my_data.get("gold", 0)
        inventory = my_data.get("inventory", [None] * 3)
        inv_full  = all(s is not None for s in inventory[:3])
        mx_ui, my_ui = pygame.mouse.get_pos()

        for idx, key in enumerate(ITEM_KEYS):
            item    = ITEMS[key]
            row_y   = panel_y + HEADER_H + idx * ITEM_ROW_H
            can_buy = gold >= item["cost"] and not inv_full

            row_col = (16, 17, 28) if idx % 2 == 0 else (13, 14, 24)
            pygame.draw.rect(ui_surf, row_col, (panel_x, row_y, PANEL_W, ITEM_ROW_H))

            name_col = (215, 195, 120) if can_buy else (100, 90, 60)
            name_s   = self._font_slot_sm.render(key, True, name_col)
            ui_surf.blit(name_s, (panel_x + 8, row_y + ITEM_ROW_H // 2 - name_s.get_height() // 2))

            desc_s = self._font_slot_sm.render(item["desc"], True, (120, 130, 150))
            ui_surf.blit(desc_s, (panel_x + 148, row_y + ITEM_ROW_H // 2 - desc_s.get_height() // 2))

            cost_col = (200, 170, 50) if gold >= item["cost"] else (120, 80, 40)
            cost_s   = self._font_slot_sm.render(f"{item['cost']}g", True, cost_col)
            ui_surf.blit(cost_s, (panel_x + PANEL_W - 86, row_y + ITEM_ROW_H // 2 - cost_s.get_height() // 2))

            btn_rect = pygame.Rect(panel_x + PANEL_W - 58, row_y + 8, 52, 30)
            self.shop_btn_rects.append(btn_rect)
            hovered  = btn_rect.collidepoint(mx_ui, my_ui)
            if can_buy:
                btn_bg, btn_brd, btn_tc = (40, 120, 50) if hovered else (25, 80, 35), (70, 180, 80), (220, 255, 220)
            else:
                btn_bg, btn_brd, btn_tc = (30, 30, 40), (45, 45, 60), (70, 70, 90)
            pygame.draw.rect(ui_surf, btn_bg,  btn_rect, border_radius=4)
            pygame.draw.rect(ui_surf, btn_brd, btn_rect, 1, border_radius=4)
            buy_s = self._font_slot_sm.render("BUY", True, btn_tc)
            ui_surf.blit(buy_s, buy_s.get_rect(center=btn_rect.center))

        if inv_full:
            msg = self._font_slot_sm.render("Inventory full", True, (180, 80, 60))
            ui_surf.blit(msg, msg.get_rect(right=panel_x + PANEL_W - 8, top=panel_y + 4))

    # ── Minimap ──────────────────────────────────────────────────────────────

    def _render_minimap(self, ui_surf, snap, client, cam_x, cam_y, cam_locked, is_visible_fn):
        from shared.constants import RUNE_X, RUNE_Y
        mini_x  = 8
        mini_y  = self._sh - MINI_H - 8
        my_team = client.my_team

        ui_surf.blit(self._mini_terrain, (mini_x, mini_y))
        ui_surf.blit(self._mini_fog_surf, (mini_x, mini_y))

        for b in snap.get("buildings", {}).values():
            if b.get("is_destroyed"):
                continue
            btype = b.get("type")
            col   = TEAM_COLOURS.get(b.get("team", 0), (110, 110, 110))
            bx    = mini_x + int(b["x"] * MINI_SX)
            by    = mini_y + int(b["y"] * MINI_SY)
            size  = 6 if btype == "BuildingHeadquarter" else 3
            pygame.draw.rect(ui_surf, col, (bx, by, size, size))

        for shop in snap.get("shops", {}).values():
            sx_m = mini_x + int(shop["x"] * MINI_SX)
            sy_m = mini_y + int(shop["y"] * MINI_SY)
            pygame.draw.rect(ui_surf, (200, 170, 40), (sx_m, sy_m, 4, 4))

        for t in snap.get("turrets", {}).values():
            if t.get("is_destroyed"):
                continue
            col  = TEAM_COLOURS.get(t.get("team", 0), (150, 150, 150))
            tx   = mini_x + int(t["x"] * MINI_SX)
            ty_m = mini_y + int(t["y"] * MINI_SY)
            pygame.draw.rect(ui_surf, col, (tx - 2, ty_m - 2, 4, 4))

        for bn in snap.get("banners", {}).values():
            if bn.get("is_destroyed"):
                continue
            if bn.get("team") != my_team and not is_visible_fn(bn["x"], bn["y"]):
                continue
            bx_m = mini_x + int(bn["x"] * MINI_SX)
            by_m = mini_y + int(bn["y"] * MINI_SY)
            pygame.draw.circle(ui_surf, (60, 220, 100), (bx_m, by_m), 3)

        rune_mini = snap.get("rune", {})
        if rune_mini.get("state") not in ("inactive", "cooldown"):
            rmx = mini_x + int(RUNE_X * MINI_SX)
            rmy = mini_y + int(RUNE_Y * MINI_SY)
            pygame.draw.circle(ui_surf, (180, 80, 240), (rmx, rmy), 4)

        for pid in client.get_entity_ids("players"):
            p_data = snap.get("players", {}).get(pid, {})
            if p_data.get("is_dead"):
                continue
            pos = client.get_interpolated_pos("players", pid)
            if not pos:
                continue
            team = p_data.get("team")
            if team != my_team and not is_visible_fn(pos[0], pos[1]):
                continue
            col = TEAM_COLOURS.get(team, (255, 255, 255))
            pygame.draw.circle(ui_surf, col,
                               (mini_x + int(pos[0] * MINI_SX), mini_y + int(pos[1] * MINI_SY)), 3)

        from shared.constants import MAP_W, MAP_H
        vx = mini_x + int(cam_x * MINI_SX)
        vy = mini_y + int(cam_y * MINI_SY)
        vw = max(1, int((MAP_W / (MAP_W / MINI_W)) * MINI_SX))
        vh = max(1, int((MAP_H / (MAP_H / MINI_H)) * MINI_SY))

        # Viewport rect: world-to-mini scale
        from shared.constants import MAP_W as _MW, MAP_H as _MH
        VIEWPORT_W = 640
        VIEWPORT_H = 400
        vw = max(1, int(VIEWPORT_W * MINI_SX))
        vh = max(1, int(VIEWPORT_H * MINI_SY))
        pygame.draw.rect(ui_surf, (200, 200, 200), (vx, vy, vw, vh), 1)
        pygame.draw.rect(ui_surf, (38, 44, 64), (mini_x, mini_y, MINI_W, MINI_H), 1)

        label     = "CAM" if cam_locked else "FREE"
        label_col = (80, 160, 80) if cam_locked else (160, 120, 50)
        lock_s    = self._font_mini_lbl.render(label, True, label_col)
        ui_surf.blit(lock_s, (mini_x + MINI_W - lock_s.get_width() - 4, mini_y - lock_s.get_height() - 3))

    # ── Lobby overlay ────────────────────────────────────────────────────────

    def _render_lobby_overlay(self, ui_surf, snap, game_phase, my_ready, mx_ui, my_ui):
        sw, sh  = self._sw, self._sh
        players = snap.get("players", {})

        self.ready_btn_rect   = None
        self.force_start_rect = None

        if game_phase == "countdown":
            cd = max(0, snap.get("countdown_timer", 3.0))
            ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 120))
            ui_surf.blit(ov, (0, 0))
            cd_s = self._font_lobby_cd.render(str(math.ceil(cd)), True, (255, 230, 80))
            ui_surf.blit(cd_s, cd_s.get_rect(centerx=sw // 2, centery=sh // 2 - 20))
            lbl = self._font_lobby_body.render("GET READY", True, (200, 200, 220))
            ui_surf.blit(lbl, lbl.get_rect(centerx=sw // 2, centery=sh // 2 + 60))
            return

        pw = int(sw * 0.30)
        ph = int(sh * 0.38)
        px = (sw - pw) // 2
        py = int(sh * 0.18)

        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((8, 10, 22, 220))
        ui_surf.blit(panel, (px, py))
        pygame.draw.rect(ui_surf, (50, 65, 110), (px, py, pw, ph), 2, border_radius=8)

        title = self._font_lobby_title.render("WAITING FOR PLAYERS", True, (200, 200, 230))
        ui_surf.blit(title, title.get_rect(centerx=px + pw // 2, top=py + 14))
        pygame.draw.line(ui_surf, (40, 50, 80), (px + 16, py + 52), (px + pw - 16, py + 52))

        col_w    = pw // 2
        row_h    = 26
        text_top = py + 62
        for team in (1, 2):
            cx     = px + (col_w * (team - 1)) + col_w // 2
            team_s = self._font_lobby_body.render(f"TEAM {team}", True, TEAM_COLOURS.get(team, (200, 200, 200)))
            ui_surf.blit(team_s, team_s.get_rect(centerx=cx, top=text_top))
            row = text_top + row_h
            for p in players.values():
                if p.get("team") != team:
                    continue
                hero  = p.get("hero", "?")[:3].upper()
                ready = p.get("is_ready", False)
                col   = (80, 210, 100) if ready else (160, 160, 180)
                line  = self._font_lobby_body.render(f"{'✓' if ready else '·'} {hero}", True, col)
                ui_surf.blit(line, line.get_rect(centerx=cx, top=row))
                row += row_h

        btn_y = py + ph - int(ph * 0.28)
        if not my_ready:
            btn_w = int(pw * 0.42)
            btn_h = int(sh * 0.046)
            btn_r = pygame.Rect(px + (pw - btn_w) // 2, btn_y, btn_w, btn_h)
            hov   = btn_r.collidepoint(mx_ui, my_ui)
            pygame.draw.rect(ui_surf, (30, 140, 60) if hov else (20, 105, 45), btn_r, border_radius=8)
            pygame.draw.rect(ui_surf, (60, 220, 100), btn_r, 2, border_radius=8)
            lbl = self._font_lobby_title.render("READY", True, (255, 255, 255))
            ui_surf.blit(lbl, lbl.get_rect(center=btn_r.center))
            self.ready_btn_rect = btn_r
        else:
            wait_s = self._font_lobby_body.render("Waiting for others...", True, (100, 200, 120))
            ui_surf.blit(wait_s, wait_s.get_rect(centerx=px + pw // 2, top=btn_y + 6))

        wait_elapsed = snap.get("wait_elapsed", 0)
        if wait_elapsed >= 90:
            fs_w = int(pw * 0.52)
            fs_h = int(sh * 0.036)
            fs_r = pygame.Rect(px + (pw - fs_w) // 2, py + ph - int(sh * 0.038), fs_w, fs_h)
            hov  = fs_r.collidepoint(mx_ui, my_ui)
            pygame.draw.rect(ui_surf, (120, 60, 20) if hov else (90, 40, 10), fs_r, border_radius=6)
            pygame.draw.rect(ui_surf, (200, 120, 40), fs_r, 1, border_radius=6)
            lbl = self._font_lobby_body.render("FORCE START", True, (230, 160, 60))
            ui_surf.blit(lbl, lbl.get_rect(center=fs_r.center))
            self.force_start_rect = fs_r

    # ── Death / respawn overlay ──────────────────────────────────────────────

    def _render_dead_overlay(self, ui_surf, my_data, snap):
        sw, sh    = self._sw, self._sh
        exhausted = snap.get("minerals_exhausted", False)
        ov        = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 80))
        ui_surf.blit(ov, (0, 0))
        if exhausted:
            msg = self._font_dead_big.render("ELIMINATED", True, (200, 60, 60))
            sub = self._font_dead_sub.render("No respawns — minerals exhausted", True, (180, 120, 120))
        else:
            timer = max(0, my_data.get("respawn_timer", 0))
            msg   = self._font_dead_big.render("YOU DIED", True, (200, 60, 60))
            sub   = self._font_dead_sub.render(f"Respawning in {timer:.1f}s", True, (180, 160, 160))
        ui_surf.blit(msg, msg.get_rect(centerx=sw // 2, centery=sh // 2 - 30))
        ui_surf.blit(sub, sub.get_rect(centerx=sw // 2, centery=sh // 2 + 26))

    # ── Victory / defeat overlay ─────────────────────────────────────────────

    def _render_victory_overlay(self, ui_surf, winner, my_team):
        sw, sh = self._sw, self._sh
        ov     = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        ui_surf.blit(ov, (0, 0))
        big_font = pygame.font.SysFont("arial", 80, bold=True)
        sub_font = pygame.font.SysFont("arial", 24)
        my_win   = winner == my_team
        main_s   = big_font.render("VICTORY" if my_win else "DEFEAT",
                                   True, (230, 195, 50) if my_win else (170, 50, 50))
        ui_surf.blit(main_s, main_s.get_rect(centerx=sw // 2, centery=sh // 2 - 50))
        hint_s = sub_font.render("Press ESC to exit", True, (160, 160, 180))
        ui_surf.blit(hint_s, hint_s.get_rect(centerx=sw // 2, centery=sh // 2 + 40))

    # ── Static helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_mini_terrain(obstacles):
        surf = pygame.Surface((MINI_W, MINI_H))
        surf.fill((30, 35, 40))
        for obs in obstacles:
            ox = int(obs.x      * MINI_SX)
            oy = int(obs.y      * MINI_SY)
            ow = max(1, int(obs.width  * MINI_SX))
            oh = max(1, int(obs.height * MINI_SY))
            pygame.draw.rect(surf, (12, 14, 18), (ox, oy, ow, oh))
        return surf


# ── Module-level helpers ─────────────────────────────────────────────────────

def _check_near_shop(snap, my_pos):
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
