from typing import Final
import arcade

ORIG_TILE_SIZE = (16, 16)

def _load_grid(
    file: str,
    columns: int,
    rows: int,
    tile_size: tuple[int, int] = ORIG_TILE_SIZE
) -> list[arcade.Texture]:
    """
    Loads a texture grid from a spritesheet.

    Args:
        file:
            Path to the spritesheet file name.
        columns:
            The number of columns in the grid.
        rows:
            The number of rows in the grid.
        tile_size (optional):
            The size in pixels of one element of the grid. Defaults to the
            standard tile size of `(16, 16)` that we use in our assets.

    Returns:
        A list of the loaded textures, flattened by row. The texture at grid
        coordinates `(x, y)` is at index `(y * columns) + x` in the list.
    """
    spritesheet = arcade.load_spritesheet(file)
    return spritesheet.get_texture_grid(tile_size, columns, columns * rows)

def _load_animation_strip(
    file: str,
    frame_count: int,
    frame_duration: int = 100,
    tile_size: tuple[int, int] = ORIG_TILE_SIZE,
) -> arcade.TextureAnimation:
    """
    Loads an animation strip from a line-oriented spritesheet.

    Args:
        file:
            Path to the spritesheet file name.
        frame_count:
            The number of frames in the animation, which should also be the
            number of sub-images in the file.
        frame_duration (optional):
            The duration of each frame in ms (defaults to 100).
        tile_size (optional):
            The size in pixels of one element of the grid, i.e.,  of a frame.
            Defaults to the standard tile size of `(16, 16)` that we use in our
            assets.

    Returns:
        An `arcade.TextureAnimation` representing the full animation.
    """
    grid = _load_grid(file, columns=frame_count, rows=1, tile_size=tile_size)
    keyframes = [arcade.TextureKeyframe(frame, frame_duration) for frame in grid]
    return arcade.TextureAnimation(keyframes)

_overworld_grid = _load_grid("assets/Top_Down_Adventure_Pack_v.1.0/Overworld_Tileset.png", 18, 13)

_dungeon_grid = _load_grid("assets/Top_Down_Adventure_Pack_v.1.0/Dungeon_Tileset.png", 13, 12)

# faudra redesgner tout cela parce que c bien laid, faut faire comme ce que j'ai fait l'épée avec le dico
TEXTURE_GRASS: Final[arcade.Texture] = _overworld_grid[18*1 + 6]

TEXTURE_BUSH: Final[arcade.Texture] = _overworld_grid[18*3 + 5]

# Petite pancarte: 8e tuile depuis la gauche, 4e depuis le haut du tileset overworld.
TEXTURE_SIGN: Final[arcade.Texture] = _overworld_grid[18*3 + 7]

LEVER_TEXTURES: Final[dict[bool,arcade.Texture]] = {
    True: arcade.load_texture(":resources:/images/tiles/leverLeft.png"), # on
    False: arcade.load_texture(":resources:/images/tiles/leverRight.png") # off
}

GATE_TEXTURES: Final[dict[bool,arcade.Texture]] = {
    True: _dungeon_grid[13*4 + 8], # open
    False: _dungeon_grid[13*7 + 8] # closed
}

HEALTH_BAR_TEXTURE: Final[arcade.Texture] = arcade.load_texture("assets/Top_Down_Adventure_Pack_v.1.0/Hud_Ui/health_bar_hud.png")

HEALTH_TEXTURE: Final[arcade.Texture] = arcade.load_texture("assets/Top_Down_Adventure_Pack_v.1.0/Hud_Ui/health_hud.png")

ANIMATION_PLAYER_IDLE_LEFT: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_idle_left_anim_strip_6.png", 6)

ANIMATION_PLAYER_IDLE_RIGHT: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_idle_right_anim_strip_6.png", 6)

ANIMATION_PLAYER_IDLE_UP: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_idle_up_anim_strip_6.png", 6)

ANIMATION_PLAYER_IDLE_DOWN: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_idle_down_anim_strip_6.png", 6)

ANIMATION_PLAYER_RUN_LEFT: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_run_left_anim_strip_6.png", 6)

ANIMATION_PLAYER_RUN_RIGHT: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_run_right_anim_strip_6.png", 6)

ANIMATION_PLAYER_RUN_UP: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_run_up_anim_strip_6.png", 6)

ANIMATION_PLAYER_RUN_DOWN: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_run_down_anim_strip_6.png", 6)


SPINNER_ANIMATION: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Enemies_Sprites/Spinner_Sprites/spinner_run_attack_anim_all_dir_strip_8.png", 3)

BAT_ANIMATION: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Enemies_Sprites/Pinkbat_Sprites/pinkbat_idle_left_anim_strip_5.png", 5)

BLOB_ANIMATION: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Enemies_Sprites/Pinkslime_Sprites/pinkslime_run_anim_anim_all_dir_strip_6.png", 6)

CRYSTAL_ANIMATION: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/Top_Down_Adventure_Pack_v.1.0/Props_Items_(animated)/crystal_item_anim_strip_6.png", 6)

CRYSTAL_SOUND = arcade.load_sound(":resources:sounds/coin5.wav")

DAMAGE_SOUND = arcade.load_sound(":resources:sounds/hurt2.wav")

BOOMERANG_ANIMATION: Final[arcade.TextureAnimation] = \
    _load_animation_strip("assets/provided/boomerang-sheet.png", 8, frame_duration=25)

TEXTURE_HOLE: Final[arcade.Texture] = _overworld_grid[18*4 + 8]


SWORD_ATTACK_ANIMATIONS: Final[dict[str, arcade.TextureAnimation]] = {
    "up": _load_animation_strip(
        "assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_attack48_up_anim_strip_6.png",
        frame_count=6, frame_duration=50, tile_size=(48, 48),
    ),
    "down": _load_animation_strip(
        "assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_attack48_down_anim_strip_6.png",
        frame_count=6, frame_duration=50, tile_size=(48, 48),
    ),
    "left": _load_animation_strip(
        "assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_attack48_left_anim_strip_6.png",
        frame_count=6, frame_duration=50, tile_size=(48, 48),
    ),
    "right": _load_animation_strip(
        "assets/Top_Down_Adventure_Pack_v.1.0/Char_Sprites/char_attack48_right_anim_strip_6.png",
        frame_count=6, frame_duration=50, tile_size=(48, 48),
    ),
}
