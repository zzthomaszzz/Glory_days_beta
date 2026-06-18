# GloryDay — Technical Design Document

## Architecture Overview

```
shared/            ← imported by both server and client
  constants.py     ← all game tunables in one place
  map_data.py      ← obstacle rects, spawn zones, base positions
  protocol.py      ← snapshot/input message format

server/
  main.py          ← asyncio entry point
  net.py           ← GameServer: broadcast_loop + handle_client
  game_state.py    ← authoritative game state, update(dt) called each tick
  entities.py      ← Player, Building, Base classes

client/
  main.py          ← pygame init, game loop, asyncio bridge
  net.py           ← NetworkClient: connects, recv loop, interpolation
  scene.py         ← SceneBase + SceneTest (renders the game world)
  node.py          ← single node in the map grid
  map_system.py    ← builds node grid, runs BFS fog of war
```

**Key rule:** the map node grid lives on the **client only** (rendering concern). The server only needs obstacle rects for collision. Both load those rects from `shared/map_data.py`.

---

## Current File Status

| File | Status | What's missing |
|------|--------|----------------|
| `shared/constants.py` | ✅ Done | — |
| `shared/map_data.py` | ✅ Done | — |
| `shared/protocol.py` | ⚠️ Update | Add `buildings` + `winner` to snapshot |
| `server/main.py` | ✅ Done | — |
| `server/net.py` | ⚠️ Update | Pass `buildings` + `winner` to `make_snapshot` |
| `server/game_state.py` | ⚠️ Update | Add buildings dict, real `update(dt)`, `_check_win` |
| `server/entities.py` | ❌ Create | `Player`, `Building`, `Base` classes |
| `client/main.py` | ⚠️ Update | Screen size 1280×720 → 1280×800 |
| `client/net.py` | ✅ Done | — |
| `client/scene.py` | ⚠️ Update | Replace circle fog with `MapSystem` |
| `client/node.py` | ⚠️ Update | Add `cx`, `cy` cached centres |
| `client/map_system.py` | ❌ Create | Full fog-of-war system |

---

## Step-by-Step Implementation Guide

Do these in order. Each step has a small test you can run to confirm it works before moving on.

---

### STEP 1 — Fix `client/node.py` (add cached centres)

**File:** `client/node.py`

Add `cx` and `cy` right after `self.rect`:

```python
self.rect = pygame.Rect(x, y, size, size)
self.cx = x + size // 2    # add this
self.cy = y + size // 2    # add this
```

**Why:** The BFS inner loop calls centre coordinates thousands of times per frame. Storing them as plain Python floats at construction time is faster than reading `rect.centerx` (a C property) on every iteration.

**Test:** `python -c "from client.node import Node; n = Node(64, 96, 32); print(n.cx, n.cy)"` → should print `80 112`.

---

### STEP 2 — Create `client/map_system.py`

**File:** `client/map_system.py` (new file)

```python
import pygame
import math
from collections import deque
from client.node import Node
from shared.constants import NODE_SIZE


class MapSystem:
    def __init__(self, size_x, size_y, obstacles, spawns):
        self.size_x = size_x
        self.size_y = size_y
        self.size = NODE_SIZE   # change NODE_SIZE in constants.py to resize the whole grid
        self.node_x = size_x // self.size
        self.node_y = size_y // self.size
        self.obstacles = obstacles
        self.spawns = spawns

        self.nodes = []
        self.discovered_nodes = []       # lit by players this frame
        self.building_vision_nodes = []  # lit by buildings (rebuilt on events)
        self._fog_surface = pygame.Surface((size_x, size_y), pygame.SRCALPHA)

        self._init_nodes()
        self._set_obstacles()
        self._set_spawns()

    def _init_nodes(self):
        for y in range(self.node_y):
            self.nodes.append([])
            for x in range(self.node_x):
                self.nodes[y].append(Node(x * self.size, y * self.size))

    def _set_obstacles(self):
        for row in self.nodes:
            for node in row:
                if node.rect.collidelist(self.obstacles) >= 0:
                    node.traversable = 0

    def _set_spawns(self):
        for row in self.nodes:
            for node in row:
                if node.rect.collidelist(self.spawns) >= 0:
                    node.isSpawn = 1

    def get_adjacent(self, node):
        adj = []
        x = round(node.grid_id[0])
        y = round(node.grid_id[1])
        if x > 0:               adj.append(self.nodes[y][x - 1])
        if x < self.node_x - 1: adj.append(self.nodes[y][x + 1])
        if y > 0:               adj.append(self.nodes[y - 1][x])
        if y < self.node_y - 1: adj.append(self.nodes[y + 1][x])
        return adj

    def get_node_from_pos(self, pos_x, pos_y):
        x = max(0, min(int(pos_x // self.size), self.node_x - 1))
        y = max(0, min(int(pos_y // self.size), self.node_y - 1))
        return self.nodes[y][x]

    def _run_bfs(self, origin, vision, write_building=False):
        queue = deque([origin])
        visited = {id(origin)}

        while queue:
            node = queue.popleft()

            dist = math.hypot(node.cx - origin.cx, node.cy - origin.cy)
            if dist > vision:
                continue

            visible = True
            for obstacle in self.obstacles:
                if obstacle.clipline(node.cx, node.cy, origin.cx, origin.cy):
                    if node.traversable:
                        visible = False
                        break

            if visible:
                if write_building:
                    if not node.building_vision:
                        node.building_vision = True
                        self.building_vision_nodes.append(node)
                else:
                    if not node.discovered:
                        node.discovered = 1
                        self.discovered_nodes.append(node)

                for adj in self.get_adjacent(node):
                    if id(adj) not in visited:
                        visited.add(id(adj))
                        queue.append(adj)

    def handle_fog(self, origin_nodes, vision):
        for node in self.discovered_nodes:
            node.discovered = 0
        self.discovered_nodes.clear()
        for origin in origin_nodes:
            self._run_bfs(origin, vision, write_building=False)

    def compute_building_vision(self, building_sources):
        # building_sources: list of (origin_node, vision_radius)
        for node in self.building_vision_nodes:
            node.building_vision = False
        self.building_vision_nodes.clear()
        for origin, vision in building_sources:
            self._run_bfs(origin, vision, write_building=True)

    def draw(self, surface):
        self._fog_surface.fill((0, 0, 0, 160))
        for node in self.discovered_nodes:
            self._fog_surface.fill((0, 0, 0, 0), node.rect)
        for node in self.building_vision_nodes:
            self._fog_surface.fill((0, 0, 0, 0), node.rect)
        surface.blit(self._fog_surface, (0, 0))
```

**Key things to understand:**

- `handle_fog` is called **every frame** — resets previous frame's discovered nodes, then BFS from each friendly player
- `compute_building_vision` is called **once per building event** (spawn or destroy), not per frame
- `write_building=True` writes to `building_vision_nodes`, `False` writes to `discovered_nodes`
- The guard `if not node.discovered` prevents adding the same node twice when two players both see it
- Neighbours are **always** expanded even if visible — a node blocked from player A might be reachable via player B's path

**Test:** Import and construct: `python -c "import pygame; pygame.init(); from client.map_system import MapSystem; from shared.map_data import OBSTACLES, SPAWN_ZONES; m = MapSystem(1280, 800, OBSTACLES, SPAWN_ZONES); print(len(m.nodes), len(m.nodes[0]))"` → should print `25 40`.

---

### STEP 3 — Create `server/entities.py`

**File:** `server/entities.py` (new file)

```python
from shared.constants import (
    RESPAWN_TIME, MINERAL_START, GOLD_TICK_INTERVAL,
    MINERALS_PER_TICK, GOLD_PER_MINERAL
)


class Player:
    def __init__(self, player_id, team):
        self.id = player_id
        self.team = team
        self.pos = [100.0 if team == 0 else 1180.0, 400.0]
        self.hp = 100
        self.max_hp = 100
        self.speed = 200
        self.gold = 0
        self.dx = 0
        self.dy = 0
        self.is_dead = False
        self.respawn_timer = 0.0

    def die(self):
        self.is_dead = True
        self.respawn_timer = RESPAWN_TIME

    def update(self, dt):
        if self.is_dead:
            self.respawn_timer -= dt
            if self.respawn_timer <= 0:
                self.is_dead = False
                self.hp = self.max_hp
                self.pos = [100.0 if self.team == 0 else 1180.0, 400.0]
            return
        self.pos[0] += self.dx * self.speed * dt
        self.pos[1] += self.dy * self.speed * dt
        self.pos[0] = max(0.0, min(self.pos[0], 1280.0))
        self.pos[1] = max(0.0, min(self.pos[1], 800.0))

    def to_dict(self):
        return {
            "id": self.id,
            "team": self.team,
            "pos": self.pos,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "gold": self.gold,
            "is_dead": self.is_dead,
            "respawn_timer": round(self.respawn_timer, 2),
        }


class Building:
    def __init__(self, building_id, pos, team, hp):
        self.id = building_id
        self.pos = list(pos)
        self.team = team
        self.hp = hp
        self.max_hp = hp
        self.is_destroyed = False

    def update(self, dt, players):
        pass

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.__class__.__name__,
            "pos": self.pos,
            "team": self.team,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "is_destroyed": self.is_destroyed,
        }


class Base(Building):
    def __init__(self, building_id, pos, team):
        super().__init__(building_id, pos, team, hp=1000)
        self.mineral_pool = MINERAL_START
        self.gold_tick_timer = 0.0

    def update(self, dt, players):
        if self.is_destroyed or self.mineral_pool <= 0:
            return
        self.gold_tick_timer += dt
        if self.gold_tick_timer >= GOLD_TICK_INTERVAL:
            self.gold_tick_timer = 0.0
            self.mineral_pool = max(0, self.mineral_pool - MINERALS_PER_TICK)
            for player in players.values():
                if player.team == self.team and not player.is_dead:
                    player.gold += GOLD_PER_MINERAL

    def to_dict(self):
        d = super().to_dict()
        d["mineral_pool"] = self.mineral_pool
        return d
```

**Why `Building` is a base class:** Future buildings (Turret, Barracks, etc.) just subclass it and override `update()`. The renderer and snapshot code never need to change — they call `to_dict()` polymorphically and dispatch on `"type"`.

**Test:** `python -c "from server.entities import Player, Base; p = Player(0, 0); b = Base(0, (48,48), 0); print(p.to_dict()); print(b.to_dict())"` → both should print their dicts.

---

### STEP 4 — Rewrite `server/game_state.py`

**File:** `server/game_state.py`

Replace the entire file:

```python
from server.entities import Player, Base
from shared.map_data import BASE_POSITIONS


class GameState:
    def __init__(self):
        self.players = {}
        self.buildings = {}
        self.match_time = 0.0
        self.winner = None
        self._next_building_id = 0
        self._spawn_bases()

    def _spawn_bases(self):
        for team, pos in enumerate(BASE_POSITIONS):
            bid = self._next_building_id
            self._next_building_id += 1
            self.buildings[bid] = Base(bid, pos, team)

    def add_player(self, player_id):
        team = 0 if len(self.players) % 2 == 0 else 1
        self.players[player_id] = Player(player_id, team)

    def remove_player(self, player_id):
        self.players.pop(player_id, None)

    def apply_input(self, player_id, msg):
        player = self.players.get(player_id)
        if not player or player.is_dead:
            return
        player.dx = msg.get("dx", 0)
        player.dy = msg.get("dy", 0)

    def update(self, dt):
        for player in self.players.values():
            player.update(dt)
        for building in self.buildings.values():
            building.update(dt, self.players)
        self._check_win()

    def _check_win(self):
        if self.winner is not None:
            return
        for team in (0, 1):
            enemy = 1 - team
            enemy_buildings = [b for b in self.buildings.values() if b.team == enemy]
            if enemy_buildings and all(b.is_destroyed for b in enemy_buildings):
                self.winner = team
```

**Note on team assignment:** `team = 0 if len(self.players) % 2 == 0 else 1` puts player 1 on team 0, player 2 on team 1, player 3 on team 0, etc. This keeps teams balanced as players connect.

**Test:** `python -c "from server.game_state import GameState; gs = GameState(); gs.add_player(0); gs.add_player(1); gs.update(0.05); print(gs.players, gs.buildings)"` → should print player and building dicts.

---

### STEP 5 — Update `shared/protocol.py`

**File:** `shared/protocol.py`

Change the `make_snapshot` function to include buildings and winner:

```python
def make_snapshot(match_time, players, buildings, winner=None, events=None):
    return {
        "type": "snapshot",
        "match_time": round(match_time, 2),
        "players": {str(pid): p.to_dict() for pid, p in players.items()},
        "buildings": {str(bid): b.to_dict() for bid, b in buildings.items()},
        "winner": winner,
        "events": events or [],
    }
```

Keep `make_input_message` as-is — it's still correct.

---

### STEP 6 — Update `server/net.py`

**File:** `server/net.py`

Find the `make_snapshot(...)` call in `broadcast_loop` and update it to pass buildings and winner:

```python
snapshot = make_snapshot(
    self.game_state.match_time,
    self.game_state.players,
    self.game_state.buildings,
    winner=self.game_state.winner,
    events=[],
)
```

---

### STEP 7 — Fix `client/main.py` screen size

**File:** `client/main.py`

Find this line:
```python
screen = pygame.display.set_mode((1280, 720))
```
Change to:
```python
screen = pygame.display.set_mode((1280, 800))
```

The map PNG is 1280×800. Keeping 720 clips the bottom 80 pixels.

---

### STEP 8 — Rewrite `client/scene.py` SceneTest

**File:** `client/scene.py`

Keep `SceneBase` exactly as-is. Replace `SceneTest` with:

```python
import os
import pygame
import asyncio

from client.net import NetworkClient
from client.map_system import MapSystem
from shared.constants import CLIENT_INPUT_INTERVAL, MAP_W, MAP_H, BASE_VISION
from shared.map_data import OBSTACLES, SPAWN_ZONES

PLAYER_VISION = 150
VISION_BY_TYPE = {"Base": BASE_VISION, "Turret": 150}


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


class SceneTest(SceneBase):
    def __init__(self, client):
        super().__init__(client)
        self.dx = 0
        self.dy = 0
        self.input_send_timer = 0.0
        self.map_system = MapSystem(MAP_W, MAP_H, OBSTACLES, SPAWN_ZONES)
        self.map_bg = pygame.image.load(os.path.join("asset", "map.png")).convert()
        self._prev_building_states = {}
        self._building_vision_dirty = True

    def process_input(self, events):
        super().process_input(events)
        self.dx = 0
        self.dy = 0
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]: self.dx -= 1
        if keys[pygame.K_d]: self.dx += 1
        if keys[pygame.K_w]: self.dy -= 1
        if keys[pygame.K_s]: self.dy += 1

    def update(self, dt):
        super().update(dt)
        self.input_send_timer += dt
        if self.input_send_timer >= CLIENT_INPUT_INTERVAL:
            self.input_send_timer = 0.0
            asyncio.create_task(self.client.send_input(self.dx, self.dy))

        snap = self.client.latest_snapshot
        buildings = snap.get("buildings", {})
        for bid, b in buildings.items():
            prev = self._prev_building_states.get(bid)
            if prev != b.get("is_destroyed"):
                self._building_vision_dirty = True
                self._prev_building_states[bid] = b.get("is_destroyed")

        if self._building_vision_dirty:
            self._recompute_building_vision(buildings)
            self._building_vision_dirty = False

    def _recompute_building_vision(self, buildings):
        sources = []
        for b in buildings.values():
            if not b.get("is_destroyed"):
                node = self.map_system.get_node_from_pos(b["pos"][0], b["pos"][1])
                vision = VISION_BY_TYPE.get(b.get("type", "Base"), BASE_VISION)
                sources.append((node, vision))
        self.map_system.compute_building_vision(sources)

    def render(self, screen):
        screen.blit(self.map_bg, (0, 0))

        snap = self.client.latest_snapshot

        origin_nodes = []
        for pid in self.client.get_entity_ids("players"):
            pos = self.client.get_interpolated_pos("players", pid)
            if pos:
                origin_nodes.append(self.map_system.get_node_from_pos(pos[0], pos[1]))
        self.map_system.handle_fog(origin_nodes, PLAYER_VISION)

        for b in snap.get("buildings", {}).values():
            if not b.get("is_destroyed"):
                col = (60, 100, 220) if b["team"] == 0 else (220, 60, 60)
                pygame.draw.rect(screen, col, (*b["pos"], 32, 32))

        for pid in self.client.get_entity_ids("players"):
            pos = self.client.get_interpolated_pos("players", pid)
            p_data = snap.get("players", {}).get(pid, {})
            if pos and not p_data.get("is_dead"):
                col = (80, 140, 255) if p_data.get("team") == 0 else (255, 80, 80)
                pygame.draw.circle(screen, col, (int(pos[0]), int(pos[1])), 8)

        self.map_system.draw(screen)
```

**Draw order matters:**
1. Map background (bottom layer)
2. Buildings
3. Players
4. Fog overlay (top layer) — painted last so it covers everything

**Fog call order matters:**
`handle_fog` must be called before `draw` — it populates `discovered_nodes` that `draw` iterates.

---

## How the Fog System Works (Summary)

```
Every frame:
  SceneTest.update()
    → handle_fog(origin_nodes, 150)    # resets + BFS from all player positions

  SceneTest.render()
    → map_system.draw(screen)          # paints alpha-160 over whole map,
                                       # then punches alpha-0 holes for discovered nodes

On building event (add / destroy):
  SceneTest.update()
    → _recompute_building_vision()     # BFS from each active friendly building
                                       # (different vision radius per building type)
```

---

## Verification Checklist

Test each step before moving to the next.

| Step | What to check | Pass condition |
|------|--------------|----------------|
| 1 (node.py) | `n.cx`, `n.cy` exist | Print values match expected centre |
| 2 (map_system.py) | Construct MapSystem | Grid is 40×25 nodes, no crash |
| 3 (entities.py) | Construct Player + Base | `to_dict()` returns correct keys |
| 4 (game_state.py) | `GameState.update(0.05)` | No crash, gold ticks after 5s |
| 5 (protocol.py) | Call `make_snapshot(...)` | JSON includes `buildings` key |
| 6 (net.py) | Server starts | No crash on `python -m server.main` |
| 7 (main.py) | Window opens | Window is 1280×800 |
| 8 (scene.py) | Run two clients | Map.png visible, fog dims undiscovered areas, LOS shadows behind obstacles |

---

## asyncio Concepts to Know

Since you're learning asyncio, here's what's happening in this project:

**Server:**
```
asyncio.run(main())
  └─ main() calls asyncio.gather(server, broadcast_loop)
       ├─ server: asyncio.start_server → spawns handle_client() per connection
       └─ broadcast_loop: runs every SNAPSHOT_INTERVAL seconds, sends snapshot to all
```

**Client:**
```
asyncio.run(main())
  └─ main() creates async game_loop() that also starts recv_loop() as a task
       ├─ game_loop: runs every frame, calls asyncio.sleep(0) to yield
       └─ recv_loop: awaits incoming data and updates latest_snapshot
```

`asyncio.sleep(0)` in the game loop is the "yield point" — it lets the recv_loop task run between frames without blocking. Without it, the game loop would hog the event loop and never receive data.
