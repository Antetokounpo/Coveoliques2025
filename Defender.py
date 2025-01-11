from game_message import Character, Position, Item, TeamGameState, GameMap, MoveLeftAction, MoveRightAction, MoveUpAction, MoveDownAction, DropAction, Action
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass

@dataclass
class Target:
  enemy: Character
  defender_id: str
  threat_level: float
  last_seen_position: Position

class Defender:
  # Class variable to track all targets
  _targets: Dict[str, Target] = {}

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

    # Clear old targets if this is first defender initialization this tick
    if any(ally.id == self.allies[0].id for ally in self.allies):
      self._targets.clear()

    # Initialize or update current target
    self.current_target = None
    self.update_target()

  def is_valid_position(self, x: int, y: int) -> bool:
    """Check if a position is valid (in bounds and not a wall)"""
    if not (0 <= x < self.map.width and 0 <= y < self.map.height):
      return False
    return self.map.tiles[x][y] != "WALL"

  def is_in_our_territory(self, position: Position) -> bool:
    """Check if a position is in our territory"""
    return self.team_zone[position.x][position.y] == self.team_id

  @staticmethod
  def manhattan_distance(pos1: Position, pos2: Position) -> int:
    """Calculate Manhattan distance between two positions"""
    return abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y)

  def calculate_threat_level(self, enemy: Character) -> float:
    """Calculate threat level of an enemy based on various factors"""
    if not enemy.alive or enemy.numberOfCarriedItems == 0:
      return 0.0

    threat = sum(item.value for item in enemy.carriedItems)

    # Higher threat if closer to our territory
    distance_to_border = min(
      self.manhattan_distance(enemy.position, pos)
      for x in range(self.map.width)
      for y in range(self.map.height)
      if self.is_in_our_territory(pos := Position(x, y))
    )

    # Exponential decay of threat with distance
    threat *= max(0.1, 1 - (distance_to_border * 0.1))

    # Bonus threat if enemy is moving towards our territory
    if self.is_approaching_territory(enemy):
      threat *= 1.5

    return threat

  def is_approaching_territory(self, enemy: Character) -> bool:
    """Check if enemy appears to be moving towards our territory"""
    # Find closest border point
    min_distance = float('inf')
    closest_border = None

    for x in range(self.map.width):
      for y in range(self.map.height):
        pos = Position(x, y)
        if self.is_in_our_territory(pos):
          # Check if it's a border point
          is_border = any(
            not self.is_in_our_territory(Position(x + dx, y + dy))
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]
            if self.is_valid_position(x + dx, y + dy)
          )
          if is_border:
            dist = self.manhattan_distance(enemy.position, pos)
            if dist < min_distance:
              min_distance = dist
              closest_border = pos

    if not closest_border:
      return False

    # If enemy is very close to border, consider them approaching
    if min_distance <= 2:
      return True

    # TODO: Could be enhanced by tracking enemy's previous positions
    # and determining their movement vector
    return True

  def update_target(self):
    """Update current target based on threats and other defenders"""
    # Remove dead or empty targets
    self._targets = {
      enemy_id: target for enemy_id, target in self._targets.items()
      if any(e.id == enemy_id and e.alive and e.numberOfCarriedItems > 0
             for e in self.enemies)
    }

    # Calculate threats for all enemies
    threats = [
      (enemy, self.calculate_threat_level(enemy))
      for enemy in self.enemies
    ]

    # Sort by threat level
    threats.sort(key=lambda x: x[1], reverse=True)

    # First, check if we should keep current target
    if self.current_target and self.current_target.enemy.id in self._targets:
      target = self._targets[self.current_target.enemy.id]
      if target.defender_id == self.car_id:
        # Update threat level and position
        enemy = next(e for e in self.enemies if e.id == target.enemy.id)
        self.current_target = Target(
          enemy=enemy,
          defender_id=self.car_id,
          threat_level=self.calculate_threat_level(enemy),
          last_seen_position=enemy.position
        )
        self._targets[enemy.id] = self.current_target
        return

    # Try to find new target
    for enemy, threat in threats:
      # Skip if enemy already targeted by another defender
      if enemy.id in self._targets and self._targets[enemy.id].defender_id != self.car_id:
        continue

      if threat > 0:
        self.current_target = Target(
          enemy=enemy,
          defender_id=self.car_id,
          threat_level=threat,
          last_seen_position=enemy.position
        )
        self._targets[enemy.id] = self.current_target
        return

    self.current_target = None

  def get_border_intercept_position(self, enemy: Character) -> Optional[Position]:
    """Calculate optimal border position to intercept enemy"""
    if not enemy.alive:
      return None

    best_pos = None
    min_score = float('inf')

    # Find border points
    for x in range(self.map.width):
      for y in range(self.map.height):
        pos = Position(x, y)
        if not self.is_in_our_territory(pos):
          continue

        # Check if it's a border point
        is_border = any(
          not self.is_in_our_territory(Position(x + dx, y + dy))
          for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]
          if self.is_valid_position(x + dx, y + dy)
        )

        if not is_border:
          continue

        # Score based on distance to enemy and current position
        distance_to_enemy = self.manhattan_distance(pos, enemy.position)
        distance_to_self = self.manhattan_distance(pos, self.position)

        # Prefer positions ahead of enemy's path
        score = distance_to_enemy + (distance_to_self * 0.5)

        if score < min_score:
          min_score = score
          best_pos = pos

    return best_pos

  def find_patrol_position(self) -> Optional[Position]:
    """Find optimal patrol position"""
    best_score = float('-inf')
    best_position = None

    # Get all enemies carrying valuable items
    valuable_enemies = [
      enemy for enemy in self.enemies
      if enemy.alive and sum(item.value for item in enemy.carriedItems) > 0
    ]

    # Get all valuable items in our territory
    valuable_items = [
      item for item in self.all_items
      if item.value > 0 and self.is_in_our_territory(item.position)
    ]

    for x in range(self.map.width):
      for y in range(self.map.height):
        if not self.is_valid_position(x, y):
          continue

        current_pos = Position(x, y)
        if not self.is_in_our_territory(current_pos):
          continue

        score = 0

        # Score based on territory coverage
        for enemy in valuable_enemies:
          dist = self.manhattan_distance(current_pos, enemy.position)
          if dist <= 3:
            score += 10 / (dist + 1)  # Higher weight for enemy proximity

        # Score based on valuable item protection
        for item in valuable_items:
          dist = self.manhattan_distance(current_pos, item.position)
          if dist <= 2:
            score += 5 / (dist + 1)  # Lower weight for item proximity

        # Bonus for central positions in our territory
        territory_bonus = sum(
          1 for dx in range(-2, 3)
          for dy in range(-2, 3)
          if (0 <= x + dx < self.map.width and
              0 <= y + dy < self.map.height and
              self.is_in_our_territory(Position(x + dx, y + dy)))
        )
        score += territory_bonus * 0.5

        if score > best_score:
          best_score = score
          best_position = current_pos

    return best_position

  def get_next_move(self, target_pos: Position) -> Optional[Action]:
    """
    Get the next move towards a target position while staying in our territory.
    Returns appropriate MoveAction (Left/Right/Up/Down) based on best direction.
    """
    if not target_pos:
      return None

    best_direction = None
    min_distance = float('inf')

    # Define directions and their corresponding Action classes
    direction_actions = [
      ((0, 1), lambda cid: MoveDownAction(characterId=cid)),   # Down
      ((0, -1), lambda cid: MoveUpAction(characterId=cid)),    # Up
      ((1, 0), lambda cid: MoveRightAction(characterId=cid)),  # Right
      ((-1, 0), lambda cid: MoveLeftAction(characterId=cid))   # Left
    ]

    for (dx, dy), action_creator in direction_actions:
      new_x = self.position.x + dx
      new_y = self.position.y + dy

      if not self.is_valid_position(new_x, new_y):
        continue

      if not self.is_in_our_territory(Position(new_x, new_y)):
        continue

      # Check if any enemy will be in interception range
      will_intercept = any(
        self.manhattan_distance(Position(new_x, new_y), enemy.position) <= 1
        for enemy in self.enemies
        if enemy.alive and enemy.numberOfCarriedItems > 0
      )

      new_distance = abs(new_x - target_pos.x) + abs(new_y - target_pos.y)

      # Prefer positions that lead to interception if enemies are nearby
      if will_intercept:
        new_distance -= 2

      if new_distance < min_distance:
        min_distance = new_distance
        best_direction = action_creator

    return best_direction(self.car_id) if best_direction else None

  def should_drop_items(self) -> bool:
    """Only drop negative value items since we're safe in our territory"""
    return self.value < 0

  def get_action(self) -> Optional[Action]:
    """Get the next action for this defender"""
    # First check if we need to drop items
    if self.should_drop_items():
      return DropAction(characterId=self.car_id)

    # Update targeting
    self.update_target()

    if self.current_target:
      enemy = self.current_target.enemy

      # If enemy is in our territory, chase directly
      if self.is_in_our_territory(enemy.position):
        if self.manhattan_distance(self.position, enemy.position) <= 1:
          return None  # Adjacent - interception happens automatically
        return self.get_next_move(enemy.position)

      # Otherwise, move to intercept position at border
      intercept_pos = self.get_border_intercept_position(enemy)
      if intercept_pos:
        return self.get_next_move(intercept_pos)

    # If no target, patrol as before
    patrol_position = self.find_patrol_position()
    return self.get_next_move(patrol_position)