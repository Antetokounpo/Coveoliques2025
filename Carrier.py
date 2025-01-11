import game_message
from game_message import Character, Position, Item, TeamGameState, GameMap, MoveLeftAction, MoveRightAction, MoveUpAction, MoveDownAction, MoveToAction, GrabAction, DropAction, Action
from typing import List, Optional, Tuple
import math

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

  def get_closest_item(self, items: List[Item]) -> Optional[Item]:
    """Find the closest item from a list of items"""
    if not items:
      return None

    closest_item = min(items, key=lambda item:
    abs(item.position.x - self.position.x) +
    abs(item.position.y - self.position.y))
    return closest_item

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
    """Check if a position is safe from enemies"""
    if not self.is_in_enemy_zone(pos):
      return True

    carrying_blitzium = any(item.type.startswith("blitzium_") for item in self.items)

    # More careful when carrying Blitzium
    if carrying_blitzium:
      for enemy in self.enemies:
        if enemy.alive:
          enemy_dist = abs(enemy.position.x - pos.x) + abs(enemy.position.y - pos.y)
          if enemy_dist <= 2:  # Stay further away when carrying Blitzium
            return False
    else:
      # Count nearby enemies when not carrying Blitzium
      nearby_enemies = sum(1 for enemy in self.enemies
                           if enemy.alive and
                           abs(enemy.position.x - pos.x) +
                           abs(enemy.position.y - pos.y) <= 1)
      if nearby_enemies > 1:  # Only avoid if multiple enemies are very close
        return False
    return True

  def find_radiant_in_team_zone(self) -> Optional[Item]:
    """Find radiant items in our team zone"""
    radiant_items = [
      item for item in self.all_items
      if (item.type == "radiant_core" or item.type == "radiant_slag") and
         self.is_in_team_zone(item.position)
    ]
    return self.get_closest_item(radiant_items)

  def find_blitzium_in_zone(self, check_enemy: bool = True, check_neutral: bool = True) -> Optional[Item]:
    """Find most valuable blitzium items in specified zones"""
    valid_items = []
    for item in self.all_items:
      if not item.type.startswith("blitzium_"):
        continue
      pos = item.position
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

  def find_drop_spot_near(self, target: Position, max_radius: int = 3) -> Optional[Position]:
    """Find a valid spot to drop an item near a target position"""
    for radius in range(max_radius + 1):
      for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
          pos = Position(
            x=target.x + dx,
            y=target.y + dy
          )

          # Check if position is valid and in enemy zone
          if (0 <= pos.x < self.map.width and
                  0 <= pos.y < self.map.height and
                  self.map.tiles[pos.x][pos.y] != "WALL" and
                  self.is_in_enemy_zone(pos)):

            # Check if position is empty
            if not any(item.position.x == pos.x and
                       item.position.y == pos.y
                       for item in self.all_items):
              return pos
    return None

  def find_safest_team_position(self) -> Optional[Position]:
    """Find the safest valid position in our territory"""
    best_pos = None
    best_score = float('-inf')

    for x in range(self.map.width):
      for y in range(self.map.height):
        # Check if position is valid and in our zone
        pos = Position(x=x, y=y)
        if (self.team_zone[x][y] == self.team_id and
                self.map.tiles[x][y] != "WALL" and
                not any(item.position.x == x and item.position.y == y
                        for item in self.all_items)):

          # Calculate risk from enemies
          risk = sum(1 for enemy in self.enemies
                     if enemy.alive and
                     abs(enemy.position.x - x) + abs(enemy.position.y - y) <= 3)

          # Count non-team adjacent tiles to measure depth
          border_count = sum(1
                             for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]
                             if 0 <= x+dx < self.map.width and
                             0 <= y+dy < self.map.height and
                             self.team_zone[x+dx][y+dy] != self.team_id)

          # Scoring: prefer low risk and low border count (deeper position)
          score = -risk - border_count

          if score > best_score:
            best_score = score
            best_pos = pos

    return best_pos

  def get_action(self) -> Optional[Action]:
    """Determine the next action for the carrier with enemy juking"""
    if not self.alive:
      return None

    # Step 1: If in ally zone and empty, pick up radiant
    if self.is_in_team_zone(self.position) and not self.items:
      radiant = self.find_radiant_in_team_zone()
      if radiant:
        if self.position.x == radiant.position.x and self.position.y == radiant.position.y:
          return GrabAction(characterId=self.car_id)
        return MoveToAction(characterId=self.car_id, position=radiant.position)

    # If carrying items, execute main strategy
    if self.items:
      carrying_radiant = any(item.type.startswith("radiant_") for item in self.items)
      carrying_blitzium = any(item.type.startswith("blitzium_") for item in self.items)

      # Step 2: If carrying radiant, go drop in enemy zone
      if carrying_radiant:
        if self.is_in_enemy_zone(self.position):
          # Check if current spot is safe and empty
          if not any(item.position.x == self.position.x and
                     item.position.y == self.position.y for item in self.all_items):
            return DropAction(characterId=self.car_id)

        # Find safe path to enemy zone
        closest_enemy = min(
          [e for e in self.enemies if e.alive],
          key=lambda e: abs(e.position.x - self.position.x) + abs(e.position.y - self.position.y),
          default=None
        )

        if closest_enemy:
          # Try to find a drop spot that avoids direct enemy contact
          drop_spot = self.find_juke_path_to_enemy(closest_enemy.position)
          if drop_spot:
            return MoveToAction(characterId=self.car_id, position=drop_spot)

      # Step 3: If carrying blitzium, bring it home safely
      if carrying_blitzium:
        if self.is_in_team_zone(self.position):
          deeper_pos = self.find_safest_team_position()
          if deeper_pos and not (self.position.x == deeper_pos.x and
                                 self.position.y == deeper_pos.y):
            return MoveToAction(characterId=self.car_id, position=deeper_pos)
          return DropAction(characterId=self.car_id)
        else:
          # Find safe path home using juking
          safe_pos = self.find_juke_path_home()
          if safe_pos:
            return MoveToAction(characterId=self.car_id, position=safe_pos)

    # No items - look for blitzium to grab
    target_blitzium = self.find_blitzium_in_zone(check_enemy=True, check_neutral=True)
    if target_blitzium and self.hasSpace:
      if (self.position.x == target_blitzium.position.x and
              self.position.y == target_blitzium.position.y):
        return GrabAction(characterId=self.car_id)
      if self.is_safe_position(target_blitzium.position):
        safe_path = self.find_juke_path_to_target(target_blitzium.position)
        if safe_path:
          return MoveToAction(characterId=self.car_id, position=safe_path)

    # If no blitzium available, restart cycle
    return None

  def find_juke_path_to_enemy(self, enemy_pos: Position) -> Optional[Position]:
    """Find a path to enemy zone while avoiding direct enemy contact"""
    possible_positions = []

    for dx in range(-3, 4):
      for dy in range(-3, 4):
        pos = Position(
          x=enemy_pos.x + dx,
          y=enemy_pos.y + dy
        )

        if (0 <= pos.x < self.map.width and
                0 <= pos.y < self.map.height and
                self.map.tiles[pos.x][pos.y] != "WALL" and
                self.is_in_enemy_zone(pos)):

          # Calculate risk score based on enemy positions
          risk_score = sum(1 for enemy in self.enemies
                           if enemy.alive and
                           abs(enemy.position.x - pos.x) +
                           abs(enemy.position.y - pos.y) <= 1)

          # Calculate progress score based on distance to target
          progress_score = -(abs(pos.x - enemy_pos.x) +
                             abs(pos.y - enemy_pos.y))

          if risk_score == 0:  # Only consider safe positions
            possible_positions.append((pos, progress_score))

    if possible_positions:
      # Return position with best progress score
      return max(possible_positions, key=lambda x: x[1])[0]
    return None

  def find_juke_path_home(self) -> Optional[Position]:
    """Find a safe path home while avoiding enemies"""
    safe_spots = []

    # Find all possible positions in our territory
    for x in range(self.map.width):
      for y in range(self.map.height):
        if (self.team_zone[x][y] == self.team_id and
                self.map.tiles[x][y] != "WALL"):
          pos = Position(x=x, y=y)

          # Calculate risk from enemies
          risk = sum(1 for enemy in self.enemies
                     if enemy.alive and
                     abs(enemy.position.x - x) +
                     abs(enemy.position.y - y) <= 2)

          # Calculate progress towards home
          progress = -(abs(x - self.position.x) +
                       abs(y - self.position.y))

          if risk == 0:  # Only consider safe positions
            safe_spots.append((pos, progress))

    if safe_spots:
      # Return position with best progress score
      return max(safe_spots, key=lambda x: x[1])[0]
    return None

  def find_juke_path_to_target(self, target_pos: Position) -> Optional[Position]:
    """Find a safe path to target while avoiding enemies"""
    possible_moves = []

    for dx in range(-2, 3):
      for dy in range(-2, 3):
        pos = Position(
          x=self.position.x + dx,
          y=self.position.y + dy
        )

        if (0 <= pos.x < self.map.width and
                0 <= pos.y < self.map.height and
                self.map.tiles[pos.x][pos.y] != "WALL"):

          # Calculate risk from enemies
          risk = sum(1 for enemy in self.enemies
                     if enemy.alive and
                     abs(enemy.position.x - pos.x) +
                     abs(enemy.position.y - pos.y) <= 1)

          # Calculate progress towards target
          progress = -(abs(pos.x - target_pos.x) +
                       abs(pos.y - target_pos.y))

          if risk == 0:  # Only consider safe positions
            possible_moves.append((pos, progress))

    if possible_moves:
      # Return position with best progress score
      return max(possible_moves, key=lambda x: x[1])[0]
    return None