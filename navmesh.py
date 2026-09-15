from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Final

import arcade
import networkx as nx

from constants import NAVMESH_BUCKET_SIZE, NAVMESH_NODES_N, TILE_SIZE
from helper import BucketPosition, MeshIndex, MeshPosition, grid_to_pixels

if TYPE_CHECKING: # importe Map pour les types, pas pour exécution
    from map import Map


@dataclass(frozen=True)
class NavNode:
    mesh_x: MeshIndex
    mesh_y: MeshIndex


type NavNodeGrid = list[list[NavNode | None]]

PATH_POINT_EPSILON: Final[float] = 1e-9 

class NavMesh:
    """Façade de navigation: le graphe NetworkX reste un détail interne.

    Les chemins calculés passent par le navmesh, mais les segments entre les
    positions exactes données par l'appelant et les premiers/derniers noeuds ne
    sont pas validés contre les obstacles. L'appelant doit donc fournir des
    positions finies et plausibles pour un blob.
    """

    __graph: Final[nx.Graph[NavNode]]
    __buckets: Final[dict[BucketPosition, tuple[NavNode, ...]]]
    __node_positions: Final[dict[NavNode, arcade.Vec2]]

    def __init__(
        self,
        graph: nx.Graph[NavNode],
        buckets: dict[BucketPosition, tuple[NavNode, ...]],
        node_positions: dict[NavNode, arcade.Vec2],
    ) -> None:
        self.__graph = graph
        self.__buckets = buckets
        self.__node_positions = node_positions

    @property
    def node_count(self) -> int:
        return self.__graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.__graph.number_of_edges()

    def node_positions(self) -> tuple[arcade.Vec2, ...]:
        return tuple(_copy_position(position) for position in self.__node_positions.values())

    def edge_segments(self) -> Iterator[tuple[arcade.Vec2, arcade.Vec2]]:
        for node, neighbor in self.__graph.edges:
            yield (
                _copy_position(self.__node_positions[node]),
                _copy_position(self.__node_positions[neighbor]),
            )

    def closest_node(self, position: arcade.Vec2) -> NavNode:
        """Retourne le noeud le plus proche en inspectant uniquement les buckets nécessaires.
        c'est la partie du projet dont nous sommes les plus fiers car elle a une complexité quasi constant """
        _validate_finite_position(position, "position")

        if self.node_count == 0:
            raise ValueError("Cannot find closest node in an empty navmesh.")

        center = _bucket_position_of_position(position)

        radius = 0
        candidates = tuple(self.__nodes_in_bucket_ring(center, radius))

        while len(candidates) == 0:
            radius += 1
            candidates = tuple(self.__nodes_in_bucket_ring(center, radius))

        best_node = min(
            candidates,
            key=lambda node: self.__distance_squared_to_node(node, position),
        )
        best_distance_squared = self.__distance_squared_to_node(best_node, position)

        while _unchecked_buckets_may_contain_closer_node(position, center, radius, best_distance_squared):
            radius += 1

            for node in self.__nodes_in_bucket_ring(center, radius):
                distance_squared = self.__distance_squared_to_node(node, position)

                if distance_squared < best_distance_squared:
                    best_node = node
                    best_distance_squared = distance_squared

        return best_node

    def closest_node_legacy(self, position: arcade.Vec2) -> NavNode:
        """Retourne le noeud le plus proche en inspectant tous les noeuds du navmesh."""
        _validate_finite_position(position, "position")

        if self.node_count == 0:
            raise ValueError("Cannot find closest node in an empty navmesh.")

        return min(
            self.__graph.nodes,
            key=lambda node: self.__distance_squared_to_node(node, position),
        )

    def closest_position(self, position: arcade.Vec2) -> arcade.Vec2:
        return _copy_position(self.__node_positions[self.closest_node(position)])

    def can_reach(self, source: arcade.Vec2, target: arcade.Vec2) -> bool:
        """Teste si les noeuds les plus proches de `source` et `target` sont connectés.

        Précondition: `source` et `target` doivent représenter des positions
        finies et plausibles dans la zone navigable. Cette méthode ne vérifie
        pas que les points exacts sont eux-mêmes praticables.
        """
        _validate_finite_position(source, "source")
        _validate_finite_position(target, "target")

        if self.node_count == 0:
            return False

        source_node = self.closest_node(source)
        target_node = self.closest_node(target)
        return nx.has_path(self.__graph, source_node, target_node)

    def path_between(self, source: arcade.Vec2, target: arcade.Vec2) -> list[arcade.Vec2] | None:
        """Calcule le chemin source -> navmesh -> target, ou None si les composantes sont séparées.

        Précondition: `source` et `target` doivent être des positions finies et
        plausibles pour un blob. Les segments `source -> premier noeud` et
        `dernier noeud -> target` ne sont pas testés contre les obstacles.
        """
        _validate_finite_position(source, "source")
        _validate_finite_position(target, "target")

        if _positions_are_equal(source, target): 
            return [_copy_position(source)]
        if self.node_count == 0:
            return None

        source_node = self.closest_node(source)
        target_node = self.closest_node(target)

        try:
            node_path = nx.dijkstra_path(self.__graph, source=source_node, target=target_node, weight="weight")
        except nx.NetworkXNoPath:
            return None

        node_positions = [_copy_position(self.__node_positions[node]) for node in node_path]

        if len(node_positions) >= 2 and source.distance(node_positions[1]) <= node_positions[0].distance(node_positions[1]):
            # Evite que le blob reparte légèrement en arrière au début du chemin.
            # Précondition: l'appelant donne une source déjà praticable.
            node_positions.pop(0)

        return _with_endpoints_without_duplicates(source, node_positions, target)

    def __nodes_in_bucket_ring(self, center: BucketPosition, radius: int) -> Iterator[NavNode]:
        for bucket_position in _bucket_ring(center, radius):
            yield from self.__buckets.get(bucket_position, ())

    def __distance_squared_to_node(self, node: NavNode, position: arcade.Vec2) -> float:
        node_position = self.__node_positions[node]
        dx = node_position.x - position.x
        dy = node_position.y - position.y
        return dx * dx + dy * dy

    def __repr__(self) -> str:
        return (
            f"NavMesh("
            f"nodes={self.node_count}, "
            f"edges={self.edge_count}, "
            f"buckets={len(self.__buckets)}"
            ")"
        )


def mesh_index_to_pixels(mesh_i: MeshIndex) -> float:
    tile_i, inner_i = divmod(mesh_i, NAVMESH_NODES_N)
    return tile_i * TILE_SIZE + ((2 * inner_i + 1) * TILE_SIZE) / (2 * NAVMESH_NODES_N)


def is_walkable(game_map: Map, x: int, y: int) -> bool:
    return not game_map.get(x, y).is_blob_nav_obstacle


def is_wall_for_clearance(game_map: Map, x: int, y: int) -> bool:
    return game_map.get(x, y).is_player_obstacle


def build_navmesh(
    game_map: Map,
    is_walkable_for_blob: Callable[[Map, int, int], bool] = is_walkable,
    is_wall_for_clearance: Callable[[Map, int, int], bool] = is_wall_for_clearance,
) -> NavMesh:
    _validate_navmesh_constants()
    _validate_map_dimensions(game_map)

    graph: nx.Graph[NavNode] = nx.Graph()
    navmesh_grid = _build_navmesh_grid(game_map, is_walkable_for_blob, is_wall_for_clearance)
    node_grid, node_positions = _add_nodes(graph, navmesh_grid)

    _add_edges(graph, navmesh_grid, node_grid, node_positions)

    return NavMesh(
        graph=graph,
        buckets=_build_buckets(graph, node_positions),
        node_positions=node_positions,
    )


def _copy_position(position: arcade.Vec2) -> arcade.Vec2:
    return arcade.Vec2(position.x, position.y)


def _positions_are_equal(first: arcade.Vec2, second: arcade.Vec2) -> bool:
    return first.distance(second) <= PATH_POINT_EPSILON


def _with_endpoints_without_duplicates(
    source: arcade.Vec2,
    middle_points: Sequence[arcade.Vec2],
    target: arcade.Vec2,
) -> list[arcade.Vec2]:
    path = [_copy_position(source)]

    for point in (*middle_points, target):
        if not _positions_are_equal(path[-1], point):
            path.append(_copy_position(point))

    return path


def _validate_navmesh_constants() -> None:
    if NAVMESH_NODES_N <= 0:
        raise ValueError("NAVMESH_NODES_N must be positive.")
    if NAVMESH_NODES_N % 2 == 0:
        raise ValueError("NAVMESH_NODES_N must be odd.")
    if NAVMESH_NODES_N >= TILE_SIZE:
        raise ValueError("NAVMESH_NODES_N must be smaller than TILE_SIZE.")
    if NAVMESH_BUCKET_SIZE <= 0:
        raise ValueError("NAVMESH_BUCKET_SIZE must be positive.")


def _validate_map_dimensions(game_map: Map) -> None:
    if game_map.width <= 0 or game_map.height <= 0:
        raise ValueError("Cannot build a navmesh for an empty map.")


def _validate_finite_position(position: arcade.Vec2, name: str) -> None:
    if not math.isfinite(position.x) or not math.isfinite(position.y):
        raise ValueError(f"{name} must have finite coordinates.")


def _is_mesh_position_inside(game_map: Map, mesh_x: MeshIndex, mesh_y: MeshIndex) -> bool:
    return (
        0 <= mesh_x < game_map.width * NAVMESH_NODES_N
        and 0 <= mesh_y < game_map.height * NAVMESH_NODES_N
    )


def _is_too_close_to_wall(node_position: arcade.Vec2, wall_x: int, wall_y: int) -> bool:
    wall_position = arcade.Vec2(grid_to_pixels(wall_x), grid_to_pixels(wall_y))
    dx = node_position.x - wall_position.x
    dy = node_position.y - wall_position.y
    return dx * dx + dy * dy < TILE_SIZE * TILE_SIZE


def _build_navmesh_grid(
    game_map: Map,
    is_walkable_for_blob: Callable[[Map, int, int], bool],
    is_wall_for_clearance: Callable[[Map, int, int], bool],
) -> list[list[bool]]:
    n = NAVMESH_NODES_N
    navmesh_grid: list[list[bool]] = [[True] * (game_map.height * n) for _ in range(game_map.width * n)]

    nearby_tiles: Final[tuple[MeshPosition, ...]] = (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    )

    for x in range(game_map.width):
        for y in range(game_map.height):
            if not is_walkable_for_blob(game_map, x, y):
                for inner_x in range(n):
                    for inner_y in range(n):
                        navmesh_grid[x * n + inner_x][y * n + inner_y] = False

            # Les obstacles de navigation suppriment leur case entière; les murs
            # de clearance suppriment aussi les noeuds trop proches d'eux.
            if is_wall_for_clearance(game_map, x, y):
                _remove_nodes_too_close_to_wall(navmesh_grid, game_map, x, y, nearby_tiles)

    return navmesh_grid


def _remove_nodes_too_close_to_wall(
    navmesh_grid: list[list[bool]],
    game_map: Map,
    wall_x: int,
    wall_y: int,
    nearby_tiles: tuple[MeshPosition, ...],
) -> None:
    n = NAVMESH_NODES_N

    for diff_x, diff_y in nearby_tiles:
        tile_x = wall_x + diff_x
        tile_y = wall_y + diff_y

        for inner_x in range(n):
            for inner_y in range(n):
                mesh_x = tile_x * n + inner_x
                mesh_y = tile_y * n + inner_y

                if not _is_mesh_position_inside(game_map, mesh_x, mesh_y):
                    continue

                node_position = arcade.Vec2(
                    mesh_index_to_pixels(mesh_x),
                    mesh_index_to_pixels(mesh_y),
                )
                if _is_too_close_to_wall(node_position, wall_x, wall_y):
                    navmesh_grid[mesh_x][mesh_y] = False


def _add_nodes(graph: nx.Graph[NavNode], navmesh_grid: list[list[bool]]) -> tuple[NavNodeGrid, dict[NavNode, arcade.Vec2]]:
    node_grid: NavNodeGrid = [[None] * len(navmesh_grid[0]) for _ in range(len(navmesh_grid))]
    node_positions: dict[NavNode, arcade.Vec2] = {}

    for mesh_x in range(len(navmesh_grid)):
        for mesh_y in range(len(navmesh_grid[mesh_x])):
            if not navmesh_grid[mesh_x][mesh_y]:
                continue

            node = NavNode(mesh_x, mesh_y)
            graph.add_node(node)
            node_grid[mesh_x][mesh_y] = node
            node_positions[node] = arcade.Vec2(
                mesh_index_to_pixels(mesh_x),
                mesh_index_to_pixels(mesh_y),
            )

    return node_grid, node_positions


def _add_edges(
    graph: nx.Graph[NavNode],
    navmesh_grid: list[list[bool]],
    node_grid: NavNodeGrid,
    node_positions: dict[NavNode, arcade.Vec2],
) -> None:
    neighbor_offsets: Final[tuple[MeshPosition, ...]] = (
        (1, 0),
        (0, 1),
        (1, 1),
        (1, -1),
    )

    width = len(navmesh_grid)
    height = len(navmesh_grid[0]) if width > 0 else 0

    for mesh_x in range(width):
        for mesh_y in range(height):
            node = node_grid[mesh_x][mesh_y]
            if node is None:
                continue

            for diff_x, diff_y in neighbor_offsets:
                if not _can_link(navmesh_grid, mesh_x, mesh_y, diff_x, diff_y):
                    continue

                neighbor = node_grid[mesh_x + diff_x][mesh_y + diff_y]
                if neighbor is None:
                    continue

                graph.add_edge(
                    node,
                    neighbor,
                    weight=node_positions[node].distance(node_positions[neighbor]),
                )


def _can_link(
    navmesh_grid: list[list[bool]],
    mesh_x: MeshIndex,
    mesh_y: MeshIndex,
    diff_x: MeshIndex,
    diff_y: MeshIndex,
) -> bool:
    neighbor_x = mesh_x + diff_x
    neighbor_y = mesh_y + diff_y
    width = len(navmesh_grid)
    height = len(navmesh_grid[0]) if width > 0 else 0

    if not (0 <= neighbor_x < width and 0 <= neighbor_y < height):
        return False
    if not navmesh_grid[neighbor_x][neighbor_y]:
        return False

    if diff_x != 0 and diff_y != 0:
        # Une diagonale n'est valide que si le blob pourrait aussi passer par les deux côtés du coin.
        return navmesh_grid[mesh_x + diff_x][mesh_y] and navmesh_grid[mesh_x][mesh_y + diff_y]

    return True


def _bucket_position_of_position(position: arcade.Vec2) -> BucketPosition:
    return (
        int(position.x // NAVMESH_BUCKET_SIZE),
        int(position.y // NAVMESH_BUCKET_SIZE),
    )


def _bucket_ring(center: BucketPosition, radius: int) -> Iterator[BucketPosition]:
    center_x, center_y = center

    for bucket_x in range(center_x - radius, center_x + radius + 1):
        for bucket_y in range(center_y - radius, center_y + radius + 1):
            if max(abs(bucket_x - center_x), abs(bucket_y - center_y)) == radius:
                yield (bucket_x, bucket_y)


def _build_buckets(
    graph: nx.Graph[NavNode],
    node_positions: dict[NavNode, arcade.Vec2],
) -> dict[BucketPosition, tuple[NavNode, ...]]:
    mutable_buckets: dict[BucketPosition, list[NavNode]] = {}

    for node in graph.nodes:
        bucket_position = _bucket_position_of_position(node_positions[node])

        if bucket_position not in mutable_buckets:
            mutable_buckets[bucket_position] = []

        mutable_buckets[bucket_position].append(node)

    return {
        bucket_position: tuple(nodes)
        for bucket_position, nodes in mutable_buckets.items()
    }


def _unchecked_buckets_may_contain_closer_node(
    position: arcade.Vec2,
    center: BucketPosition,
    inspected_radius: int,
    best_distance_squared: float,
) -> bool:
    center_x, center_y = center

    left = (center_x - inspected_radius) * NAVMESH_BUCKET_SIZE
    right = (center_x + inspected_radius + 1) * NAVMESH_BUCKET_SIZE
    bottom = (center_y - inspected_radius) * NAVMESH_BUCKET_SIZE
    top = (center_y + inspected_radius + 1) * NAVMESH_BUCKET_SIZE

    min_unchecked_distance = min(
        position.x - left,
        right - position.x,
        position.y - bottom,
        top - position.y,
    )

    return min_unchecked_distance * min_unchecked_distance < best_distance_squared
