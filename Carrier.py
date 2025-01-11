import game_message
from game_message import Character, Position, Item, TeamGameState, GameMap, MoveLeftAction, MoveRightAction, MoveUpAction, MoveDownAction, MoveToAction, GrabAction, DropAction, Action
from typing import List, Optional, Tuple

class Carrier:
  def __init__(self, car: Character, game_state: TeamGameState):
    self.car_id = car.id
    self.position = car.position
    self.alive = car.alive
    self.items = car.carriedItems
    self.hasSpace = car.numberOfCarriedItems < game_state.constants.maxNumberOfItemsCarriedPerCharacter

    # Store important game state information
    self.team_id = game_state.currentTeamId
    self.team_zone = game_state.teamZoneGrid
    self.map = game_state.map
    self.tick = game_state.currentTickNumber
    self.all_items = game_state.items
    self.enemies = game_state.otherCharacters
    self.allies = game_state.yourCharacters

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

  def is_position_reachable(self, pos: Position) -> bool:
    """Check if a position can be reached (not surrounded by walls)"""
    if not (0 <= pos.x < self.map.width and 0 <= pos.y < self.map.height):
      return False
    if self.map.tiles[pos.x][pos.y] == "WALL":
      return False

    # Check if at least one adjacent tile is not a wall
    for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
      new_x, new_y = pos.x + dx, pos.y + dy
      if (0 <= new_x < self.map.width and
              0 <= new_y < self.map.height and
              self.map.tiles[new_x][new_y] != "WALL"):
        return True
    return False

  def is_safe_position(self, pos: Position) -> bool:
    """Check if a position is safe from enemies"""
    if not (0 <= pos.x < self.map.width and 0 <= pos.y < self.map.height):
      return False
    if self.map.tiles[pos.x][pos.y] == "WALL":
      return False

    # Count nearby enemies
    nearby_enemies = sum(1 for enemy in self.enemies
                         if enemy.alive and
                         abs(enemy.position.x - pos.x) +
                         abs(enemy.position.y - pos.y) <= 1)
    return nearby_enemies == 0

  def find_nearest_enemy(self) -> Optional[Character]:
    """Find the closest alive enemy"""
    alive_enemies = [e for e in self.enemies if e.alive]
    if not alive_enemies:
      return None

    return min(alive_enemies,
               key=lambda e: abs(e.position.x - self.position.x) +
                             abs(e.position.y - self.position.y))

  def find_radiant_in_team_zone(self) -> Optional[Item]:
    """Find closest radiant in our team zone"""
    radiant_items = [
      item for item in self.all_items
      if (item.type == "radiant_core" or item.type == "radiant_slag") and
         self.is_in_team_zone(item.position) and
         self.is_position_reachable(item.position)
    ]

    if not radiant_items:
      return None

    return min(radiant_items,
               key=lambda i: abs(i.position.x - self.position.x) +
                             abs(i.position.y - self.position.y))

  def find_reachable_blitzium(self) -> Optional[Item]:
    """Find highest value reachable blitzium in enemy/neutral zones"""
    valid_items = [
      item for item in self.all_items
      if (item.type.startswith("blitzium_") and
          (self.is_in_enemy_zone(item.position) or
           self.is_in_neutral_zone(item.position)) and
          self.is_position_reachable(item.position))
    ]

    if not valid_items:
      return None

    return max(valid_items,
               key=lambda i: (i.value,
                              -(abs(i.position.x - self.position.x) +
                                abs(i.position.y - self.position.y))))

  def find_safe_move_towards(self, target_pos: Position) -> Optional[Position]:
    """Find a safe move that gets us closer to the target"""
    if not self.is_position_reachable(target_pos):
      return None

    best_pos = None
    best_score = float('-inf')
    current_dist = abs(self.position.x - target_pos.x) + abs(self.position.y - target_pos.y)

    for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
      new_x = self.position.x + dx
      new_y = self.position.y + dy
      new_pos = Position(x=new_x, y=new_y)

      if not self.is_safe_position(new_pos):
        continue

      new_dist = abs(new_x - target_pos.x) + abs(new_y - target_pos.y)
      progress = current_dist - new_dist

      if progress > best_score:
        best_score = progress
        best_pos = new_pos

    return best_pos

  def get_action(self) -> Optional[Action]:
    """Main action loop"""
    if not self.alive:
      return None

    # 1. If we have items, handle them first
    carrying_radiant = any(item.type.startswith("radiant_") for item in self.items)
    carrying_blitzium = any(item.type.startswith("blitzium_") for item in self.items)

    if carrying_blitzium:
      # Bring blitzium home
      if self.is_in_team_zone(self.position):
        return DropAction(characterId=self.car_id)

      nearest_home = None
      min_dist = float('inf')
      for x in range(self.map.width):
        for y in range(self.map.height):
          if self.team_zone[x][y] == self.team_id:
            dist = abs(x - self.position.x) + abs(y - self.position.y)
            if dist < min_dist:
              min_dist = dist
              nearest_home = Position(x=x, y=y)

      if nearest_home:
        safe_move = self.find_safe_move_towards(nearest_home)
        if safe_move:
          return MoveToAction(characterId=self.car_id, position=safe_move)

    if carrying_radiant:
      # Try to drop radiant in enemy zone
      if self.is_in_enemy_zone(self.position):
        if not any(item.position.x == self.position.x and
                   item.position.y == self.position.y
                   for item in self.all_items):
          return DropAction(characterId=self.car_id)

      nearest_enemy = self.find_nearest_enemy()
      if nearest_enemy:
        safe_move = self.find_safe_move_towards(nearest_enemy.position)
        if safe_move:
          return MoveToAction(characterId=self.car_id, position=safe_move)

    # 2. If we're empty, look for items to grab
    if self.hasSpace:
      # First priority: Grab radiant from our zone
      if self.is_in_team_zone(self.position):
        radiant = self.find_radiant_in_team_zone()
        if radiant:
          if self.position.x == radiant.position.x and self.position.y == radiant.position.y:
            return GrabAction(characterId=self.car_id)
          return MoveToAction(characterId=self.car_id, position=radiant.position)

      # Second priority: Get reachable blitzium
      blitzium = self.find_reachable_blitzium()
      if blitzium:
        if self.position.x == blitzium.position.x and self.position.y == blitzium.position.y:
          return GrabAction(characterId=self.car_id)
        safe_move = self.find_safe_move_towards(blitzium.position)
        if safe_move:
          return MoveToAction(characterId=self.car_id, position=safe_move)

      # Third priority: Keep cleaning radiant
      radiant = self.find_radiant_in_team_zone()
      if radiant:
        return MoveToAction(characterId=self.car_id, position=radiant.position)

      # Fourth priority: Move towards enemy zone for future drops
      nearest_enemy = self.find_nearest_enemy()
      if nearest_enemy:
        safe_move = self.find_safe_move_towards(nearest_enemy.position)
        if safe_move:
          return MoveToAction(characterId=self.car_id, position=safe_move)

    return None