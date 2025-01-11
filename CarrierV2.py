from game_message import Character, Position, Item, TeamGameState, GameMap, MoveLeftAction, MoveRightAction, MoveUpAction, MoveDownAction, MoveToAction, GrabAction, DropAction, Action
from typing import List, Optional, Tuple, Set
from collections import deque

class Carrier:
  def __init__(self, car: Character, game_state: TeamGameState):
    self.car_id = car.id
    self.position = car.position
    self.alive = car.alive
    self.items = car.carriedItems
    self.hasSpace = car.numberOfCarriedItems < game_state.constants.maxNumberOfItemsCarriedPerCharacter
    self.value = sum(item.value for item in car.carriedItems)

    # Store important game state information
    self.team_id = game_state.currentTeamId
    self.team_zone = game_state.teamZoneGrid
    self.map = game_state.map
    self.tick = game_state.currentTickNumber
    self.all_items = game_state.items
    self.enemies = game_state.otherCharacters
    self.allies = game_state.yourCharacters

  def is_valid_position(self, pos: Position) -> bool:
    """Check if a position is within bounds and not a wall"""
    return (0 <= pos.x < self.map.width and
            0 <= pos.y < self.map.height and
            self.map.tiles[pos.x][pos.y] != "WALL")

  def find_path(self, start: Position, end: Position) -> bool:
    """
    Use BFS to check if there's a valid path between two positions
    Returns True if path exists, False otherwise
    """
    if not self.is_valid_position(end):
      return False

    visited = set()
    queue = deque([(start.x, start.y)])
    visited.add((start.x, start.y))

    # Possible moves: up, down, left, right
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while queue:
      curr_x, curr_y = queue.popleft()

      # If we reached the destination
      if curr_x == end.x and curr_y == end.y:
        return True

      # Try all possible moves
      for dx, dy in directions:
        next_x, next_y = curr_x + dx, curr_y + dy
        next_pos = (next_x, next_y)

        if (next_pos not in visited and
                0 <= next_x < self.map.width and
                0 <= next_y < self.map.height and
                self.map.tiles[next_x][next_y] != "WALL"):
          queue.append(next_pos)
          visited.add(next_pos)

    return False

  def get_closest_item(self, items: List[Item]) -> Optional[Item]:
    """Find the closest reachable item from a list of items"""
    if not items:
      return None

    reachable_items = [
      item for item in items
      if self.find_path(self.position, item.position)
    ]

    if not reachable_items:
      return None

    return min(reachable_items, key=lambda item:
    abs(item.position.x - self.position.x) +
    abs(item.position.y - self.position.y))

  def is_in_team_zone(self, pos: Position) -> bool:
    """Check if a position is in our team's zone"""
    return self.team_zone[pos.x][pos.y] == self.team_id

  def is_in_enemy_zone(self, pos: Position) -> bool:
    """Check if a position is in enemy zone"""
    zone = self.team_zone[pos.x][pos.y]
    return zone != "" and zone != self.team_id

  def is_in_neutral_zone(self, pos: Position) -> bool:
    """Check if a position is in neutral zone"""
    return self.team_zone[pos.x][pos.y] == ""

  def is_safe_position(self, pos: Position) -> bool:
    """Check if a position is safe from enemies and reachable"""
    if not self.find_path(self.position, pos):
      return False

    if not self.is_in_enemy_zone(pos):
      return True

    carrying_blitzium = any(item.type.startswith("blitzium_") for item in self.items)

    # More careful when carrying Blitzium
    if carrying_blitzium:
      for enemy in self.enemies:
        if enemy.alive:
          enemy_dist = abs(enemy.position.x - pos.x) + abs(enemy.position.y - pos.y)
          if enemy_dist <= 2:
            return False
    else:
      # Count nearby enemies when not carrying Blitzium
      nearby_enemies = sum(1 for enemy in self.enemies
                           if enemy.alive and
                           abs(enemy.position.x - pos.x) +
                           abs(enemy.position.y - pos.y) <= 1)
      if nearby_enemies > 1:
        return False
    return True

  def find_radiant_in_team_zone(self) -> Optional[Item]:
    """Find reachable radiant items in our team zone"""
    radiant_items = [
      item for item in self.all_items
      if (item.type == "radiant_core" or item.type == "radiant_slag") and
         self.is_in_team_zone(item.position)
    ]
    return self.get_closest_item(radiant_items)

  def find_blitzium_in_zone(self, check_enemy: bool = True, check_neutral: bool = True) -> Optional[Item]:
    """Find most valuable reachable blitzium items in specified zones"""
    valid_items = []
    for item in self.all_items:
      if not item.type.startswith("blitzium_"):
        continue
      pos = item.position
      if not self.find_path(self.position, pos):
        continue
      if (check_enemy and self.is_in_enemy_zone(pos)) or \
              (check_neutral and self.is_in_neutral_zone(pos)):
        valid_items.append(item)

    if not valid_items:
      return None

    # Sort by value first, then by distance if values are equal
    return max(valid_items,
               key=lambda item: (item.value,
                                 -abs(item.position.x - self.position.x) -
                                 abs(item.position.y - self.position.y)))

  def find_safe_drop_spot_in_enemy_zone(self) -> Optional[Position]:
    """Find a safe and reachable spot in enemy territory to drop items"""
    best_pos = None
    best_score = float('-inf')

    for x in range(self.map.width):
      for y in range(self.map.height):
        pos = Position(x=x, y=y)
        if not self.find_path(self.position, pos):
          continue

        if (self.is_in_enemy_zone(pos) and
                self.map.tiles[x][y] != "WALL" and
                not any(item.position.x == x and item.position.y == y
                        for item in self.all_items)):

          # Calculate safety score based on distance from enemies
          safety_score = min(
            abs(enemy.position.x - x) + abs(enemy.position.y - y)
            for enemy in self.enemies if enemy.alive
          ) if self.enemies else 10  # High safety if no enemies

          if safety_score > best_score:
            best_score = safety_score
            best_pos = pos

    return best_pos

  def handle_radiant_cleanup(self) -> Optional[Action]:
    """Handle radiant item cleanup when no blitzium is accessible"""
    # If carrying radiant, try to drop it in enemy territory
    if any(item.type.startswith("radiant_") for item in self.items):
      if self.is_in_enemy_zone(self.position) and not any(
              item.position.x == self.position.x and
              item.position.y == self.position.y
              for item in self.all_items
      ):
        return DropAction(characterId=self.car_id)

      # Find safe spot to drop in enemy territory
      drop_spot = self.find_safe_drop_spot_in_enemy_zone()
      if drop_spot:
        return MoveToAction(characterId=self.car_id, position=drop_spot)

    # If not carrying radiant, look for radiant in our territory
    elif self.hasSpace:
      radiant = self.find_radiant_in_team_zone()
      if radiant:
        if (self.position.x == radiant.position.x and
                self.position.y == radiant.position.y):
          return GrabAction(characterId=self.car_id)
        return MoveToAction(characterId=self.car_id, position=radiant.position)

    return None

  def get_action(self) -> Optional[Action]:
    """Determine the next action for the carrier"""
    if not self.alive:
      return None

    # If carrying Blitzium, try to bring it home safely
    if any(item.type.startswith("blitzium_") for item in self.items):
      if self.is_in_team_zone(self.position):
        return DropAction(characterId=self.car_id)
      else:
        # Find safe path home
        safe_home_positions = [
          Position(x=x, y=y)
          for x in range(self.map.width)
          for y in range(self.map.height)
          if self.is_in_team_zone(Position(x=x, y=y)) and
             self.is_valid_position(Position(x=x, y=y)) and
             self.find_path(self.position, Position(x=x, y=y))
        ]
        if safe_home_positions:
          closest_pos = min(safe_home_positions,
                            key=lambda pos: abs(pos.x - self.position.x) + abs(pos.y - self.position.y))
          return MoveToAction(characterId=self.car_id, position=closest_pos)

    # Look for accessible Blitzium
    for check_zones in [(True, False), (False, True)]:  # First enemy, then neutral
      blitzium = self.find_blitzium_in_zone(
        check_enemy=check_zones[0],
        check_neutral=check_zones[1]
      )
      if blitzium and self.is_safe_position(blitzium.position):
        if (self.position.x == blitzium.position.x and
                self.position.y == blitzium.position.y):
          return GrabAction(characterId=self.car_id)
        return MoveToAction(characterId=self.car_id, position=blitzium.position)

    # If no Blitzium is accessible, focus on radiant cleanup
    radiant_action = self.handle_radiant_cleanup()
    if radiant_action:
      return radiant_action

    return None