"""
GloryDay Map Editor v2
======================
8-layer visual editor. Press S to save all data to shared/map_data.py
AND regenerate asset/map.png from tile images.

Layers
------
1  OBSTACLES      (red)    drag rect  → wall.png tiles in map.png
2  BUSHES         (green)  drag rect  → bush.png tiles in map.png
3  WATER_ZONES    (blue)   drag rect  → water.png tiles in map.png
4  CAPTURE_ZONES  (yellow) click 32px
5  HQ_POSITIONS   (purple) click 48px  T = toggle team
6  TOWER_POSITIONS(orange) click 32px  T = toggle team
7  SPAWN_ZONES    (cyan)   drag rect  (no tile baked into map.png)
8  SHOP_POSITIONS (brown)  click 32px  T = toggle team

Controls
--------
1-8      Switch active layer
T        Toggle team 1/2 (layers 5, 6, 8)
LDrag    Draw rect  (rect layers)
LClick   Place cell (cell layers)
RClick   Delete item under cursor
Z        Undo last add
G        Toggle grid
S        Save to shared/map_data.py + regenerate asset/map.png
ESC      Quit
"""

import sys, os, re, importlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["SDL_VIDEODRIVER"] = "windib"

import pygame

GRID  = 32
MAP_W = 1280
MAP_H = 800
BAR_H = 52

ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "asset")
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "map_data.py")
MAP_PNG   = os.path.join(ASSET_DIR, "map.png")

GROUND_COLOR = (182, 149, 72)

# Layer IDs
L_OBS   = 0
L_BUSH  = 1
L_WATER = 2
L_CAP   = 3
L_HQ    = 4
L_TOW   = 5
L_SPAWN = 6
L_SHOP  = 7

LAYERS = {
    L_OBS:   dict(name="OBSTACLES",       col=(255,  60,  60), mode="rect", cell=32,  tile="wall.png"),
    L_BUSH:  dict(name="BUSHES",          col=( 30, 200,  30), mode="rect", cell=32,  tile="bush.png"),
    L_WATER: dict(name="WATER_ZONES",     col=( 30, 120, 255), mode="rect", cell=32,  tile="water.png"),
    L_CAP:   dict(name="CAPTURE_ZONES",   col=(255, 220,   0), mode="cell", cell=32,  tile=None),
    L_HQ:    dict(name="HQ_POSITIONS",    col=(180,   0, 255), mode="cell", cell=48,  tile=None),
    L_TOW:   dict(name="TOWER_POSITIONS", col=(255, 140,   0), mode="cell", cell=32,  tile=None),
    L_SPAWN: dict(name="SPAWN_POSITIONS",  col=(  0, 220, 220), mode="cell", cell=32,  tile=None),
    L_SHOP:  dict(name="SHOP_POSITIONS",  col=(180, 130,  30), mode="cell", cell=32,  tile=None),
}

TEAM_LAYERS = {L_HQ, L_TOW, L_SPAWN, L_SHOP}


# ── helpers ───────────────────────────────────────────────────────────────────

def snap(v):
    return (v // GRID) * GRID

def make_rect(ax, ay, bx, by):
    x = snap(min(ax, bx))
    y = snap(min(ay, by))
    r = (max(ax, bx) // GRID + 1) * GRID
    b = (max(ay, by) // GRID + 1) * GRID
    return pygame.Rect(x, y, r - x, b - y)


# ── data loading ──────────────────────────────────────────────────────────────

def load_all():
    import shared.map_data as md
    importlib.reload(md)
    obs   = list(md.OBSTACLES)
    bush  = list(md.BUSHES)
    water = list(md.WATER_ZONES) if hasattr(md, "WATER_ZONES") else []
    caps  = list(md.CAPTURE_ZONES)
    hqs   = list(md.HQ_POSITIONS)  if hasattr(md, "HQ_POSITIONS")  else [(1, 32, 32), (2, 1200, 720)]
    tows  = list(md.TOWER_POSITIONS)
    spawn = list(md.SPAWN_POSITIONS) if hasattr(md, "SPAWN_POSITIONS") else [(1, 60, 100), (2, 1220, 700)]
    shops = list(md.SHOP_POSITIONS) if hasattr(md, "SHOP_POSITIONS") else []
    return {
        L_OBS: obs, L_BUSH: bush, L_WATER: water,
        L_CAP: caps, L_HQ: hqs, L_TOW: tows,
        L_SPAWN: spawn, L_SHOP: shops,
    }


# ── save ──────────────────────────────────────────────────────────────────────

def _fmt_rect_list(name, rects):
    lines = [f"{name} = ["]
    for r in rects:
        lines.append(f"    pygame.Rect({r.x}, {r.y}, {r.w}, {r.h}),")
    lines.append("]")
    return "\n".join(lines)

def _fmt_tuple_list(name, items):
    lines = [f"{name} = ["]
    for t in items:
        lines.append(f"    {t},")
    lines.append("]")
    return "\n".join(lines)

def _replace_block(src, name, new_block):
    """Replace NAME = [...] using bracket counting so comments with [ ] don't confuse it."""
    m = re.search(rf"{name}\s*=\s*\[", src)
    if not m:
        return src + f"\n{new_block}\n"
    start = m.start()
    bracket_pos = m.end() - 1   # index of the opening [
    depth = 0
    end = bracket_pos
    for i in range(bracket_pos, len(src)):
        if src[i] == "[":
            depth += 1
        elif src[i] == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    return src[:start] + new_block + src[end + 1:]

def save_data(data):
    with open(DATA_PATH) as f:
        src = f.read()
    src = _replace_block(src, "OBSTACLES",      _fmt_rect_list ("OBSTACLES",      data[L_OBS]))
    src = _replace_block(src, "BUSHES",         _fmt_rect_list ("BUSHES",         data[L_BUSH]))
    src = _replace_block(src, "WATER_ZONES",    _fmt_rect_list ("WATER_ZONES",    data[L_WATER]))
    src = _replace_block(src, "SPAWN_POSITIONS", _fmt_tuple_list("SPAWN_POSITIONS", data[L_SPAWN]))
    src = _replace_block(src, "CAPTURE_ZONES",  _fmt_tuple_list("CAPTURE_ZONES",  data[L_CAP]))
    src = _replace_block(src, "HQ_POSITIONS",   _fmt_tuple_list("HQ_POSITIONS",   data[L_HQ]))
    src = _replace_block(src, "TOWER_POSITIONS",_fmt_tuple_list("TOWER_POSITIONS",data[L_TOW]))
    src = _replace_block(src, "SHOP_POSITIONS", _fmt_tuple_list("SHOP_POSITIONS", data[L_SHOP]))
    with open(DATA_PATH, "w") as f:
        f.write(src)


def _tile_image(surf, tile_img, rect):
    for ty in range(rect.y, rect.y + rect.h, GRID):
        for tx in range(rect.x, rect.x + rect.w, GRID):
            surf.blit(tile_img, (tx, ty))


def save_map_png(data):
    """Regenerate asset/map.png from tile images + ground color."""
    surf = pygame.Surface((MAP_W, MAP_H))
    surf.fill(GROUND_COLOR)

    # Rect layers — tiled across every zone rect
    for lid, fname in [(L_OBS, "wall.png"), (L_WATER, "water.png"), (L_BUSH, "bush.png")]:
        tile_path = os.path.join(ASSET_DIR, fname)
        if not os.path.exists(tile_path):
            print(f"[map_editor] WARNING: {fname} not found — skipping {LAYERS[lid]['name']} tiles")
            continue
        try:
            tile_img = pygame.image.load(tile_path).convert_alpha()
        except Exception as e:
            print(f"[map_editor] WARNING: could not load {fname}: {e}")
            continue
        for rect in data[lid]:
            _tile_image(surf, tile_img, rect)

    # Towers — team-specific images (tower1.png / tower2.png)
    tower_imgs = {}
    for team, x, y in data[L_TOW]:
        if team not in tower_imgs:
            fname = f"tower{team}.png"
            tile_path = os.path.join(ASSET_DIR, fname)
            if not os.path.exists(tile_path):
                print(f"[map_editor] WARNING: {fname} not found — skipping")
                tower_imgs[team] = None
            else:
                try:
                    tower_imgs[team] = pygame.image.load(tile_path).convert_alpha()
                except Exception as e:
                    print(f"[map_editor] WARNING: could not load {fname}: {e}")
                    tower_imgs[team] = None
        img = tower_imgs.get(team)
        if img:
            surf.blit(img, (x, y))

    # Shops — shared image
    shop_path = os.path.join(ASSET_DIR, "shop.png")
    if os.path.exists(shop_path):
        try:
            shop_img = pygame.image.load(shop_path).convert_alpha()
            for _, x, y in data[L_SHOP]:
                surf.blit(shop_img, (x, y))
        except Exception as e:
            print(f"[map_editor] WARNING: could not load shop.png: {e}")

    pygame.image.save(surf, MAP_PNG)
    print(f"[map_editor] Saved {MAP_PNG}")


# ── alpha rect draw ───────────────────────────────────────────────────────────

def draw_alpha_rect(screen, col, rect, alpha_fill=60):
    w = max(1, rect.w - 1)
    h = max(1, rect.h - 1)
    if w <= 0 or h <= 0:
        return
    tmp = pygame.Surface((w, h), pygame.SRCALPHA)
    tmp.fill((*col, alpha_fill))
    screen.blit(tmp, rect.topleft)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((MAP_W, MAP_H + BAR_H))
    pygame.display.set_caption("GloryDay Map Editor v2")
    clock     = pygame.time.Clock()
    font      = pygame.font.SysFont("consolas", 12)
    font_bold = pygame.font.SysFont("consolas", 12, bold=True)

    map_img = pygame.image.load(MAP_PNG).convert()

    data       = load_all()
    active     = L_OBS
    team       = 1
    show_grid  = True
    drawing    = False
    drag_a     = (0, 0)
    drag_b     = (0, 0)
    status     = "Loaded.  Keys 1-8=layer  T=team  S=save  Z=undo  G=grid  ESC=quit"
    undo_stack = []  # list of (layer_id, item)

    while True:
        mx, my = pygame.mouse.get_pos()
        in_map = 0 <= mx < MAP_W and 0 <= my < MAP_H
        linfo  = LAYERS[active]
        col    = linfo["col"]
        mode   = linfo["mode"]
        cell   = linfo["cell"]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); return
                elif pygame.K_1 <= event.key <= pygame.K_8:
                    active = event.key - pygame.K_1
                    status = f"Layer: {LAYERS[active]['name']}"
                elif event.key == pygame.K_t and active in TEAM_LAYERS:
                    team = 2 if team == 1 else 1
                    status = f"Team → {team}"
                elif event.key == pygame.K_g:
                    show_grid = not show_grid
                elif event.key == pygame.K_z and undo_stack:
                    lid, item = undo_stack.pop()
                    if item in data[lid]:
                        data[lid].remove(item)
                    status = f"Undo — removed from {LAYERS[lid]['name']}"
                elif event.key == pygame.K_s:
                    save_data(data)
                    save_map_png(data)
                    map_img = pygame.image.load(MAP_PNG).convert()
                    status = "Saved all layers + regenerated map.png"

            elif event.type == pygame.MOUSEBUTTONDOWN and in_map:
                if event.button == 1:
                    if mode == "rect":
                        drawing = True
                        drag_a = drag_b = (mx, my)
                    else:
                        sx, sy = snap(mx), snap(my)
                        if cell == 48:
                            sx = max(0, min(sx - 8, MAP_W - cell))
                            sy = max(0, min(sy - 8, MAP_H - cell))
                        if active == L_CAP:
                            item = (sx, sy)
                        else:
                            item = (team, sx, sy)
                        data[active].append(item)
                        undo_stack.append((active, item))
                        status = f"Placed {item} in {linfo['name']}"

                elif event.button == 3:
                    for item in list(data[active]):
                        if mode == "rect":
                            hit = item.collidepoint(mx, my)
                        else:
                            ix = item[0] if active == L_CAP else item[1]
                            iy = item[1] if active == L_CAP else item[2]
                            hit = ix <= mx < ix + cell and iy <= my < iy + cell
                        if hit:
                            data[active].remove(item)
                            status = f"Deleted from {linfo['name']}"
                            break

            elif event.type == pygame.MOUSEMOTION and drawing:
                drag_b = (min(mx, MAP_W - 1), min(my, MAP_H - 1))

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and drawing:
                    drawing = False
                    nr = make_rect(*drag_a, *drag_b)
                    if nr.w >= GRID and nr.h >= GRID:
                        data[active].append(nr)
                        undo_stack.append((active, nr))
                        status = f"Added rect({nr.x},{nr.y},{nr.w},{nr.h}) to {linfo['name']}"

        # ── RENDER ──────────────────────────────────────────────────────────────
        screen.blit(map_img, (0, 0))

        if show_grid:
            for gx in range(0, MAP_W, GRID):
                pygame.draw.line(screen, (255, 255, 255), (gx, 0), (gx, MAP_H), 1)
            for gy in range(0, MAP_H, GRID):
                pygame.draw.line(screen, (255, 255, 255), (0, gy), (MAP_W, gy), 1)

        # Draw all layers
        for lid, li in LAYERS.items():
            is_active = (lid == active)
            a_fill    = 70  if is_active else 25
            a_border  = 230 if is_active else 80
            bw        = 2   if is_active else 1
            lcol      = li["col"]
            lmode     = li["mode"]
            lcell     = li["cell"]

            for item in data[lid]:
                if lmode == "rect":
                    draw_alpha_rect(screen, lcol, item, a_fill)
                else:
                    ix = item[0] if lid == L_CAP else item[1]
                    iy = item[1] if lid == L_CAP else item[2]
                    r  = pygame.Rect(ix, iy, lcell, lcell)
                    draw_alpha_rect(screen, lcol, r, a_fill)
                    if lid != L_CAP:
                        lbl = font.render(str(item[0]), True, (255, 255, 255))
                        screen.blit(lbl, (ix + 2, iy + 2))

        # Drag preview
        if drawing:
            pr = make_rect(*drag_a, *drag_b)
            draw_alpha_rect(screen, col, pr, 80)
            dim = font.render(f"{pr.w}×{pr.h}", True, (255, 255, 255))
            screen.blit(dim, (pr.x + 2, pr.y + 2))

        # Cursor snap
        if in_map:
            pygame.draw.rect(screen, (255, 230, 0), (snap(mx), snap(my), GRID, GRID), 1)

        # ── STATUS BAR ──────────────────────────────────────────────────────────
        pygame.draw.rect(screen, (12, 12, 12), (0, MAP_H, MAP_W, BAR_H))
        pygame.draw.line(screen, (50, 50, 50), (0, MAP_H), (MAP_W, MAP_H))

        # Layer tabs
        tx = 4
        for lid, li in LAYERS.items():
            label = f" {lid+1}:{li['name']} "
            is_a  = (lid == active)
            bg    = li["col"] if is_a else (45, 45, 45)
            fg    = (255, 255, 255) if is_a else (150, 150, 150)
            surf  = (font_bold if is_a else font).render(label, True, fg)
            w     = surf.get_width() + 2
            pygame.draw.rect(screen, bg, (tx, MAP_H + 2, w, 16))
            screen.blit(surf, (tx + 1, MAP_H + 2))
            tx += w + 4

        team_str = f"  Team:{team}" if active in TEAM_LAYERS else ""
        info = font.render(
            f"  ({snap(mx)},{snap(my)}){team_str}  |  {status}",
            True, (190, 190, 190),
        )
        screen.blit(info, (4, MAP_H + 24))

        # Count info for active layer
        cnt = font.render(f"[{len(data[active])} items]", True, LAYERS[active]["col"])
        screen.blit(cnt, (MAP_W - cnt.get_width() - 6, MAP_H + 24))

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
