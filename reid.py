import random
from game_message import *
from collections import deque

class Bot:
    def __init__(self):
        print("Initializing your super mega duper bot")

    def get_next_move(self, game_message: TeamGameState):
        """
        Here is where the magic happens, for now the moves are not very good. I bet you can do better ;)
        """
        actions = []

        blitzium = deque()
        radiant = deque()
        for item in game_message.items:
            if item.type.startswith("blitzium"):
                blitzium.append(item)
            else:
                radiant.append(item)


        for character in game_message.yourCharacters:

            item_to_grab = blitzium.pop()

            if character.position == item_to_grab.position:
                actions.append(GrabAction(characterId=character.id))
            else:
                actions.append(MoveToAction(characterId=character.id, position=item_to_grab.position))

        # You can clearly do better than the random actions above! Have fun!
        return actions
