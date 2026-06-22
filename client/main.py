# Async game loop: initialises pygame, runs the active scene, and drives the network coroutine
import asyncio
import sys
import traceback

import pygame  # safe to import at module level in all environments


def _log(msg):
    print(f"[GD] {msg}")
    if sys.platform == "emscripten":
        try:
            from js import console
            console.log(f"[GD] {msg}")
        except Exception:
            pass


async def main():
    # All client.* imports are deferred to here so any ImportError can be
    # caught and shown on screen rather than silently disappearing into xterm.
    screen = None
    try:
        _log("main() start")
        pygame.init()
        _log("pygame.init() done")
        await asyncio.sleep(0)  # let WASM finish SDL setup

        if sys.platform == "emscripten":
            screen = pygame.display.set_mode((1280, 720))
        else:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

        sw = screen.get_width()
        sh = screen.get_height()
        _log(f"display {sw}x{sh}")

        # Paint red immediately to confirm display is functional
        screen.fill((220, 0, 0))
        pygame.display.flip()
        await asyncio.sleep(0)
        _log("first flip done")

        _log("importing scene...")
        import client.scene as scene_mod
        from client.scene import SceneMenu, VIEWPORT_W, VIEWPORT_H
        from shared.constants import FPS
        _log("imports done")

        scene_mod._SCREEN_W = sw
        scene_mod._SCREEN_H = sh
        scene_mod._SCALE_X  = sw / VIEWPORT_W
        scene_mod._SCALE_Y  = sh / VIEWPORT_H

        game_surf = pygame.Surface((VIEWPORT_W, VIEWPORT_H))
        ui_surf   = pygame.Surface((sw, sh), pygame.SRCALPHA)
        clock     = pygame.time.Clock()

        _log("creating SceneMenu...")
        active_scene = SceneMenu()
        _log("entering game loop")

        while active_scene is not None:
            events = pygame.event.get()
            dt = clock.tick(FPS) / 1000.0

            active_scene.process_input(events)
            active_scene.update(dt)

            active_scene.render(game_surf)
            pygame.transform.scale(game_surf, (sw, sh), screen)

            ui_surf.fill((0, 0, 0, 0))
            active_scene.render_ui(ui_surf)
            screen.blit(ui_surf, (0, 0))

            active_scene = active_scene.next_scene
            pygame.display.flip()
            await asyncio.sleep(0)

        pygame.quit()

    except Exception:
        err = traceback.format_exc()
        _log(f"EXCEPTION:\n{err}")
        if screen is not None:
            try:
                _show_error(screen, err)
                pygame.display.flip()
            except Exception:
                pass
        await asyncio.sleep(120)


def _show_error(screen, err_text):
    screen.fill((180, 30, 30))
    try:
        font = pygame.font.Font(None, 18)
    except Exception:
        return
    y = 8
    for line in err_text.split('\n'):
        for chunk in [line[i:i + 90] for i in range(0, max(len(line), 1), 90)]:
            surf = font.render(chunk, True, (255, 255, 255))
            screen.blit(surf, (8, y))
            y += 20
            if y > screen.get_height() - 20:
                return


if __name__ == "__main__":
    # Local desktop run — restore module-level imports for PyInstaller
    import client.scene as _scene  # noqa: F401 (tells PyInstaller to bundle it)
    asyncio.run(main())
