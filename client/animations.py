import os
import pygame

import sys
if getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(sys.executable)
else:
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _archer_frames(folder, name, count):
    return [os.path.join(_ROOT, "asset", "archer", folder, f"{name}{i}.png") for i in range(1, count + 1)]

ANIMATION_DEFS = {
    "Archer": {
        "idle": {
            "frames": _archer_frames("idle",   "archer_idle",   12),
            "fps": 10, "loop": True,
        },
        "running": {
            "frames": _archer_frames("run",    "archer_run",    10),
            "fps": 12, "loop": True,
        },
        "attack": {
            "frames": _archer_frames("attack", "archer_attack", 15),
            "fps": 15, "loop": True,
        },
        "dead": {
            "frames": _archer_frames("death",  "archer_death",  19),
            "fps": 10, "loop": False,  # plays once then freezes on last frame
        },
    },
}

def _anim_duration(anim_def):
    return len(anim_def["frames"]) / anim_def["fps"]


class AnimationController:
    def __init__(self):
        self._cache = {}   # (hero, state, frame_idx) -> Surface
        self._state = {}   # pid -> {"state", "frame", "hold"}

    def get_frame(self, pid, hero, server_state, dt):
        hero_defs = ANIMATION_DEFS.get(hero)
        if hero_defs is None:
            return None

        if pid not in self._state:
            self._state[pid] = {"state": server_state, "frame": 0.0, "hold": 0.0}

        entry = self._state[pid]

        # When server signals attack, latch a hold timer for the full animation duration
        # so the animation always plays through even after is_attacking flips back.
        if server_state == "attack" and entry["state"] != "attack":
            atk_def = hero_defs.get("attack")
            if atk_def:
                entry["hold"] = _anim_duration(atk_def)

        # Decrease hold; while it's active, keep playing the attack animation
        if entry["hold"] > 0:
            entry["hold"] -= dt
            effective_state = "attack"
        else:
            effective_state = server_state

        # Dead always overrides — no mid-death interruption
        if server_state == "dead":
            effective_state = "dead"
            entry["hold"] = 0.0

        anim_def = hero_defs.get(effective_state)
        if anim_def is None:
            return None

        # Reset frame counter on state change
        if entry["state"] != effective_state:
            entry["state"] = effective_state
            entry["frame"] = 0.0

        fps      = anim_def["fps"]
        n_frames = len(anim_def["frames"])
        loop     = anim_def.get("loop", True)
        new_val  = entry["frame"] + dt * fps
        entry["frame"] = new_val % n_frames if loop else min(new_val, n_frames - 1)

        return self._load_frame(hero, effective_state, int(entry["frame"]), anim_def["frames"])

    def _load_frame(self, hero, state, idx, paths):
        key = (hero, state, idx)
        if key not in self._cache:
            try:
                self._cache[key] = pygame.image.load(paths[idx]).convert_alpha()
            except Exception:
                return None
        return self._cache[key]
