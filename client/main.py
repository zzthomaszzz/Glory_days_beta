# Async game loop: initialises pygame, runs the active scene, and drives the network coroutine
import asyncio
import sys
import traceback

import pygame

import client.scene as scene_mod
from shared.constants import FPS
from client.scene import SceneMenu, VIEWPORT_W, VIEWPORT_H


async def main():
    pygame.init()
    # Always use FULLSCREEN so pygame fills the entire canvas (desktop and browser).
    # In the browser pygbag sets the canvas to 1280x720; a fixed (640,400) mode
    # only paints the top-left corner and leaves the rest black.
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    sw = screen.get_width()
    sh = screen.get_height()
    pygame.display.set_caption("GloryDay")
    pygame.mouse.set_visible(True)

    scene_mod._SCREEN_W = sw
    scene_mod._SCREEN_H = sh
    scene_mod._SCALE_X  = sw / VIEWPORT_W
    scene_mod._SCALE_Y  = sh / VIEWPORT_H

    game_surf = pygame.Surface((VIEWPORT_W, VIEWPORT_H))
    ui_surf   = pygame.Surface((sw, sh), pygame.SRCALPHA)
    clock     = pygame.time.Clock()

    try:
        active_scene = SceneMenu()
    except Exception:
        _show_error(screen, traceback.format_exc())
        pygame.display.flip()
        await asyncio.sleep(60)
        return

    while active_scene is not None:
        try:
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
        except Exception:
            _show_error(screen, traceback.format_exc())
            pygame.display.flip()
            await asyncio.sleep(60)
            return
        await asyncio.sleep(0)

    pygame.quit()


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
    asyncio.run(main())
