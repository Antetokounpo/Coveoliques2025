from game_message import Character, Position, Item, TeamGameState, GameMap, MoveLeftAction, MoveRightAction, \
  MoveUpAction, MoveDownAction, Action, DropAction
from typing import List, Optional, Tuple, Dict

class Target:
  """Represents a target for a defender."""
  __slots__ = ['enemy', 'defender_id', 'threat_level', 'last_seen_pos']  # Optimize memory usage

  def __init__(self, enemy: Character, defender_id: str, threat_level: float):
    """Initializes a Target object."""
    self.enemy = enemy
    self.defender_id = defender_id
    self.threat_level = threat_level
    self.last_seen_pos = enemy.position

class Defender:
  """Represents a defender character in the game."""
  _targets: Dict[str, Target] = {}  # Class-level tracking of targets
  _border_positions: Optional[List[Position]] = None  # Class-level, precomputed border positions

  def __init__(self, car: Character, game_state: TeamGameState):
    """Initializes a Defender object."""
    self.car_id = car.id
    self.position = car.position
    self.alive = car.alive
    self.items = car.carriedItems
    self.hasSpace = len(car.carriedItems) < game_state.constants.maxNumberOfItemsCarriedPerCharacter
    self.value = sum(item.value for item in car.carriedItems)

    self.team_id = game_state.currentTeamId
    self.team_zone = game_state.teamZoneGrid
    self.map = game_state.map
    self.tick = game_state.currentTickNumber
    self.enemies = game_state.otherCharacters
    self.allies = game_state.yourCharacters
    self.all_items = game_state.items

    # Precompute border positions once per tick for the first defender
    if self.allies and self.car_id == self.allies[0].id:
      Defender._targets.clear()
      Defender._border_positions = self._precompute_border_positions()

    self.current_target = None
    self._update_target()

  def _is_valid_position(self, x: int, y: int) -> bool:
    """Checks if the given coordinates are within the map boundaries and not a wall."""
    return 0 <= x < self.map.width and 0 <= y < self.map.height and self.map.tiles[x][y] != "WALL"

  def _is_in_our_territory(self, position: Position) -> bool:
    """Checks if the given position is within our team's territory."""
    return self.team_zone[position.x][position.y] == self.team_id

  @staticmethod
  def manhattan_distance(pos1: Position, pos2: Position) -> int:
    """Calculates the Manhattan distance between two positions."""
    return abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y)

  def _calculate_threat_level(self, enemy: Character) -> float:
    """Calculates a threat level for the given enemy based on proximity to our territory."""
    if not enemy.alive:
      return 0.0

    threat = 100.0

    # Find the minimum Manhattan distance from the enemy to our territory border
    min_border_dist = float('inf')
    for border_pos in Defender._border_positions:
      min_border_dist = min(min_border_dist, Defender.manhattan_distance(enemy.position, border_pos))

    distance_factor = max(0.2, 1 - (min_border_dist * 0.1))
    threat *= distance_factor

    if self._is_in_our_territory(enemy.position):
      threat *= 5.0  # Significantly higher threat if inside our territory

    return threat

  def _precompute_border_positions(self) -> List[Position]:
    """Precomputes and returns a list of our territory's border positions."""
    border_positions = []
    for x in range(self.map.width):
      for y in range(self.map.height):
        pos = Position(x, y)
        if self._is_in_our_territory(pos):
          # Check if any adjacent position is outside our territory
          for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if self._is_valid_position(nx, ny) and not self._is_in_our_territory(Position(nx, ny)):
              border_positions.append(pos)
              break  # Add only once per border tile
    return border_positions

  def find_nearest_border_position(self, enemy_pos: Position) -> Optional[Position]:
    """Finds the nearest position on our territory border to the given enemy."""
    if not Defender._border_positions:
      return None

    best_pos = None
    min_score = float('inf')

    for border_pos in Defender._border_positions:
      dist_to_enemy = Defender.manhattan_distance(border_pos, enemy_pos)
      dist_to_self = Defender.manhattan_distance(border_pos, self.position)
      score = dist_to_enemy + (dist_to_self * 0.5)  # Score considers both distances
      if score < min_score:
        min_score = score
        best_pos = border_pos
    return best_pos

  def _update_target(self):
    """Updates the defender's current target based on threat levels."""
    # Remove targets of dead enemies
    live_enemy_ids = {enemy.id for enemy in self.enemies if enemy.alive}
    Defender._targets = {eid: target for eid, target in Defender._targets.items() if eid in live_enemy_ids}

    # Update existing target if still valid and assigned to this defender
    if self.current_target and self.current_target.enemy.id in Defender._targets and Defender._targets[self.current_target.enemy.id].defender_id == self.car_id:
      enemy = next((e for e in self.enemies if e.id == self.current_target.enemy.id), None)
      if enemy:
        self.current_target.enemy = enemy
        self.current_target.threat_level = self._calculate_threat_level(enemy)
        Defender._targets[enemy.id] = self.current_target
        return

    # Find new target based on threat level
    available_enemies = sorted(
      [(enemy, self._calculate_threat_level(enemy)) for enemy in self.enemies if enemy.alive],
      key=lambda item: item[1],
      reverse=True  # Sort by threat level descending
    )

    # Assign the highest threat enemy not already targeted (or targeted by this defender)
    for enemy, threat in available_enemies:
      if threat > 0 and (enemy.id not in Defender._targets or Defender._targets[enemy.id].defender_id == self.car_id):
        self.current_target = Target(enemy=enemy, defender_id=self.car_id, threat_level=threat)
        Defender._targets[enemy.id] = self.current_target
        return

    self.current_target = None  # No suitable target found

  def _get_next_move_towards(self, target_pos: Position) -> Optional[Action]:
    """Determines the next move action to move towards the target position."""
    if not target_pos:
      return None

    best_action = None
    min_distance = float('inf')
    current_x, current_y = self.position.x, self.position.y

    # Possible move directions and their corresponding actions
    moves = [
      ((0, 1), MoveDownAction),
      ((0, -1), MoveUpAction),
      ((1, 0), MoveRightAction),
      ((-1, 0), MoveLeftAction),
    ]

    enemy_positions = {e.position for e in self.enemies if e.alive}  # Set of live enemy positions for quick lookup

    for (dx, dy), ActionType in moves:
      new_x, new_y = current_x + dx, current_y + dy
      new_pos = Position(new_x, new_y)

      # Check if the new position is valid and within our territory
      if self._is_valid_position(new_x, new_y) and self._is_in_our_territory(new_pos):
        distance = Defender.manhattan_distance(new_pos, target_pos)
        if new_pos in enemy_positions:  # Prioritize moves that lead to interception
          distance -= 2

        if distance < min_distance:
          min_distance = distance
          best_action = ActionType(characterId=self.car_id)

    return best_action

  def find_patrol_position(self) -> Optional[Position]:
    """Finds a suitable position to patrol, prioritizing border positions."""
    if not Defender._border_positions:
      return None

    best_score = float('-inf')
    best_pos = None

    for pos in Defender._border_positions:
      score = 10  # Base score for being a border position
      # Consider territory coverage around the border position
      coverage = sum(1 for dx in range(-1, 2) for dy in range(-1, 2)
                     if self._is_valid_position(pos.x + dx, pos.y + dy) and self._is_in_our_territory(Position(pos.x + dx, pos.y + dy)))
      score += coverage * 0.1

      if score > best_score:
        best_score = score
        best_pos = pos
    return best_pos

  def _is_position_empty(self, position: Position) -> bool:
    """Checks if the given position is empty of items."""
    return not any(item.position == position for item in self.all_items)

  def find_nearest_drop_position(self) -> Optional[Position]:
    """Finds the nearest valid and empty position in enemy territory adjacent to our border."""
    best_pos = None
    min_dist = float('inf')

    # Iterate through our border positions and check adjacent enemy territory
    for border_pos in Defender._border_positions:
      for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        drop_x, drop_y = border_pos.x + dx, border_pos.y + dy
        drop_pos = Position(drop_x, drop_y)
        # Check if the drop position is valid, in enemy territory, and empty
        if self._is_valid_position(drop_x, drop_y) and not self._is_in_our_territory(drop_pos) and self._is_position_empty(drop_pos):
          dist = Defender.manhattan_distance(self.position, drop_pos)
          if dist < min_dist:
            min_dist = dist
            best_pos = drop_pos
    return best_pos

  def is_safe_to_clean_radiant(self) -> bool:
    """Checks if it's safe to pick up a radiant item (not carrying anything and no nearby enemies)."""
    if self.items:
      return False
    return not any(Defender.manhattan_distance(self.position, enemy.position) <= 3 and enemy.alive for enemy in self.enemies)

  def find_nearby_radiant_and_drop(self) -> Optional[Tuple[Position, Position]]:
    """Finds a nearby radiant item in our territory and a suitable drop position in enemy territory."""
    if not self.is_safe_to_clean_radiant():
      return None

    best_item_pos = None
    min_item_dist = float('inf')

    # Find the nearest radiant item in our territory within a reasonable range
    for item in self.all_items:
      if item.value < 0 and self._is_in_our_territory(item.position):
        dist = Defender.manhattan_distance(self.position, item.position)
        if dist < min_item_dist and dist <= 5:
          min_item_dist = dist
          best_item_pos = item.position

    if not best_item_pos:
      return None

    # Find the nearest suitable drop position
    drop_pos = self.find_nearest_drop_position()
    if not drop_pos:
      return None

    # Check if the total distance to clean and drop is reasonable
    total_dist = min_item_dist + Defender.manhattan_distance(best_item_pos, drop_pos)
    if total_dist > 8:
      return None

    return best_item_pos, drop_pos

  def get_action(self) -> Optional[Action]:
    """Determines the next action for the defender based on the current game state."""
    self._update_target()

    if self.current_target:
      enemy = self.current_target.enemy
      enemy_pos = enemy.position

      # If the enemy is in our territory, engage
      if self._is_in_our_territory(enemy_pos):
        if Defender.manhattan_distance(self.position, enemy_pos) <= 1:
          return None  # Already adjacent to the enemy
        return self._get_next_move_towards(enemy_pos)

      # If at a border position, consider intercepting or cleaning radiant
      if self.position in Defender._border_positions:
        best_intercept = self.find_nearest_border_position(enemy_pos)
        if best_intercept and Defender.manhattan_distance(self.position, enemy_pos) <= Defender.manhattan_distance(best_intercept, enemy_pos) + 1:
          cleanup_info = self.find_nearby_radiant_and_drop()
          if cleanup_info:
            item_pos, drop_pos = cleanup_info
            if self.items:
              if Defender.manhattan_distance(self.position, drop_pos) <= 1 and self._is_valid_position(drop_pos.x, drop_pos.y) and self._is_position_empty(drop_pos):
                return DropAction(characterId=self.car_id)
              return self._get_next_move_towards(drop_pos)
            return self._get_next_move_towards(item_pos)
          return None  # Hold position at the border

      # Move towards the nearest border position to intercept the enemy
      intercept_pos = self.find_nearest_border_position(enemy_pos)
      if intercept_pos:
        return self._get_next_move_towards(intercept_pos)

    # If no target, consider cleaning nearby radiant items
    cleanup_info = self.find_nearby_radiant_and_drop()
    if cleanup_info:
      item_pos, drop_pos = cleanup_info
      if self.items:
        # Drop the carried radiant item
        if Defender.manhattan_distance(self.position, drop_pos) <= 1 and self._is_valid_position(drop_pos.x, drop_pos.y) and self._is_position_empty(drop_pos):
          return DropAction(characterId=self.car_id)
        return self._get_next_move_towards(drop_pos)
      return self._get_next_move_towards(item_pos)

    # If no target and no radiant to clean, move to a patrol position
    return self._get_next_move_towards(self.find_patrol_position())