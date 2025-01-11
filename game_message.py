from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from enum import Enum, unique
from typing import Optional


@unique
class TileType(str, Enum):
    """Type of the tile on the map."""

    EMPTY = ("EMPTY",)
    WALL = ("WALL",)


@dataclass_json
@dataclass
class Constants:
    """Game constants. These will never change during the game."""

    respawnCooldownTicks: int
    """Number of ticks before a character respawns after dying."""
    maxNumberOfItemsCarriedPerCharacter: int
    """Maximum number of items that a character can carry."""


@dataclass_json
@dataclass
class Position:
    """A two-dimensional point on the map."""

    x: int
    """X coordinate of the position. 0 is the column on the left."""
    y: int
    """Y coordinate of the position. 0 is the top row."""


@dataclass_json
@dataclass
class Item:
    """An item on the map that you can pick up."""

    position: Position
    """Position of the item on the map. If carried by a character, this is the position where it was picked up."""
    type: str
    """Type of the item. Can be one of: blitzium_nugget, blitzium_ingot, blitzium_core, radiant_slag, radiant_core"""
    value: int
    """Points value of the item."""


@dataclass_json
@dataclass
class Character:
    """Character in the game."""

    id: str
    """Unique identifier of the character."""
    teamId: str
    """Team identifier of the character."""
    position: Position
    """Position of the character."""
    alive: bool
    """Indicates if the character is alive."""
    carriedItems: list[Item]
    """Items carried by the character."""
    numberOfCarriedItems: int
    """Number of items currently carried by the character."""


@dataclass_json
@dataclass
class GameMap:
    """The game map."""

    width: int
    """Width of the map."""
    height: int
    """Height of the map."""
    tiles: list[list[TileType]]
    """The map tiles."""


@dataclass_json
@dataclass
class TeamGameState:
    """State of the game for a specific team."""

    type: str
    tick: int
    """Current tick number."""
    currentTeamId: str
    """Your team id."""
    currentTickNumber: int
    """Current tick number."""
    lastTickErrors: list[str]
    """Errors that happened during the last tick."""
    constants: Constants
    """Game constants."""
    teamZoneGrid: list[list[str]]
    """For each cell, the id of the team that owns it."""
    yourCharacters: list[Character]
    """List of all the characters that belong to your team."""
    otherCharacters: list[Character]
    """List of all the characters that belong to other teams."""
    teamIds: list[str]
    """List of all the teams currently playing."""
    map: GameMap
    """The loaded game map. This map will never change during the game."""
    items: list[Item]
    """List of all the items on the map right now. This does not include items carried by characters."""
    score: dict[str, int]
    """Current score of each team."""


class Action:
    type: str


@dataclass_json
@dataclass
class MoveLeftAction(Action):
    """Move the character to the left (X-)."""

    characterId: str
    """Character id of the character that will move."""
    type: str = "MOVE_LEFT"


@dataclass_json
@dataclass
class MoveRightAction(Action):
    """Move the character to the right (X+)."""

    characterId: str
    """Character id of the character that will move."""
    type: str = "MOVE_RIGHT"


@dataclass_json
@dataclass
class MoveUpAction(Action):
    """Move the character up (Y-)."""

    characterId: str
    """Character id of the character that will move."""
    type: str = "MOVE_UP"


@dataclass_json
@dataclass
class MoveDownAction(Action):
    """Move the character down (Y+)."""

    characterId: str
    """Character id of the character that will move"""
    type: str = "MOVE_DOWN"


@dataclass_json
@dataclass
class MoveToAction(Action):
    """Move the character to the specified position using the shortest path possible. Does nothing if the position is unreachable."""

    characterId: str
    """Character id of the character that will move."""
    position: Position
    """Position to move to."""
    type: str = "MOVE_TO"


@dataclass_json
@dataclass
class GrabAction(Action):
    """Grab the item at the character's position."""

    characterId: str
    """Character id of the character that will grab the item."""
    type: str = "GRAB"


@dataclass_json
@dataclass
class DropAction(Action):
    """Drop the item at the character's position."""

    characterId: str
    """Character id of the character that will drop the item."""
    type: str = "DROP"


@dataclass_json
@dataclass
class SetSkinAction(Action):
    """Set a skin on the character. This is only cosmetic and does not affect the game."""

    characterId: str
    """Character id of the character whose's skin will be changed."""
    skinIndex: int
    """Index of the skin to use. This is an integer between 0 and 5."""
    type: str = "SET_SKIN"
