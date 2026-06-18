import pygame
from shared.constants import NODE_SIZE


class Node:
    def __init__(self, x, y, traversable=1, spawn=0):
        self.size = NODE_SIZE
        self.rect = pygame.Rect(x, y, NODE_SIZE, NODE_SIZE)
        self.cx = x + NODE_SIZE // 2
        self.cy = y + NODE_SIZE // 2
        self.traversable = traversable
        self.discovered = 0
        self.building_vision = False
        self.isSpawn = spawn
        self.grid_id = [x / NODE_SIZE, y / NODE_SIZE]
