# Async game loop: initialises pygame, runs the active scene, and drives the network coroutine
import asyncio
import sys

import pygame

import client.scene as scene_mod
from shared.constants import FPS
from client.scene import SceneMenu, VIEWPORT_W, VIEWPORT_H


async def main():
    pygame.init()
    if sys.platform == "emscripten":
        screen = pygame.display.set_mode((VIEWPORT_W, VIEWPORT_H))
    else:
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

    active_scene = SceneMenu()

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


if __name__ == "__main__":
    asyncio.run(main())
