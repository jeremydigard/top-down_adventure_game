import arcade
import math
import pytest
import random
from textwrap import dedent
from pathlib import Path

from gameview import GameView
from constants import (
    BLOB_MOVEMENT_SPEED,
    PLAYER_HEALTH,
    SPINNER_MOVEMENT_SPEED,
    TILE_SIZE,
)
from helper import grid_to_pixels
from map import Map
from navmesh import build_navmesh, is_walkable
from monsters import Bat, Blob, compute_horizontal_bounds, compute_vertical_bounds


# ===================================================================
# Helpers
# ===================================================================

def _make_view(window: arcade.Window, tmp_path: Path, raw: str) -> GameView:
    map_file = tmp_path / "test_map.txt"
    map_file.write_text(dedent(raw))
    view = GameView.from_file(str(map_file))
    window.show_view(view)
    return view


def _make_map(raw: str) -> Map:
    return Map.from_string(dedent(raw))


def _vec_key(position: arcade.Vec2) -> tuple[float, float]:
    return (position.x, position.y)


class StraightLineNavMesh:
    """Navmesh minimal pour tester Blob sans dépendre de NetworkX."""

    path_calls: list[tuple[arcade.Vec2, arcade.Vec2]]

    def __init__(self) -> None:
        self.path_calls = []

    def path_between(self, source: arcade.Vec2, target: arcade.Vec2) -> list[arcade.Vec2]:
        self.path_calls.append((arcade.Vec2(source.x, source.y), arcade.Vec2(target.x, target.y)))
        return [arcade.Vec2(source.x, source.y), arcade.Vec2(target.x, target.y)]


# ===================================================================
# Tests SpinnerHorizontal
# ===================================================================


def test_spinner_bounds_stop_on_extended_static_obstacles() -> None:
    """
    Un trou limite la patrouille, contrairement aux entités non bloquantes
    testées plus bas.
    """
    game_map = _make_map("""\
        width: 7
        height: 3
        ---
        xxxxxxx
        xO s Ox
        xPxxxxx
        ---""")

    assert compute_horizontal_bounds(game_map, 3, 1) == (2, 4)


def test_spinner_horizontal_large_delta_stays_in_bounds(window: arcade.Window, tmp_path: Path) -> None:
    """
    Un pic de delta_time ne doit pas pousser le spinner dans le mur.

    Ce test reproduit le bug où les spinners semblaient parfois se coincer
    aléatoirement: si la SpriteList des mobs appelle l'update Arcade générique,
    le spinner avance une première fois avec change_x * delta_time * 60, puis
    update_monster le déplace une deuxième fois. Avec un delta_time élevé, le
    premier déplacement peut déjà dépasser la borne avant que notre logique de
    rebond ne soit exécutée.
    """
    view = _make_view(window, tmp_path, """\
        width: 5
        height: 3
        ---
        xxxxx
        xP sx
        xxxxx
        ---""")

    spinner = view.world.mobs[0]
    assert spinner.center_x == spinner.boundary_max

    view.on_update(0.1)

    assert spinner.center_x <= spinner.boundary_max


def test_gameview_does_not_call_generic_mob_update(
    window: arcade.Window,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GameView ne doit pas bouger les monstres via l'update générique Arcade.

    Une SpriteList Arcade sait appeler update() sur ses sprites. Le point
    important de notre architecture est donc de ne pas utiliser cette méthode
    générique dans GameView: les monstres passent par update_monster(), qui
    applique leurs règles métier et leurs bornes.
    """
    view = _make_view(window, tmp_path, """\
        width: 5
        height: 3
        ---
        xxxxx
        xP sx
        xxxxx
        ---""")

    spinner = view.world.mobs[0]

    def fail_generic_update(delta_time: float = 1 / 60, *args: object, **kwargs: object) -> None:
        raise AssertionError("GameView should call update_monster(), not Sprite.update().")

    monkeypatch.setattr(spinner, "update", fail_generic_update)

    view.on_update(0.1)

    assert spinner.center_x <= spinner.boundary_max



def test_spinner_horizontal_present_on_map(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 5
        height: 3
        ---
        xxxxx
        xs Px
        xxxxx
        ---""")

    assert len(view.world.mobs) == 1


def test_spinner_horizontal_moves_right(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 7
        height: 3
        ---
        xxxxxxx
        xs   Px
        xxxxxxx
        ---""")

    spinner = view.world.mobs[0]
    initial_x = spinner.center_x
    initial_y = spinner.center_y

    window.test(10)

    assert spinner.center_x != initial_x
    assert spinner.center_y == initial_y


def test_spinner_horizontal_bounces(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 5
        height: 3
        ---
        xxxxx
        xsPx
        xxxxx
        ---""")

    spinner = view.world.mobs[0]

    positions_x = []
    for _ in range(60):
        window.test(1)
        positions_x.append(spinner.center_x)

    min_x = min(positions_x)
    max_x = max(positions_x)
    assert min_x < max_x


def test_spinner_horizontal_bounds_ignore_non_obstacle_entities() -> None:
    """
    Les bornes d'un spinner dépendent des obstacles, pas des entités sur le sol.

    La consigne précise qu'un spinner n'est pas arrêté par les cristaux, les
    autres spinners ou le joueur. On applique la même logique aux monstres et
    leviers posés sur une case traversable.
    """
    game_map = _make_map("""\
        width: 11
        height: 3
        switches:
          - id: west
            x: 1
            y: 1
          - id: east
            x: 9
            y: 1
        ---
        xxxxxxxxxxx
        x^*svbS s^x
        xPxxxxxxxxx
        ---""")

    assert compute_horizontal_bounds(game_map, 8, 1) == (1, 9)


def test_spinner_horizontal_single_cell_corridor_does_not_enter_wall(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 5
        height: 3
        ---
        xxxxx
        xxsxx
        xPxxx
        ---""")

    spinner = view.world.mobs[0]
    assert spinner.boundary_min == spinner.boundary_max

    for _ in range(10):
        window.test(1)
        assert spinner.center_x == spinner.boundary_min
        assert not arcade.check_for_collision_with_list(spinner, view.world.walls)


def test_horizontal_spinner_contact_decreases_health(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 5
        height: 3
        ---
        xxxxx
        xPsxx
        xxxxx
        ---""")
    spinner = view.world.mobs[0]
    view.world.player.position = spinner.position

    view.on_update(1 / 60)

    assert window.current_view is view
    assert view.health == PLAYER_HEALTH - spinner.contact_damage


# ===================================================================
# Tests SpinnerVertical
# ===================================================================

def test_spinner_vertical_present_on_map(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 3
        height: 5
        ---
        xxx
        xSx
        x x
        xPx
        xxx
        ---""")

    assert len(view.world.mobs) == 1


def test_spinner_vertical_moves_up_down(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 3
        height: 7
        ---
        xxx
        xSx
        x x
        x x
        x x
        xPx
        xxx
        ---""")

    spinner = view.world.mobs[0]
    initial_x = spinner.center_x
    initial_y = spinner.center_y

    window.test(10)

    assert spinner.center_y != initial_y
    assert spinner.center_x == initial_x


def test_spinner_vertical_bounces(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 3
        height: 5
        ---
        xxx
        xSx
        x x
        xPx
        xxx
        ---""")

    spinner = view.world.mobs[0]

    positions_y = []
    for _ in range(60):
        window.test(1)
        positions_y.append(spinner.center_y)

    min_y = min(positions_y)
    max_y = max(positions_y)
    assert min_y < max_y


def test_spinner_vertical_stays_in_bounds(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 3
        height: 6
        ---
        xxx
        xSx
        x x
        x x
        xPx
        xxx
        ---""")

    spinner = view.world.mobs[0]
    bound_min = spinner.boundary_min
    bound_max = spinner.boundary_max

    for _ in range(200):
        window.test(1)
        assert spinner.center_y >= bound_min - SPINNER_MOVEMENT_SPEED
        assert spinner.center_y <= bound_max + SPINNER_MOVEMENT_SPEED


def test_spinner_vertical_single_cell_corridor_does_not_enter_wall(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 5
        height: 5
        ---
        xxxxx
        xxxxx
        xxSxx
        xxxxx
        xPxxx
        ---""")

    spinner = view.world.mobs[0]
    assert spinner.boundary_min == spinner.boundary_max

    for _ in range(10):
        window.test(1)
        assert spinner.center_y == spinner.boundary_min
        assert not arcade.check_for_collision_with_list(spinner, view.world.walls)


def test_vertical_spinner_contact_decreases_health(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 3
        height: 5
        ---
        xxx
        xSx
        xPx
        x x
        xxx
        ---""")
    spinner = view.world.mobs[0]
    view.world.player.position = spinner.position

    view.on_update(1 / 60)

    assert window.current_view is view
    assert view.health == PLAYER_HEALTH - spinner.contact_damage


# ===================================================================
# Tests pour plusieurs spinners
# ===================================================================

def test_multiple_spinners(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 7
        height: 5
        ---
        xxxxxxx
        xs   Px
        xxxxxxx
        xs   x
        xxxxxxx
        ---""")

    assert len(view.world.mobs) == 2


# ===================================================================
# Tests Bat
# ===================================================================

def test_bat_present_on_map(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 10
        height: 10
        ---
        xxxxxxxxxx
        x        x
        x        x
        x  v     x
        x        x
        x        x
        x        x
        x       Px
        x        x
        xxxxxxxxxx
        ---""")

    assert len(view.world.mobs) == 1


def test_bat_moves(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 10
        height: 10
        ---
        xxxxxxxxxx
        x        x
        x        x
        x  v     x
        x        x
        x        x
        x        x
        x       Px
        x        x
        xxxxxxxxxx
        ---""")

    bat = view.world.mobs[0]
    initial_x = bat.center_x
    initial_y = bat.center_y

    window.test(10)

    moved = (bat.center_x != initial_x) or (bat.center_y != initial_y)
    assert moved


def test_bat_stays_within_radius(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 15
        height: 15
        ---
        xxxxxxxxxxxxxxx
        x             x
        x             x
        x             x
        x             x
        x             x
        x             x
        x      v      x
        x             x
        x             x
        x             x
        x             x
        x             x
        x            Px
        xxxxxxxxxxxxxxx
        ---""")

    bat = view.world.mobs[0]
    initial_x = bat.center_x
    initial_y = bat.center_y
    max_allowed_radius = 200  # marge pour le rayon + un pas de mouvement

    for _ in range(300):
        window.test(1)
        distance = math.hypot(bat.center_x - initial_x, bat.center_y - initial_y)
        assert distance <= max_allowed_radius, (
            f"La chauve-souris a dépassé le rayon : {distance:.1f} > {max_allowed_radius}"
        )


def test_bat_clamps_patrol_area_to_world_edges(window: arcade.Window) -> None:
    """
    Une chauve-souris proche du bord ne doit pas patrouiller hors du monde.

    Ce cas est plus strict que le rayon: un rectangle de patrouille centré en
    (0, 0) doit être tronqué aux bornes [0, world_width] x [0, world_height].
    """
    bat = Bat(
        center_x=grid_to_pixels(0),
        center_y=grid_to_pixels(0),
        world_width=TILE_SIZE,
        world_height=TILE_SIZE,
        rng=random.Random(0),
    )

    for _ in range(200):
        bat.update_monster(1 / 60, (0, 0))
        assert 0 <= bat.center_x <= TILE_SIZE
        assert 0 <= bat.center_y <= TILE_SIZE


def test_bat_player_collision(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 10
        height: 10
        ---
        xxxxxxxxxx
        x        x
        x        x
        x        x
        x Pv     x
        x        x
        x        x
        x        x
        x        x
        xxxxxxxxxx
        ---""")

    view.on_key_press(arcade.key.RIGHT, 0)
    window.test(60)

    assert view.health < PLAYER_HEALTH


def test_bat_and_spinner_coexist(window: arcade.Window, tmp_path: Path) -> None:
    view = _make_view(window, tmp_path, """\
        width: 10
        height: 10
        ---
        xxxxxxxxxx
        xs       x
        x        x
        x  v     x
        x        x
        x        x
        x        x
        x       Px
        x        x
        xxxxxxxxxx
        ---""")

    assert len(view.world.mobs) == 2


# ===================================================================
# Tests Blob
# ===================================================================

def test_blob_rejects_empty_patrol_destinations(window: arcade.Window) -> None:
    """
    Le constructeur refuse explicitement un blob qui n'aurait aucun endroit où
    patrouiller.
    """
    with pytest.raises(ValueError):
        Blob(
            origine=arcade.Vec2(0, 0),
            navmesh=StraightLineNavMesh(),
            possible_destinations=(),
            sight_radius=100,
            vision_blockers=arcade.SpriteList(),
        )


def test_blob_rejects_non_positive_sight_radius(window: arcade.Window) -> None:
    with pytest.raises(ValueError):
        Blob(
            origine=arcade.Vec2(0, 0),
            navmesh=StraightLineNavMesh(),
            possible_destinations=(arcade.Vec2(0, 0),),
            sight_radius=0,
            vision_blockers=arcade.SpriteList(),
        )


def test_blob_constructor_does_not_reuse_vec2_arguments(window: arcade.Window) -> None:
    """
    Le Blob recopie les positions reçues avant de les transmettre au navmesh.
    """
    origin = arcade.Vec2(0, 0)
    destination = arcade.Vec2(10, 0)
    mesh = StraightLineNavMesh()
    blob = Blob(
        origine=origin,
        navmesh=mesh,
        possible_destinations=(destination,),
        sight_radius=100,
        vision_blockers=arcade.SpriteList(),
        rng=random.Random(0),
    )

    blob.update_monster(1 / 60, (1_000, 1_000))

    first_source, first_target = mesh.path_calls[0]
    assert first_source is not origin
    assert first_target is not destination
    assert _vec_key(first_source) == _vec_key(origin)
    assert _vec_key(first_target) == _vec_key(destination)
    assert blob.center_x == pytest.approx(BLOB_MOVEMENT_SPEED)
    assert blob.center_y == pytest.approx(0)


def test_blob_patrol_destinations_filter_unreachable_cells() -> None:
    """
    Une case d'herbe séparée par une colonne de trous est praticable localement,
    mais pas atteignable depuis le blob.
    """
    game_map = _make_map("""\
        width: 5
        height: 5
        ---
        xxxxx
        x O x
        xbO x
        xPO x
        xxxxx
        ---""")
    mesh = build_navmesh(game_map)

    destinations = Blob.patrol_destinations(
        game_map,
        origin_x=1,
        origin_y=2,
        is_walkable_for_blob=is_walkable,
        navmesh=mesh,
        radius_cells=3,
    )
    destination_keys = {_vec_key(destination) for destination in destinations}

    assert (grid_to_pixels(1), grid_to_pixels(1)) in destination_keys
    assert (grid_to_pixels(3), grid_to_pixels(2)) not in destination_keys
