from game_message import Character, Position, Item, TeamGameState, GameMap, MoveDownAction, MoveUpAction, \
  MoveRightAction, MoveLeftAction, Action, DropAction
from typing import List, Optional, Tuple

class Defender:
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

  def is_valid_position(self, x: int, y: int) -> bool:
    """Check if a position is valid (in bounds and not a wall)"""
    if not (0 <= y < self.map.height and 0 <= x < self.map.width):
      return False
    return self.map.tiles[y][x] != "WALL"

  def is_in_our_territory(self, position: Position) -> bool:
    """Check if a position is in our territory"""
    return self.team_zone[position.y][position.x] == self.team_id

  def should_intercept(self, enemy: Character) -> bool:
    """Determine if we should intercept this enemy"""
    if not self.alive or not enemy.alive:
      return False


    # Must be in our territory
    if not self.is_in_our_territory(self.position):
      return False

    # If enemy is near our territory and carrying items
    if self.manhattan_distance(self.position, enemy.position) <= 2:
      return enemy.numberOfCarriedItems > 0

    return False

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

    for y in range(self.map.height):
      for x in range(self.map.width):
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
          1 for dy in range(-2, 3)
          for dx in range(-2, 3)
          if (0 <= y + dy < self.map.height and
              0 <= x + dx < self.map.width and
              self.is_in_our_territory(Position(x + dx, y + dy)))
        )
        score += territory_bonus * 0.5

        if score > best_score:
          best_score = score
          best_position = current_pos

    return best_position

  def get_next_move(self, target_pos: Position)-> Optional[Action]:
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

  def get_nearest_enemy_with_items(self) -> Optional[Character]:
    """Find the nearest enemy carrying items"""
    nearest_enemy = None
    min_distance = float('inf')

    for enemy in self.enemies:
      if enemy.alive and enemy.numberOfCarriedItems > 0:
        dist = self.manhattan_distance(self.position, enemy.position)
        if dist < min_distance:
          min_distance = dist
          nearest_enemy = enemy

    return nearest_enemy

  @staticmethod
  def manhattan_distance(pos1: Position, pos2: Position) -> int:
    """Calculate Manhattan distance between two positions"""
    return abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y)

  def get_action(self) -> Optional[Action]:
    """Get the next action for this defender"""
    # First check if we need to drop items
    if self.should_drop_items():
      return DropAction(characterId=self.car_id)

    # Check if there's a nearby enemy we should intercept
    nearest_enemy = self.get_nearest_enemy_with_items()
    if nearest_enemy and self.should_intercept(nearest_enemy):
      # If we're already adjacent, no need to move
      if self.manhattan_distance(self.position, nearest_enemy.position) <= 1:
        return None  # Interception happens automatically
      # Otherwise, move towards enemy
      return self.get_next_move(nearest_enemy.position)

    # If no immediate threats, patrol our territory
    patrol_position = self.find_patrol_position()
    return self.get_next_move(patrol_position)