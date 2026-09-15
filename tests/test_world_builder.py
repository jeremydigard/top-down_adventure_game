from __future__ import annotations

from textwrap import dedent

import arcade
import pytest

from constants import SCALE
from helper import grid_to_pixels
from map import GridCell, InvalidMapFileException, Map
from world_builder import LoadedWorld, WorldBuilder


def make_map(*rows: tuple[GridCell, ...], player_start_x: int = 0, player_start_y: int = 0) -> Map:
    return Map(player_start_x, player_start_y, rows)


def map_from_string(raw: str) -> Map:
    return Map.from_string(dedent(raw))


def test_first_obstacle_finds_first_bush_in_direction() -> None:
    """
    Teste que first_obstacle trouve le premier obstacle dans une direction donnée
    """
    game_map = make_map((
        GridCell.BUISSON,
        GridCell.GRASS,
        GridCell.CRYSTAL,
        GridCell.BUISSON,
        GridCell.GRASS,
    ))

    assert WorldBuilder.first_obstacle(game_map, 2, 0, -1, 0) == (0, 0)
    assert WorldBuilder.first_obstacle(game_map, 2, 0, 1, 0) == (3, 0)


def test_first_obstacle_skips_non_obstacles_and_can_return_none() -> None:
    """
    Teste que first_obstacle ignore les non-obstacles et peut retourner None
    """
    game_map = make_map((
        GridCell.GRASS,
        GridCell.CRYSTAL,
        GridCell.BAT,
        GridCell.GRASS,
    ))

    assert WorldBuilder.first_obstacle(game_map, 0, 0, 1, 0) is None


def test_compute_spinner_bounds_horizontal() -> None:
    """
    Teste le calcul des limites d'un spinneur horizontal
    """
    game_map = make_map((
        GridCell.BUISSON,
        GridCell.GRASS,
        GridCell.CRYSTAL,
        GridCell.SPINNEUR_HORIZONTAL,
        GridCell.BAT,
        GridCell.GRASS,
        GridCell.BUISSON,
    ))

    assert WorldBuilder.compute_spinner_bounds(game_map, 3, 0, horizontal=True) == (1, 5)


def test_compute_spinner_bounds_vertical() -> None:
    """
    Teste le calcul des limites d'un spinneur vertical
    """
    game_map = make_map(
        (GridCell.BUISSON,),
        (GridCell.GRASS,),
        (GridCell.BLOB,),
        (GridCell.SPINNEUR_VERTICAL,),
        (GridCell.CRYSTAL,),
        (GridCell.GRASS,),
        (GridCell.BUISSON,),
    )

    assert WorldBuilder.compute_spinner_bounds(game_map, 0, 3, horizontal=False) == (1, 5)


def test_compute_spinner_bounds_raises_when_one_side_is_open() -> None:
    """
    Teste que compute_spinner_bounds lève une exception si un côté est ouvert
    """
    game_map = make_map((
        GridCell.BUISSON,
        GridCell.GRASS,
        GridCell.SPINNEUR_HORIZONTAL,
        GridCell.GRASS,
        GridCell.GRASS,
    ))

    with pytest.raises(InvalidMapFileException):
        WorldBuilder.compute_spinner_bounds(game_map, 2, 0, horizontal=True)


def test_populate_map_bound_sprites_counts_basic_tiles() -> None:
    """
    Teste que _populate_map_bound_sprites compte correctement les tuiles de base
    """
    game_map = map_from_string("""\
        width: 3
        height: 2
        ---
        x*x
        xPx
        ---""")
    world = WorldBuilder.build_from_map(game_map)

    assert len(world.grounds) == 6
    assert len(world.walls) == 4
    assert len(world.crystals) == 1
    assert len(world.trou) == 0
    assert len(world.mobs) == 0
    assert len(world.levers) == 0
    assert len(world.closed_gates) == 0
    assert len(world.exits) == 0


def test_spawn_player_and_weapons_add_them_to_sprite_lists() -> None:
    """
    Teste que _spawn_player et _spawn_weapons ajoutent les éléments aux listes de sprites
    """
    game_map = map_from_string("""\
        width: 2
        height: 2
        ---
        xx
        xP
        ---""")
    player_list = arcade.SpriteList(use_spatial_hash=False)
    weapons = arcade.SpriteList(use_spatial_hash=True)

    player = WorldBuilder._spawn_player(player_list, game_map)
    boomerang, epee, weapon_controller = WorldBuilder._spawn_weapons(weapons)

    assert len(player_list) == 1
    assert len(weapons) == 2
    assert player_list[0] is player
    assert weapons[0] is boomerang.sprite
    assert weapons[1] is epee.sprite
    assert weapon_controller.active_weapon is boomerang
    assert player.center_x == grid_to_pixels(game_map.player_start_x)
    assert player.center_y == grid_to_pixels(game_map.player_start_y)
    assert player.scale[0] == pytest.approx(0.95 * SCALE)
    assert player.scale[1] == pytest.approx(0.95 * SCALE)


def test_build_from_string_returns_consistent_loaded_world() -> None:
    """
    Teste que build_from_string() retourne un LoadedWorld cohérent avec les bonnes propriétés
    """
    world = WorldBuilder.build_from_string(dedent("""\
        width: 2
        height: 2
        ---
        xx
        xP
        ---"""))

    assert isinstance(world, LoadedWorld)
    assert world.player is world.player_list[0]
    assert world.active_weapon is world.boomerang
    assert len(world.weapons) == 2
    assert world.player.center_x == grid_to_pixels(1)
    assert world.player.center_y == grid_to_pixels(0)
    assert world.boomerang.is_active is False
    assert world.epee.is_active is False


def test_switch_player_weapon_respects_active_weapon_state() -> None:
    """
    Teste que switch_player_weapon respecte l'état de l'arme active
    """
    world = WorldBuilder.build_from_string(dedent("""\
        width: 2
        height: 2
        ---
        xx
        xP
        ---"""))

    world.weapon_controller.switch_weapon()
    assert world.active_weapon is world.epee

    world.weapon_controller.use_active_weapon(world.weapon_context)
    world.weapon_controller.switch_weapon()
    assert world.active_weapon is world.epee

    list(world.weapon_controller.update_weapon(world.weapon_context, 0.3))
    world.weapon_controller.switch_weapon()
    assert world.active_weapon is world.boomerang
