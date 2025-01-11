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

  def is_in_team_zone(self, position: Position) -> bool:
    """Check if a position is in our team's zone"""
    return self.team_zone[position.x][position.y] == self.team_id

  def is_in_enemy_zone(self, position: Position) -> bool:
    """Check if a position is in enemy zone"""
    zone = self.team_zone[position.x][position.y]
    return zone != "" and zone != self.team_id

  def is_safe_position(self, position: Position) -> bool:
    """Check if a position is safe from enemies.
    More tolerant of risk when carrying Radiant items, but still tries to avoid death."""
    if not self.is_in_enemy_zone(position):
      return True

    carrying_radiant = any(item.type.startswith("radiant_") for item in self.items)
    safe_distance = 1 if carrying_radiant else 2  # Be more willing to get closer when carrying Radiant

    # Count nearby enemies
    nearby_enemies = 0
    for enemy in self.enemies:
      if enemy.alive:
        enemy_dist = abs(enemy.position.x - position.x) + abs(enemy.position.y - position.y)
        if enemy_dist <= safe_distance:
          nearby_enemies += 1

    # When carrying Radiant, we can tolerate more risk but still avoid certain death
    if carrying_radiant:
      return nearby_enemies <= 1  # Only risk it if there's at most one enemy nearby
    else:
      return nearby_enemies == 0  # No enemies nearby when carrying Blitzium

  def find_radiant_in_team_zone(self) -> Optional[Item]:
    """Find radiant items in our team zone"""
    radiant_items = [
      item for item in self.all_items
      if (item.type == "radiant_core" or item.type == "radiant_slag") and
         self.is_in_team_zone(item.position)
    ]
    return self.get_closest_item(radiant_items)

  def find_blitzium_in_enemy_zone(self) -> Optional[Item]:
    """Find blitzium items in enemy zone"""
    blitzium_items = [
      item for item in self.all_items
      if (item.type.startswith("blitzium_")) and
         self.is_in_enemy_zone(item.position)
    ]
    return self.get_closest_item(blitzium_items)

  def find_drop_spot_near(self, target_pos: Position, max_radius: int = 3) -> Optional[Position]:
    """Find a valid spot to drop an item near a target position"""
    # Search in increasing radius
    for radius in range(max_radius + 1):
      for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
          new_pos = Position(
            x=target_pos.x + dx,
            y=target_pos.y + dy
          )

          # Check if position is valid
          if (0 <= new_pos.x < self.map.width and
                  0 <= new_pos.y < self.map.height and
                  self.map.tiles[new_pos.x][new_pos.y] != "WALL" and
                  self.is_in_enemy_zone(new_pos)):

            # Check if position is empty
            if not any(item.position.x == new_pos.x and
                       item.position.y == new_pos.y
                       for item in self.all_items):
              return new_pos
    return None

  def should_drop_radiant_for_blitzium(self, blitzium: Item) -> bool:
    """Determine if we should drop our Radiant items to pick up Blitzium"""
    if not any(item.type.startswith("radiant_") for item in self.items):
      return False

    # Calculate if we're close enough to the Blitzium to consider dropping Radiant
    dist_to_blitzium = (abs(self.position.x - blitzium.position.x) +
                        abs(self.position.y - blitzium.position.y))

    # Only drop if we're relatively close and the position is relatively safe
    return (dist_to_blitzium <= 3 and
            self.is_safe_position(blitzium.position) and
            len(self.items) + 1 > self.hasSpace)

  def get_action(self) -> Optional[Action]:
    """Determine the next action for the carrier"""
    if not self.alive:
      return None

    # If carrying items, handle them based on their type
    if self.items:
      if any(item.type.startswith("radiant_") for item in self.items):
        # When carrying Radiant items, move strategically into enemy territory
        if self.is_in_enemy_zone(self.position):
          return DropAction(characterId=self.car_id)
        else:
          # Find optimal position in enemy territory
          best_position = None
          best_score = float('-inf')

          for x in range(self.map.width):
            for y in range(self.map.height):
              pos = Position(x=x, y=y)
              if (self.team_zone[x][y] != self.team_id and
                      self.team_zone[x][y] != "" and
                      self.map.tiles[x][y] != "WALL"):

                # Calculate position score based on multiple factors
                dist = abs(x - self.position.x) + abs(y - self.position.y)
                enemy_count = sum(1 for enemy in self.enemies
                                  if enemy.alive and
                                  abs(enemy.position.x - x) + abs(enemy.position.y - y) <= 2)

                # Score formula considers:
                # - Distance (closer is better)
                # - Enemy presence (fewer enemies is better)
                # - Edge of enemy territory (preferred as it's safer)
                score = -dist - (enemy_count * 5)

                # Bonus for positions at the edge of enemy territory
                edge_bonus = any(
                  0 <= nx < self.map.width and
                  0 <= ny < self.map.height and
                  self.team_zone[nx][ny] != self.team_zone[x][y]
                  for nx, ny in [(x+1,y), (x-1,y), (x,y+1), (x,y-1)]
                )
                if edge_bonus:
                  score += 3

                if score > best_score:
                  best_score = score
                  best_position = pos

          if best_position and self.is_safe_position(best_position):
            return MoveToAction(characterId=self.car_id, position=best_position)

          # If no safe position found, stay in place or retreat
          return None
      else:
        # Bring blitzium back to our zone
        if self.is_in_team_zone(self.position):
          return DropAction(characterId=self.car_id)
        else:
          # Find closest position in our zone
          for x in range(self.map.width):
            for y in range(self.map.height):
              if self.team_zone[x][y] == self.team_id:
                return MoveToAction(
                  characterId=self.car_id,
                  position=Position(x=x, y=y)
                )

    # If we have space for items
    if self.hasSpace:
      # First priority: Get radiant items out of our zone
      radiant = self.find_radiant_in_team_zone()
      if radiant:
        if self.position.x == radiant.position.x and self.position.y == radiant.position.y:
          return GrabAction(characterId=self.car_id)
        return MoveToAction(characterId=self.car_id, position=radiant.position)

      # Second priority: Get blitzium from enemy zone
      blitzium = self.find_blitzium_in_enemy_zone()
      if blitzium and self.is_safe_position(blitzium.position):
        if self.position.x == blitzium.position.x and self.position.y == blitzium.position.y:
          return GrabAction(characterId=self.car_id)
        return MoveToAction(characterId=self.car_id, position=blitzium.position)

    # If no other action is available, move to a safe position
    return None