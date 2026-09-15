from typing import Final

WINDOW_TITLE = "Adventure"
"""Title of the main window."""

SCALE = 2
"""The global scale for all textures."""

SECONDS_PER_FRAME: Final[float] = 1 / 60 


TILE_SIZE = 16 * SCALE
"""After scaling, the size of a tile."""

NAVMESH_NODES_N: Final[int] = 3
"""Number of navmesh nodes per tile, in one dimension."""

NAVMESH_BUCKET_SIZE: Final[int] = TILE_SIZE
"""Size in pixels of one bucket used to index navmesh nodes."""

PLAYER_MOVEMENT_SPEED = 4
"""Speed of the player, in pixels per frame."""

PLAYER_HEALTH = 22
"""Initial player health points."""

SPINNER_MOVEMENT_SPEED = 3
"""Speed of the spinners, in pixels per frame."""


BAT_MOVEMENT_SPEED = 3
"""Speed of the bats, in pixels per frame."""
BAT_PATROL_HALF_SIZE = 100
BAT_FRAMES_DIR_CHANGE = 10
BAT_DIRECTION_SIGMA = 0.8
BAT_RETURN_TO_CENTER_SIGMA = 0.25

BLOB_ACTION_RADIUS = 500
BLOB_MOVEMENT_SPEED = 1.5
BLOB_TARGET_RECOMPUTE_DISTANCE = TILE_SIZE / 2



BOOMERANG_MOVEMENT_SPEED = 8
"""Speed of the boomerang, in pixels per frame."""




MAX_WINDOW_WIDTH = 28 * TILE_SIZE #45
MAX_WINDOW_HEIGHT = 25 * TILE_SIZE #25

DEFAULT_MAP_FILE = "maps/map1.txt"

SWORD_FRAME_DURATION = 50
SWORD_FRAME_COUNT = 6
SWORD_R = 25 # SWORD REACH (IN PIXELS)
SWORD_ACTIVE_DURATION = SWORD_FRAME_COUNT * SWORD_FRAME_DURATION
SWORD_COOLDOWN = 10
EPEE_COOLDOWN = SWORD_COOLDOWN
BOOMERANG_COOLDOWN = 30
