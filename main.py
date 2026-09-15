import sys
import arcade

from constants import *
from gameview import GameView
from map import InvalidMapFileException
from world_builder import WorldBuilder

def main() -> None:
    map_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MAP_FILE

    try:
        world = WorldBuilder.build_from_file(map_file)
    except InvalidMapFileException as e:
        print(f"Erreur lors du chargement de la carte : {e}")
        sys.exit(1)

    game_map = world.game_map
    game_width = min(MAX_WINDOW_WIDTH, game_map.width * TILE_SIZE)
    game_height = min(MAX_WINDOW_HEIGHT, game_map.height * TILE_SIZE)

    window = arcade.Window(game_width, game_height, WINDOW_TITLE)
    game_view = GameView(world, map_file)
    window.show_view(game_view)
    arcade.run()

if __name__ == "__main__":
    main()
