from bot import Bot
import random
from game_message import *

class MyBot(Bot):
    def __init__(self):
        super().__init__()

    def get_next_move(self, game_message: TeamGameState):
        """
        Here is where the magic happens, for now the moves are not very good. I bet you can do better ;)
        """
        actions = []
        game_message.print()
        for character in game_message.yourCharacters:
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
        # You can clearly do better than the random actions above! Have fun!
        return actions
if __name__ == "__main__":
    bot = MyBot()
