from game_message import Character, Position, Item, TeamGameState, GameMap, MoveLeftAction, MoveRightAction, \
  MoveUpAction, MoveDownAction, Action, DropAction
from typing import List, Optional, Tuple, Dict

class Target:
  def __init__(self, enemy: Character, defender_id: str, threat_level: float):
    self.enemy = enemy
    self.defender_id = defender_id
    self.threat_level = threat_level
    self.last_seen_pos = enemy.position

class Defender:
  # Class variable to track targets across all defender instances
  _targets: Dict[str, Target] = {}

  def __init__(self, car: Character, game_state: TeamGameState):
    self.car_id = car.id
    self.position = car.position
    self.alive = car.alive

    # Store important game state information
    self.team_id = game_state.currentTeamId
    self.team_zone = game_state.teamZoneGrid
    self.map = game_state.map
    self.tick = game_state.currentTickNumber
    self.enemies = game_state.otherCharacters
    self.allies = game_state.yourCharacters

    # Reset targets at start of new tick
    if any(ally.id == self.allies[0].id for ally in self.allies):
      self._targets.clear()

    # Initialize current target
    self.current_target = None
    self.update_target()

  def is_valid_position(self, x: int, y: int) -> bool:
    """Check if a position is valid (in bounds and not a wall)"""
    if not (0 <= x < self.map.width and 0 <= y < self.map.height):
      return False
    return self.map.tiles[x][y] != "WALL"  # [X][Y] order

  def is_in_our_territory(self, position: Position) -> bool:
    """Check if a position is in our territory"""
    return self.team_zone[position.x][position.y] == self.team_id  # [X][Y] order

  @staticmethod
  def manhattan_distance(pos1: Position, pos2: Position) -> int:
    """Calculate Manhattan distance between two positions"""
    return abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y)

  def calculate_threat_level(self, enemy: Character) -> float:
    """Calculate how threatening an enemy is based on various factors"""
    if not enemy.alive:
      return 0.0

    threat = 100.0  # Base threat level for any enemy

    # Distance to our territory border
    min_border_dist = float('inf')
    for x in range(self.map.width):
      for y in range(self.map.height):
        if self.is_in_our_territory(Position(x, y)):
          dist = self.manhattan_distance(enemy.position, Position(x, y))
          min_border_dist = min(min_border_dist, dist)

    # Higher threat when closer to border
    distance_factor = max(0.2, 1 - (min_border_dist * 0.1))
    threat *= distance_factor

    # Highest priority if already in our territory
    if self.is_in_our_territory(enemy.position):
      threat *= 5.0  # Massive threat increase for territory violation

    return threat

  def find_nearest_border_position(self, enemy_pos: Position) -> Optional[Position]:
    """Find the nearest border position to intercept an enemy"""
    best_pos = None
    min_score = float('inf')

    for x in range(self.map.width):
      for y in range(self.map.height):
        pos = Position(x, y)

        if not self.is_in_our_territory(pos):
          continue

        # Check if it's a border position
        is_border = any(
          not self.is_in_our_territory(Position(x + dx, y + dy))
          for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]
          if self.is_valid_position(x + dx, y + dy)
        )

        if not is_border:
          continue

        # Score based on distances
        dist_to_enemy = self.manhattan_distance(pos, enemy_pos)
        dist_to_self = self.manhattan_distance(pos, self.position)

        # We want to be close to enemy but also consider our distance
        score = dist_to_enemy + (dist_to_self * 0.5)

        if score < min_score:
          min_score = score
          best_pos = pos

    return best_pos

  def update_target(self):
    """Update target selection based on threats and coordination"""
    # Remove stale targets
    self._targets = {
      enemy_id: target for enemy_id, target in self._targets.items()
      if any(e.id == enemy_id and e.alive for e in self.enemies)
    }

    # Check if current target is still valid
    if self.current_target:
      target_id = self.current_target.enemy.id
      if (target_id in self._targets and
              self._targets[target_id].defender_id == self.car_id):
        # Update existing target
        enemy = next(e for e in self.enemies if e.id == target_id)
        self.current_target = Target(
          enemy=enemy,
          defender_id=self.car_id,
          threat_level=self.calculate_threat_level(enemy)
        )
        self._targets[target_id] = self.current_target
        return

    # Find new target
    available_enemies = [
      (enemy, self.calculate_threat_level(enemy))
      for enemy in self.enemies
      if enemy.alive
    ]

    # Sort by threat level
    available_enemies.sort(key=lambda x: x[1], reverse=True)

    # Try to find untargeted threat
    for enemy, threat in available_enemies:
      if threat > 0 and (
              enemy.id not in self._targets or
              self._targets[enemy.id].defender_id == self.car_id
      ):
        self.current_target = Target(
          enemy=enemy,
          defender_id=self.car_id,
          threat_level=threat
        )
        self._targets[enemy.id] = self.current_target
        return

    self.current_target = None

  def get_next_move(self, target_pos: Position) -> Optional[Action]:
    """Get next move towards target while staying in territory"""
    if not target_pos:
      return None

    best_direction = None
    min_distance = float('inf')

    moves = [
      ((0, 1), lambda cid: MoveDownAction(characterId=cid)),
      ((0, -1), lambda cid: MoveUpAction(characterId=cid)),
      ((1, 0), lambda cid: MoveRightAction(characterId=cid)),
      ((-1, 0), lambda cid: MoveLeftAction(characterId=cid))
    ]

    for (dx, dy), action_creator in moves:
      new_x = self.position.x + dx
      new_y = self.position.y + dy

      if not self.is_valid_position(new_x, new_y):
        continue

      # Stay in our territory unless chasing
      if not self.is_in_our_territory(Position(new_x, new_y)):
        continue

      new_pos = Position(new_x, new_y)
      new_distance = self.manhattan_distance(new_pos, target_pos)

      # Prefer positions that lead to interception
      will_intercept = any(
        self.manhattan_distance(new_pos, e.position) <= 1
        for e in self.enemies
        if e.alive
      )
      if will_intercept:
        new_distance -= 2

      if new_distance < min_distance:
        min_distance = new_distance
        best_direction = action_creator

    return best_direction(self.car_id) if best_direction else None

  def find_patrol_position(self) -> Optional[Position]:
    """Find good position to patrol when no active threats"""
    best_score = float('-inf')
    best_pos = None

    for x in range(self.map.width):
      for y in range(self.map.height):
        if not self.is_valid_position(x, y):
          continue

        pos = Position(x, y)
        if not self.is_in_our_territory(pos):
          continue

        score = 0

        # Prefer border positions
        is_border = any(
          not self.is_in_our_territory(Position(x + dx, y + dy))
          for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]
          if self.is_valid_position(x + dx, y + dy)
        )
        if is_border:
          score += 10

        # Consider territory coverage
        coverage = sum(
          1 for dx in range(-2, 3)
          for dy in range(-2, 3)
          if self.is_valid_position(x + dx, y + dy) and
          self.is_in_our_territory(Position(x + dx, y + dy))
        )
        score += coverage * 0.5

        if score > best_score:
          best_score = score
          best_pos = pos

    return best_pos

  def is_border_position(self, position: Position) -> bool:
    """Check if a position is on our territory border"""
    if not self.is_in_our_territory(position):
      return False

    return any(
      not self.is_in_our_territory(Position(position.x + dx, position.y + dy))
      for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]
      if self.is_valid_position(position.x + dx, position.y + dy)
    )

  def is_position_empty(self, position: Position) -> bool:
    """Check if a position has no items on it"""
    return not any(item.position.x == position.x and item.position.y == position.y
                   for item in self.all_items)

  def find_nearest_drop_position(self) -> Optional[Position]:
    """Find nearest empty enemy territory position to drop items"""
    best_pos = None
    min_dist = float('inf')

    # Check border of our territory for drop points
    for x in range(self.map.width):
      for y in range(self.map.height):
        pos = Position(x, y)
        if self.is_in_our_territory(pos):
          continue

        # Must be an empty, valid position
        if not self.is_valid_position(x, y) or not self.is_position_empty(pos):
          continue

        # Must be adjacent to our territory
        if not any(
                self.is_in_our_territory(Position(x + dx, y + dy))
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]
                if self.is_valid_position(x + dx, y + dy)
        ):
          continue

        dist = self.manhattan_distance(self.position, pos)
        if dist < min_dist:
          min_dist = dist
          best_pos = pos

    return best_pos

  def is_safe_to_clean_radiant(self) -> bool:
    """Check if it's safe to pick up radiant items"""
    # Don't clean if we're carrying anything
    if len(self.items) > 0:
      return False

    # Check if any enemies are too close
    for enemy in self.enemies:
      if not enemy.alive:
        continue
      if self.manhattan_distance(self.position, enemy.position) <= 3:
        return False
    return True

  def find_nearby_radiant(self) -> Optional[Tuple[Position, Position]]:
    """Find nearby radiant item and position to drop it in enemy territory"""
    if not self.is_safe_to_clean_radiant():
      return None

    # Find nearest radiant item in our territory
    best_item_pos = None
    min_item_dist = float('inf')

    for item in self.all_items:
      if item.value < 0 and self.is_in_our_territory(item.position):
        dist = self.manhattan_distance(self.position, item.position)
        if dist < min_item_dist and dist <= 3:  # Only consider nearby items
          min_item_dist = dist
          best_item_pos = item.position

    if not best_item_pos:
      return None

    # Find nearest drop position
    drop_pos = self.find_nearest_drop_position()
    if not drop_pos:
      return None

    # Only clean if total distance is reasonable
    total_dist = min_item_dist + self.manhattan_distance(best_item_pos, drop_pos)
    if total_dist > 6:  # Don't go too far from patrol
      return None

    return (best_item_pos, drop_pos)

  def get_action(self) -> Optional[Action]:
    """Determine next action based on current situation"""
    # Update targeting
    self.update_target()

    if self.current_target:
      enemy = self.current_target.enemy

      # If enemy in territory, chase aggressively
      if self.is_in_our_territory(enemy.position):
        if self.manhattan_distance(self.position, enemy.position) <= 1:
          return None  # Already adjacent for kill
        return self.get_next_move(enemy.position)

      # If we're at a good border position, consider staying put or cleaning radiant
      if self.is_border_position(self.position):
        # Check if our current position is a good intercept point
        dist_to_enemy = self.manhattan_distance(self.position, enemy.position)
        best_intercept = self.find_nearest_border_position(enemy.position)

        if best_intercept:
          best_dist = self.manhattan_distance(best_intercept, enemy.position)
          is_good_position = dist_to_enemy <= best_dist + 1

          if is_good_position:
            # Consider cleaning radiant if we're in a good spot
            cleanup_info = self.find_nearby_radiant()
            if cleanup_info:
              item_pos, drop_pos = cleanup_info
              if len(self.items) > 0:  # If carrying item
                if self.manhattan_distance(self.position, drop_pos) <= 1:
                  return DropAction(characterId=self.car_id)
                return self.get_next_move(drop_pos)
              return self.get_next_move(item_pos)
            return None

      # Otherwise get to border for interception
      intercept_pos = self.find_nearest_border_position(enemy.position)
      if intercept_pos:
        return self.get_next_move(intercept_pos)

    # No target - consider cleaning radiant
    cleanup_info = self.find_nearby_radiant()
    if cleanup_info:
      item_pos, drop_pos = cleanup_info
      if len(self.items) > 0:  # If carrying item
        if self.manhattan_distance(self.position, drop_pos) <= 1:
          return DropAction(characterId=self.car_id)
        return self.get_next_move(drop_pos)
      return self.get_next_move(item_pos)

    # Just patrol
    if self.is_border_position(self.position):
      return None  # Stay at border if already there
    return self.get_next_move(self.find_patrol_position())