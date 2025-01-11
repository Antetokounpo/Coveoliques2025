import random
from game_message import *
from collections import deque
from Defender import Defender
from CarrierV2 import Carrier
import astar

class MyBot:
    def __init__(self):
        self.clean_up_own_zone = True

    def clean_up(self, game_message: TeamGameState, character: Character, radian_to_grab: Item):
        pass 


    def get_next_move(self, game_message: TeamGameState):
        """
        Here is where the magic happens, for now the moves are not very good. I bet you can do better ;)
        """
        actions = []

        current_id = game_message.currentTeamId

        blitzium = deque() # blitzium dans la zone adverse
        radiant = deque() # radiant dans notre zone
        for item in game_message.items:
            item_pos = item.position
            if item.type.startswith("radiant") and game_message.teamZoneGrid[item_pos.x][item_pos.y] == current_id:
                radiant.append(item)
            elif item.type.startswith("blitzium") and game_message.teamZoneGrid[item_pos.x][item_pos.y] != current_id:
                blitzium.append(item)

        for character in game_message.yourCharacters:

            radiant_to_grab = None if not radiant else radiant.pop()

            if self.clean_up_own_zone:
                pass

            if character.position == radiant_to_grab.position:
                actions.append(GrabAction(characterId=character.id))
            else:
                actions.append(MoveToAction(characterId=character.id, position=radiant_to_grab.position))

        # You can clearly do better than the random actions above! Have fun!
        return actions


class DefenderBot:
    def __init__(self):
        pass

    def get_next_move(self, game_message: TeamGameState):
        actions = []
        one_defender = False

        print(len(game_message.map.tiles))
        print(game_message.map.width, game_message.map.height)

        for character in game_message.yourCharacters:
            if not one_defender:
                #one_defender = True
                defender = Defender(character, game_message)
                next_action = defender.get_action()
                if next_action is not None:
                    actions.append(next_action)
            else:
                actions.append(
                    random.choice(
                        [
                            MoveUpAction(characterId=character.id),
                            MoveRightAction(characterId=character.id),
                            MoveDownAction(characterId=character.id),
                            MoveLeftAction(characterId=character.id),
                            GrabAction(characterId=character.id),
                            DropAction(characterId=character.id),
                        ]
                    )
                )
        
        return actions

class HalfHalf:
    def __init__(self):
        self.inited = False
        self.bool_map = None

    def get_next_move(self, game_message: TeamGameState):
        if not self.inited:
            self.bool_map = astar.convert_to_bool_map(game_message)
            self.inited = True

        actions = []

        current_bool_map = self.bool_map.copy()
        astar.add_enemies_to_map(current_bool_map, game_message.otherCharacters) # inplace

        for i, character in enumerate(game_message.yourCharacters):
            GameRole = Defender if i % 2 == 1 else Carrier
            player = GameRole(character, game_message, current_bool_map)
            next_action = player.get_action()
            if next_action is not None:
                actions.append(next_action)
            
            if isinstance(next_action, DropAction):
                game_message.items.append(
                    Item(
                        position=player.position,
                        type=player.items[-1].type,
                        value=player.items[-1].value
                    )
                )
            #elif isinstance(next_action, GrabAction):
            #    picked_up_item = Item(
            #            position=player.position,
            #            type=game_message.items,
            #            value=player.items[-1].value
            #    )
            #    game_message.items.remove(picked_up_item)
 
        return actions

Bot = HalfHalf 