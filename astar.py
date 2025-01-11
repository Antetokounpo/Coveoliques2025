from collections import defaultdict
from numbers import Number
from functools import partial
from heapq import heappush, heappop
import numpy as np
from game_message import *

def d_manhattan(a: tuple[Number, ...], b: tuple[Number, ...]) -> Number:
    return sum([abs(pair[0] - pair[1]) for pair in zip(a, b)])

def neighbors_one_move_udlr(position: tuple[Number, Number], map: list[list[bool]]) -> list[tuple[Number, Number]]:
    return [(position[0]+i, position[1]+j) for i, j in [(0, -1), (0, 1), (-1, 0), (1, 0)] if map[position[0]+i][position[1]+j]]

def reconstruct_path(came_from, current):
    total_path = [current]

    while current := came_from.get(current):
        total_path.append(current)

    return total_path[::-1]


def A_star(start, goal, neighbors, d, h) -> list[tuple[Number, Number]] | None:

    came_from = {}

    g_score = defaultdict(lambda: float("inf"))

    g_score[start] = 0

    f_score = defaultdict(lambda: float("inf"))
    f_score[start] = h(start)

    open_set = []
    heappush(open_set, (f_score[start], start))
    while open_set:
        _, current = heappop(open_set)

        if current == goal:
            return reconstruct_path(came_from, current)
        
        for node in neighbors(current):
            tentative_g_score = g_score[current] + d(current, node)
            if tentative_g_score < g_score[node]:
                came_from[node] = current
                g_score[node] = tentative_g_score
                f_score[node] = tentative_g_score + h(node)

                if node not in open_set:
                    heappush(open_set, (f_score[node], node))
    

djikstra = partial(A_star, h=lambda _: 0)

def A_star_classic(start, goal, neighbors, d) -> list[tuple[Number, Number]] | None:
    h = partial(d_manhattan, goal)
    return A_star(start, goal, neighbors, d, h)

def convert_to_bool_map(game_message: TeamGameState):
    w, h = game_message.map.width, game_message.map.height

    bool_map = np.full((w, h), True)

    for x in range(w):
        for y in range(h):
            bool_map[x, y] = game_message.map.tiles[x][y] != 'WALL'

    return bool_map

# c'est inplace attention
def add_enemies_to_map(bool_map, game_message: TeamGameState):
    for e in game_message.otherCharacters:
        bool_map[e.position.x, e.position.y] = False

def add_items_to_map(bool_map, game_message: TeamGameState):
    for item in game_message.items:
        bool_map[item.position.x, item.position.y] = False

def A_star_voiture(game_map, start, goal) -> list[tuple[Number, Number]] | None:
    return A_star_classic(start, goal, partial(neighbors_one_move_udlr, map=game_map), d_manhattan)
