# GloryDay — Game Design Document

## Overview

**GloryDay** is a 3v3 real-time action-strategy game. Two teams of three heroes fight for economic control of a fixed map. Gold comes from capturing and holding mineral bases. The team that destroys every enemy building wins.

---

## Core Loop

```
Spawn at base → earn gold from minerals → buy items → fight →
capture more bases → drain enemy economy → destroy enemy buildings → win
```

The economy is the pressure valve. Each base has a finite mineral pool. As your starting base runs dry, you're forced to push outward — straight toward the enemy.

---

## Map

- **Size:** 1280 × 800 pixels (fixed screen, no scroll for now)
- **Background:** `asset/map.png`
- **Team 0 spawn:** top-left corner (0, 0, 96×96)
- **Team 1 spawn:** bottom-right corner (1184, 704, 96×96)
- **Obstacles:** 37 wall structures that block movement and line-of-sight
- **Heal zones:** 4 locations that restore HP on contact *(future)*
- **Capture zone:** centre of map (512, 320, 255×127) — reserved for future objective

---

## Buildings

| Building | HP   | Vision | Gold source | Notes |
|----------|------|--------|-------------|-------|
| Base     | 1000 | 200px  | Yes — passive tick from mineral pool | One per team at start |
| Turret   | 300  | 150px  | No | Hero-placed; attacks enemies in range *(future)* |

- Every building can be destroyed
- Destroying **all** enemy buildings = win
- Buildings provide static vision for their team (pre-computed once per building event, not per frame)

---

## Economy

| Constant | Value | Meaning |
|----------|-------|---------|
| `MINERAL_START` | 1500 | Minerals per base on spawn |
| `MINERALS_PER_TICK` | 2 | Minerals consumed every tick |
| `GOLD_PER_MINERAL` | 1 | Gold gained by each teammate per tick |
| `GOLD_TICK_INTERVAL` | 5.0s | Seconds between ticks |

- When a base's mineral pool hits 0, it stops generating gold (still stands until destroyed)
- Each player holds personal gold — not shared with teammates
- Players spend gold at a shop to buy items *(shop system: future)*

**Why this creates pressure:** both teams start with ~12.5 minutes of income from their main base (1500 ÷ 2 = 750 ticks × 5s = 3750s / 60 ≈ 62 min — or at 1 gold/teammate that's 750 gold per player from base alone). But additional bases cut that to a fraction. Teams that expand earn more; teams that stand still fall behind.

---

## Heroes

- **Count:** 3 per team (6 total)
- **Movement:** WASD, server-authoritative (`speed × dt` per tick)
- **Speed:** 200 px/s
- **Vision:** 150px radius BFS + line-of-sight from hero position, updated every frame

### Death & Respawn

1. Hero HP drops to 0 → marked `is_dead = True`
2. `respawn_timer` counts down from `RESPAWN_TIME` (8 seconds)
3. Timer hits 0 → hero teleports to team's **main base**, full HP, `is_dead = False`
4. While dead: input ignored, hero not rendered on client

### Future Hero Abilities

One hero archetype will be able to **place turrets** on the map. Turrets are `Building` subclasses, attacking nearby enemies and granting vision.

---

## Fog of War

- The whole map is always **dimly visible** (alpha-160 dark overlay) — players can orient themselves
- Nodes within a friendly hero's vision radius **and** clear line-of-sight are **fully revealed**
- Nodes within a friendly **building's** vision radius and clear LOS are also fully revealed
- Vision is **shared** across teammates — all 3 heroes' vision merges each frame
- Obstacles cast hard LOS shadows using `pygame.Rect.clipline()`
- Building vision is pre-computed once when a building is added or destroyed, not every frame

---

## Win Condition

A team wins when **every building belonging to the enemy team** has `is_destroyed = True`. The server checks this every tick via `_check_win()` and broadcasts a `winner` field in the snapshot.

---

## Future Systems (not in prototype)

- Item shop and purchasable upgrades
- Hero abilities (Q/W/E/R)
- Turret placement by heroes
- Capture zone objective
- Heal zones
- Camera scroll for larger maps
- Champion selection screen
