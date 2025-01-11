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

  def is_in_neutral_zone(self, position: Position) -> bool:
    """Check if a position is in neutral zone"""
    return self.team_zone[position.x][position.y] == ""

  def is_safe_position(self, position: Position) -> bool:
    """Check if a position is safe from enemies"""
    if not self.is_in_enemy_zone(position):
      return True

    carrying_blitzium = any(item.type.startswith("blitzium_") for item in self.items)

    # More careful when carrying Blitzium
    if carrying_blitzium:
      for enemy in self.enemies:
        if enemy.alive:
          enemy_dist = abs(enemy.position.x - position.x) + abs(enemy.position.y - position.y)
          if enemy_dist <= 2:  # Stay further away when carrying Blitzium
            return False
    else:
      # Count nearby enemies when not carrying Blitzium
      nearby_enemies = sum(1 for enemy in self.enemies
                           if enemy.alive and
                           abs(enemy.position.x - position.x) +
                           abs(enemy.position.y - position.y) <= 1)
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

  def find_drop_spot_near(self, target_pos: Position) -> Optional[Position]:
    """Find a valid spot to drop an item near a target position"""
    max_radius = 3
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

  def get_action(self) -> Optional[Action]:
    """Determine the next action for the carrier"""
    if not self.alive:
      return None

    # If carrying items
    if self.items:
      carrying_radiant = any(item.type.startswith("radiant_") for item in self.items)
      carrying_blitzium = any(item.type.startswith("blitzium_") for item in self.items)

      # If carrying Blitzium, try to bring it home
      if carrying_blitzium:
        if self.is_in_team_zone(self.position):
          # Try to move deeper into our territory
          current_dist_to_border = min(
            abs(self.position.x - x) + abs(self.position.y - y)
            for x in range(self.map.width)
            for y in range(self.map.height)
            if not self.is_in_team_zone(Position(x=x, y=y))
          )

          if current_dist_to_border < 2:  # If too close to border
            deeper_pos = None
            max_dist = current_dist_to_border
            for x in range(self.map.width):
              for y in range(self.map.height):
                pos = Position(x=x, y=y)
                if self.is_in_team_zone(pos):
                  dist_to_border = min(
                    abs(x - bx) + abs(y - by)
                    for bx in range(self.map.width)
                    for by in range(self.map.height)
                    if not self.is_in_team_zone(Position(x=bx, y=by))
                  )
                  if dist_to_border > max_dist:
                    max_dist = dist_to_border
                    deeper_pos = pos

            if deeper_pos:
              return MoveToAction(characterId=self.car_id, position=deeper_pos)

          return DropAction(characterId=self.car_id)
        else:
          # Find safest path home
          min_risk_pos = None
          min_risk = float('inf')
          for x in range(self.map.width):
            for y in range(self.map.height):
              if self.team_zone[x][y] == self.team_id:
                pos = Position(x=x, y=y)
                risk = sum(1 for enemy in self.enemies
                           if enemy.alive and
                           abs(enemy.position.x - x) + abs(enemy.position.y - y) <= 3)
                if risk < min_risk:
                  min_risk = risk
                  min_risk_pos = pos
          if min_risk_pos:
            return MoveToAction(characterId=self.car_id, position=min_risk_pos)

      # Look for Blitzium in enemy zone first
      target_blitzium = self.find_blitzium_in_zone(check_enemy=True, check_neutral=False)
      if not target_blitzium and carrying_radiant:
        # If we have Radiant and no enemy Blitzium, try to drop Radiant
        if self.is_in_enemy_zone(self.position):
          return DropAction(characterId=self.car_id)

        # Find spot to drop Radiant in enemy territory
        for x in range(self.map.width):
          for y in range(self.map.height):
            pos = Position(x=x, y=y)
            if (self.is_in_enemy_zone(pos) and
                    self.map.tiles[x][y] != "WALL" and
                    not any(item.position.x == x and item.position.y == y
                            for item in self.all_items)):
              return MoveToAction(characterId=self.car_id, position=pos)

      # If no enemy Blitzium, look in neutral zone
      if not target_blitzium:
        target_blitzium = self.find_blitzium_in_zone(check_enemy=False, check_neutral=True)

      if target_blitzium:
        if self.position.x == target_blitzium.position.x and \
                self.position.y == target_blitzium.position.y:
          return GrabAction(characterId=self.car_id)
        return MoveToAction(characterId=self.car_id, position=target_blitzium.position)

    # If we have space for items
    if self.hasSpace:
      # First priority: Get radiant items out of our zone
      radiant = self.find_radiant_in_team_zone()
      if radiant:
        if self.position.x == radiant.position.x and self.position.y == radiant.position.y:
          return GrabAction(characterId=self.car_id)
        return MoveToAction(characterId=self.car_id, position=radiant.position)

      # Look for Blitzium opportunities (enemy zone first, then neutral)
      for check_zones in [(True, False), (False, True)]:  # First enemy, then neutral
        blitzium = self.find_blitzium_in_zone(
          check_enemy=check_zones[0],
          check_neutral=check_zones[1]
        )
        if blitzium and self.is_safe_position(blitzium.position):
          if self.position.x == blitzium.position.x and \
                  self.position.y == blitzium.position.y:
            return GrabAction(characterId=self.car_id)
          return MoveToAction(characterId=self.car_id, position=blitzium.position)

    return None