from game_message import Character, Position, Item, TeamGameState, GameMap, MoveLeftAction, MoveRightAction, \
  MoveUpAction, MoveDownAction, Action, DropAction
from typing import List, Optional, Tuple, Dict
from functools import lru_cache

class Target:
  __slots__ = ['enemy', 'defender_id', 'threat_level', 'last_seen_pos']

  def __init__(self, enemy: Character, defender_id: str, threat_level: float):
    self.enemy = enemy
    self.defender_id = defender_id
    self.threat_level = threat_level
    self.last_seen_pos = enemy.position

class Defender:
  _targets: Dict[str, Target] = {}
  _DIRECTIONS = [(0, 1), (0, -1), (1, 0), (-1, 0)]
  _MOVE_ACTIONS = {
    (0, 1): lambda cid: MoveDownAction(characterId=cid),
    (0, -1): lambda cid: MoveUpAction(characterId=cid),
    (1, 0): lambda cid: MoveRightAction(characterId=cid),
    (-1, 0): lambda cid: MoveLeftAction(characterId=cid)
  }

  def __init__(self, car: Character, game_state: TeamGameState):
    # Cache frequently accessed values
    self.car_id = car.id
    self.position = car.position
    self.alive = car.alive
    self.items = car.carriedItems
    self.hasSpace = car.numberOfCarriedItems < game_state.constants.maxNumberOfItemsCarriedPerCharacter
    self.value = sum(item.value for item in self.items)

    # Cache game state
    self.team_id = game_state.currentTeamId
    self.team_zone = game_state.teamZoneGrid
    self.map = game_state.map
    self.tick = game_state.currentTickNumber
    self.enemies = game_state.otherCharacters
    self.allies = game_state.yourCharacters

    # Pre-compute map dimensions
    self.width = self.map.width
    self.height = self.map.height

    # Pre-compute valid positions matrix
    self._valid_positions = self._precompute_valid_positions()

    # Reset targets at start of new tick
    if any(ally.id == self.allies[0].id for ally in self.allies):
      self._targets.clear()

    self.current_target = None
    self.update_target()

  def _precompute_valid_positions(self) -> List[List[bool]]:
    """Pre-compute valid positions matrix"""
    return [[
      self.map.tiles[x][y] != "WALL"
      for y in range(self.height)
    ] for x in range(self.width)]

  @lru_cache(maxsize=1024)
  def is_valid_position(self, x: int, y: int) -> bool:
    """Check if a position is valid (cached)"""
    if not (0 <= x < self.width and 0 <= y < self.height):
      return False
    return self._valid_positions[x][y]

  @lru_cache(maxsize=1024)
  def is_in_our_territory(self, x: int, y: int) -> bool:
    """Check if a position is in our territory (cached)"""
    return self.team_zone[x][y] == self.team_id

  @staticmethod
  def manhattan_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Optimized Manhattan distance calculation"""
    return abs(x1 - x2) + abs(y1 - y2)

  def calculate_threat_level(self, enemy: Character) -> float:
    """Calculate threat level with optimized territory checking"""
    if not enemy.alive:
      return 0.0

    threat = 100.0
    enemy_x, enemy_y = enemy.position.x, enemy.position.y

    # Check if already in territory (highest priority)
    if self.is_in_our_territory(enemy_x, enemy_y):
      return threat * 5.0

    # Find minimum border distance efficiently
    min_border_dist = float('inf')
    found_territory = False

    # Use dynamic programming approach for border distance
    for x in range(self.width):
      for y in range(self.height):
        if self.is_in_our_territory(x, y):
          found_territory = True
          dist = self.manhattan_distance(enemy_x, enemy_y, x, y)
          if dist < min_border_dist:
            min_border_dist = dist
            if min_border_dist <= 2:  # Early exit if very close
              return threat * 2.0

    if not found_territory:
      return 0.0

    distance_factor = max(0.2, 1 - (min_border_dist * 0.1))
    return threat * distance_factor

  def get_next_move(self, target_pos: Position) -> Optional[Action]:
    """Optimized pathfinding towards target"""
    if not target_pos:
      return None

    current_x, current_y = self.position.x, self.position.y
    target_x, target_y = target_pos.x, target_pos.y

    best_direction = None
    min_distance = float('inf')

    # Check all possible moves
    for dx, dy in self._DIRECTIONS:
      new_x, new_y = current_x + dx, current_y + dy

      if not self.is_valid_position(new_x, new_y):
        continue

      if not self.is_in_our_territory(new_x, new_y):
        continue

      new_distance = self.manhattan_distance(new_x, new_y, target_x, target_y)

      # Quick interception check
      for enemy in self.enemies:
        if enemy.alive and self.manhattan_distance(new_x, new_y, enemy.position.x, enemy.position.y) <= 1:
          new_distance -= 2
          break

      if new_distance < min_distance:
        min_distance = new_distance
        best_direction = (dx, dy)

    return self._MOVE_ACTIONS[best_direction](self.car_id) if best_direction else None

  def get_action(self) -> Optional[Action]:
    """Optimized main action decision logic"""
    self.update_target()

    if self.current_target:
      enemy = self.current_target.enemy
      enemy_pos = enemy.position

      # Quick adjacency check for kill
      if self.manhattan_distance(self.position.x, self.position.y, enemy_pos.x, enemy_pos.y) <= 1:
        return None

      # Handle enemy in territory
      if self.is_in_our_territory(enemy_pos.x, enemy_pos.y):
        return self.get_next_move(enemy_pos)

      # Efficient border position handling
      if self._is_good_border_position(self.position):
        cleanup_action = self._handle_cleanup()
        if cleanup_action:
          return cleanup_action
        return None

      # Get to border for interception
      intercept_pos = self._find_efficient_intercept(enemy_pos)
      if intercept_pos:
        return self.get_next_move(intercept_pos)

    # Handle cleanup and patrol
    cleanup_action = self._handle_cleanup()
    if cleanup_action:
      return cleanup_action

    if not self._is_good_border_position(self.position):
      return self.get_next_move(self._find_efficient_patrol_position())

    return None

  def _is_good_border_position(self, pos: Position) -> bool:
    """Efficient border position check"""
    if not self.is_in_our_territory(pos.x, pos.y):
      return False

    return any(
      not self.is_in_our_territory(pos.x + dx, pos.y + dy)
      for dx, dy in self._DIRECTIONS
      if self.is_valid_position(pos.x + dx, pos.y + dy)
    )

  def _find_efficient_intercept(self, enemy_pos: Position) -> Optional[Position]:
    """Find efficient interception position using gradient descent"""
    current_x, current_y = self.position.x, self.position.y

    # Start from current position and move towards border
    for _ in range(5):  # Limit iterations
      best_pos = None
      best_score = float('inf')

      for dx, dy in self._DIRECTIONS:
        new_x, new_y = current_x + dx, current_y + dy

        if not self.is_valid_position(new_x, new_y):
          continue

        if not self._is_good_border_position(Position(new_x, new_y)):
          continue

        score = self.manhattan_distance(new_x, new_y, enemy_pos.x, enemy_pos.y)

        if score < best_score:
          best_score = score
          best_pos = Position(new_x, new_y)

      if best_pos:
        return best_pos

    return None

  def is_position_empty(self, x: int, y: int) -> bool:
    """Check if a position has no items on it"""
    return not any(
      item.position.x == x and item.position.y == y
      for item in self.all_items
    )

  def _find_efficient_drop_position(self) -> Optional[Position]:
    """Find nearest valid empty position to drop items in enemy territory"""
    current_x, current_y = self.position.x, self.position.y
    best_pos = None
    min_dist = float('inf')

    # Search in expanding radius
    for radius in range(1, 6):  # Limit search radius
      for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
          x, y = current_x + dx, current_y + dy

          if not self.is_valid_position(x, y):
            continue

          # Must be in enemy territory - NEVER drop in our territory
          if self.is_in_our_territory(x, y):
            continue

          # Must be empty
          if not self.is_position_empty(x, y):
            continue

          # Should be adjacent to our territory for safe drops
          has_our_territory = any(
            self.is_in_our_territory(x + tdx, y + tdy)
            for tdx, tdy in self._DIRECTIONS
            if self.is_valid_position(x + tdx, y + tdy)
          )

          if not has_our_territory:
            continue

          dist = self.manhattan_distance(current_x, current_y, x, y)
          if dist < min_dist:
            min_dist = dist
            best_pos = Position(x, y)

      if best_pos:  # Found a valid position in current radius
        break

    return best_pos

  def _handle_cleanup(self) -> Optional[Action]:
    """Optimized cleanup handling with position validation"""
    if self.items:
      drop_pos = self._find_efficient_drop_position()
      if drop_pos:
        # Double check all conditions before dropping
        if (self.manhattan_distance(self.position.x, self.position.y, drop_pos.x, drop_pos.y) <= 1 and
                self.is_position_empty(drop_pos.x, drop_pos.y) and
                not self.is_in_our_territory(drop_pos.x, drop_pos.y)):  # Extra safety check
          return DropAction(characterId=self.car_id)
        return self.get_next_move(drop_pos)

    return None

  @lru_cache(maxsize=128)
  def _find_efficient_patrol_position(self) -> Optional[Position]:
    """Find efficient patrol position using territory coverage"""
    current_x, current_y = self.position.x, self.position.y

    best_pos = None
    best_score = -1

    # Search in expanding radius
    for radius in range(1, 4):
      for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
          x, y = current_x + dx, current_y + dy

          if not self.is_valid_position(x, y):
            continue

          if not self.is_in_our_territory(x, y):
            continue

          if self._is_good_border_position(Position(x, y)):
            score = 10 - self.manhattan_distance(current_x, current_y, x, y)

            if score > best_score:
              best_score = score
              best_pos = Position(x, y)

      if best_pos:
        return best_pos

    return Position(current_x, current_y)