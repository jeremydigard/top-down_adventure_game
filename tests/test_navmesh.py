from importlib import import_module
from enum import Enum, auto

import arcade
import pytest

import navmesh
from constants import NAVMESH_NODES_N, TILE_SIZE
from helper import grid_to_pixels


class Cell(Enum):
    """Minimal cell type used to test navmesh.py without importing map.py."""

    GRASS = auto()
    WALL = auto()
    HOLE = auto()
    GATE = auto()
    BLOB = auto()

    @property
    def is_blob_nav_obstacle(self) -> bool:
        return self in {Cell.WALL, Cell.HOLE, Cell.GATE}

    @property
    def is_player_obstacle(self) -> bool:
        return self in {Cell.WALL, Cell.GATE}


class FakeMap:
    width: int
    height: int
    __rows: tuple[tuple[Cell, ...], ...]

    def __init__(self, rows: tuple[tuple[Cell, ...], ...]) -> None:
        self.__rows = rows
        self.height = len(rows)
        self.width = len(rows[0])

    def get(self, x: int, y: int) -> Cell:
        return self.__rows[y][x]


class EmptyMap:
    width = 0
    height = 0

    def get(self, x: int, y: int) -> Cell:
        raise ValueError("Empty map has no cells.")


def make_map(*rows: tuple[Cell, ...]) -> FakeMap:
    return FakeMap(rows)


def pos(x: int, y: int) -> arcade.Vec2:
    return arcade.Vec2(grid_to_pixels(x), grid_to_pixels(y))


def assert_vec2_close(actual: arcade.Vec2, expected: arcade.Vec2) -> None:
    assert actual.x == pytest.approx(expected.x)
    assert actual.y == pytest.approx(expected.y)


def closest_position_def(navmesh_positions: tuple[arcade.Vec2, ...], position: arcade.Vec2) -> arcade.Vec2:
    """Définition naïve utilisée comme oracle pour tester l'indexation par buckets."""
    return min(navmesh_positions, key=lambda node_position: node_position.distance(position))


def path_length_def(path: list[arcade.Vec2]) -> float:
    """Définition directe de la longueur d'un chemin polygonal."""
    total = 0.0
    for index in range(len(path) - 1):
        previous = path[index]
        current = path[index + 1]
        total += previous.distance(current)
    return total


def assert_no_consecutive_duplicates(path: list[arcade.Vec2]) -> None:
    for index in range(len(path) - 1):
        previous = path[index]
        current = path[index + 1]
        assert previous.distance(current) > 0


def assert_all_path_points_inside_map(path: list[arcade.Vec2], game_map: FakeMap) -> None:
    for point in path:
        assert 0 <= point.x <= game_map.width * TILE_SIZE
        assert 0 <= point.y <= game_map.height * TILE_SIZE


def assert_all_positions_far_enough_from(position: arcade.Vec2, positions: tuple[arcade.Vec2, ...]) -> None:
    for candidate in positions:
        assert candidate.distance(position) >= TILE_SIZE


def assert_all_positions_different_from(position: arcade.Vec2, positions: tuple[arcade.Vec2, ...]) -> None:
    for candidate in positions:
        assert candidate.distance(position) > 0


def assert_some_position_close_to(position: arcade.Vec2, positions: tuple[arcade.Vec2, ...]) -> None:
    found_close_position = False

    for candidate in positions:
        if candidate.distance(position) < TILE_SIZE:
            found_close_position = True

    assert found_close_position


def test_mesh_positions() -> None:
    first_inner_position = TILE_SIZE / (2 * NAVMESH_NODES_N)

    assert navmesh.mesh_index_to_pixels(0) == pytest.approx(first_inner_position)
    assert navmesh.mesh_index_to_pixels(1) == pytest.approx(3 * first_inner_position)
    assert navmesh.mesh_index_to_pixels(NAVMESH_NODES_N - 1) == pytest.approx(TILE_SIZE - first_inner_position)
    assert navmesh.mesh_index_to_pixels(NAVMESH_NODES_N) == pytest.approx(TILE_SIZE + first_inner_position)
    assert navmesh.mesh_index_to_pixels(2 * NAVMESH_NODES_N) == pytest.approx(2 * TILE_SIZE + first_inner_position)


def test_node_positions_are_defensive_copies() -> None:
    """External code must not be able to mutate the positions stored inside NavMesh."""
    mesh = navmesh.build_navmesh(make_map((Cell.GRASS,)))
    first_snapshot = mesh.node_positions()
    second_snapshot = mesh.node_positions()

    assert first_snapshot is not second_snapshot
    assert first_snapshot[0] is not second_snapshot[0]
    assert_vec2_close(first_snapshot[0], second_snapshot[0])


def test_walkable_predicate() -> None:
    game_map = make_map((Cell.GRASS, Cell.WALL, Cell.HOLE, Cell.GATE, Cell.BLOB))

    assert navmesh.is_walkable(game_map, 0, 0)
    assert not navmesh.is_walkable(game_map, 1, 0)
    assert not navmesh.is_walkable(game_map, 2, 0)
    assert not navmesh.is_walkable(game_map, 3, 0)
    assert navmesh.is_walkable(game_map, 4, 0)


def test_clearance_predicate() -> None:
    game_map = make_map((Cell.GRASS, Cell.WALL, Cell.HOLE, Cell.GATE, Cell.BLOB))

    assert not navmesh.is_wall_for_clearance(game_map, 0, 0)
    assert navmesh.is_wall_for_clearance(game_map, 1, 0)
    assert not navmesh.is_wall_for_clearance(game_map, 2, 0)
    assert navmesh.is_wall_for_clearance(game_map, 3, 0)
    assert not navmesh.is_wall_for_clearance(game_map, 4, 0)


def test_construction_counts() -> None:
    open_map = make_map((Cell.GRASS,))
    blocked_map = make_map((Cell.HOLE,))
    mixed_map = make_map((Cell.GRASS, Cell.HOLE))

    assert navmesh.build_navmesh(open_map).node_count == NAVMESH_NODES_N ** 2
    assert navmesh.build_navmesh(blocked_map).node_count == 0
    assert navmesh.build_navmesh(mixed_map).node_count == NAVMESH_NODES_N ** 2
    assert navmesh.build_navmesh(open_map).edge_count > 0
    assert navmesh.build_navmesh(blocked_map).edge_count == 0


def test_private_graph() -> None:
    mesh = navmesh.build_navmesh(make_map((Cell.GRASS, Cell.GRASS)))

    assert not hasattr(mesh, "graph") 
    assert not hasattr(mesh, "buckets")
    assert mesh.node_count > 0
    assert mesh.edge_count > 0


def test_closest_node() -> None:
    mesh = navmesh.build_navmesh(make_map(
        (Cell.GRASS, Cell.GRASS, Cell.GRASS),
        (Cell.GRASS, Cell.WALL, Cell.GRASS),
        (Cell.GRASS, Cell.GRASS, Cell.GRASS),
    ))
    positions = mesh.node_positions()

    for position in (
        arcade.Vec2(3.0, 4.0),
        arcade.Vec2(40.0, 17.0),
        arcade.Vec2(95.0, 95.0),
        arcade.Vec2(-10.0, 50.0),
        arcade.Vec2(500.0, 500.0),
    ):
        assert_vec2_close(mesh.closest_position(position), closest_position_def(positions, position))


def test_empty_mesh() -> None:
    mesh = navmesh.build_navmesh(make_map(
        (Cell.HOLE, Cell.HOLE),
        (Cell.HOLE, Cell.HOLE),
    ))

    assert mesh.node_count == 0
    assert mesh.edge_count == 0
    assert mesh.path_between(pos(0, 0), pos(1, 1)) is None
    assert not mesh.can_reach(pos(0, 0), pos(1, 1))

    with pytest.raises(ValueError):
        mesh.closest_node(pos(0, 0))


def test_empty_map_dimensions_raise() -> None:
    with pytest.raises(ValueError):
        navmesh.build_navmesh(EmptyMap())


def test_non_finite_positions_raise() -> None:
    mesh = navmesh.build_navmesh(make_map((Cell.GRASS,)))
    invalid_position = arcade.Vec2(float("nan"), 0)

    with pytest.raises(ValueError):
        mesh.closest_node(invalid_position)
    with pytest.raises(ValueError):
        mesh.can_reach(pos(0, 0), invalid_position)
    with pytest.raises(ValueError):
        mesh.path_between(pos(0, 0), invalid_position)


def test_obstacle_cells() -> None:
    mesh = navmesh.build_navmesh(make_map((Cell.GRASS, Cell.HOLE, Cell.GRASS)))
    hole_center = pos(1, 0)

    assert mesh.node_count == 2 * NAVMESH_NODES_N ** 2
    assert_all_positions_different_from(hole_center, mesh.node_positions())
    assert not mesh.can_reach(pos(0, 0), pos(2, 0))
    assert mesh.path_between(pos(0, 0), pos(2, 0)) is None


def test_wall_clearance() -> None:
    wall_map = make_map((Cell.GRASS, Cell.WALL, Cell.GRASS))
    hole_map = make_map((Cell.GRASS, Cell.HOLE, Cell.GRASS))
    gate_map = make_map((Cell.GRASS, Cell.GATE, Cell.GRASS))
    obstacle_center = pos(1, 0)

    wall_positions = navmesh.build_navmesh(wall_map).node_positions()
    hole_positions = navmesh.build_navmesh(hole_map).node_positions()
    gate_positions = navmesh.build_navmesh(gate_map).node_positions()

    assert_all_positions_far_enough_from(obstacle_center, wall_positions)
    assert_some_position_close_to(obstacle_center, hole_positions)
    assert_all_positions_far_enough_from(obstacle_center, gate_positions)


def test_corner_cutting() -> None:
    blocked_corner = navmesh.build_navmesh(make_map(
        (Cell.GRASS, Cell.HOLE),
        (Cell.HOLE, Cell.GRASS),
    ))
    open_corner = navmesh.build_navmesh(make_map(
        (Cell.GRASS, Cell.GRASS),
        (Cell.GRASS, Cell.GRASS),
    ))

    assert blocked_corner.path_between(pos(0, 0), pos(1, 1)) is None
    assert not blocked_corner.can_reach(pos(0, 0), pos(1, 1))
    assert open_corner.path_between(pos(0, 0), pos(1, 1)) is not None
    assert open_corner.can_reach(pos(0, 0), pos(1, 1))


def test_path_endpoints() -> None:
    source = arcade.Vec2(2.0, 7.0)
    target = arcade.Vec2(2 * TILE_SIZE + 13.0, 9.0)
    game_map = make_map((Cell.GRASS, Cell.GRASS, Cell.GRASS))
    mesh = navmesh.build_navmesh(game_map)

    path = mesh.path_between(source, target)

    assert path is not None
    assert_vec2_close(path[0], source)
    assert_vec2_close(path[-1], target)
    assert_no_consecutive_duplicates(path)
    assert_all_path_points_inside_map(path, game_map)


def test_shortest_path_weights() -> None:
    mesh = navmesh.build_navmesh(make_map(
        (Cell.GRASS, Cell.GRASS),
        (Cell.GRASS, Cell.GRASS),
    ))

    cardinal_path = mesh.path_between(pos(0, 0), pos(1, 0))
    diagonal_path = mesh.path_between(pos(0, 0), pos(1, 1))

    assert cardinal_path is not None
    assert diagonal_path is not None
    assert path_length_def(cardinal_path) == pytest.approx(TILE_SIZE)
    assert path_length_def(diagonal_path) == pytest.approx(TILE_SIZE * 2 ** 0.5)


def test_detour() -> None:
    game_map = make_map(
        (Cell.GRASS, Cell.GRASS, Cell.GRASS),
        (Cell.GRASS, Cell.HOLE, Cell.GRASS),
        (Cell.GRASS, Cell.GRASS, Cell.GRASS),
    )
    mesh = navmesh.build_navmesh(game_map)

    direct_path = mesh.path_between(pos(0, 1), pos(2, 1))
    top_path = mesh.path_between(pos(0, 2), pos(2, 2))

    assert direct_path is not None
    assert top_path is not None
    assert path_length_def(direct_path) > path_length_def(top_path)
    assert_no_consecutive_duplicates(direct_path)
    assert_all_path_points_inside_map(direct_path, game_map)


def test_reachability() -> None:
    connected = navmesh.build_navmesh(make_map(
        (Cell.GRASS, Cell.GRASS, Cell.GRASS),
        (Cell.GRASS, Cell.GRASS, Cell.GRASS),
    ))
    disconnected = navmesh.build_navmesh(make_map(
        (Cell.GRASS, Cell.HOLE, Cell.GRASS),
        (Cell.GRASS, Cell.HOLE, Cell.GRASS),
    ))

    assert connected.can_reach(pos(0, 0), pos(2, 1))
    assert connected.path_between(pos(0, 0), pos(2, 1)) is not None
    assert not disconnected.can_reach(pos(0, 0), pos(2, 0))
    assert disconnected.path_between(pos(0, 0), pos(2, 0)) is None


def test_build_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    """monkeypatch temporarily replaces constants inside navmesh.py for this test."""
    game_map = make_map((Cell.GRASS,))

    monkeypatch.setattr(navmesh, "NAVMESH_NODES_N", 0)
    with pytest.raises(ValueError):
        navmesh.build_navmesh(game_map)

    monkeypatch.setattr(navmesh, "NAVMESH_NODES_N", 2)
    with pytest.raises(ValueError):
        navmesh.build_navmesh(game_map)

    monkeypatch.setattr(navmesh, "NAVMESH_NODES_N", TILE_SIZE)
    with pytest.raises(ValueError):
        navmesh.build_navmesh(game_map)

    monkeypatch.setattr(navmesh, "NAVMESH_NODES_N", NAVMESH_NODES_N)
    monkeypatch.setattr(navmesh, "NAVMESH_BUCKET_SIZE", 0)
    with pytest.raises(ValueError):
        navmesh.build_navmesh(game_map)


def test_project_imports() -> None:
    import_module("map")
    import_module("monsters")
