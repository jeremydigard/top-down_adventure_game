from __future__ import annotations

import csv
import gc
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from statistics import median
from time import perf_counter

import arcade

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from map import Map
from navmesh import build_navmesh
from world_builder import LoadedWorld, WorldBuilder


BENCHMARK_DIR = PROJECT_ROOT / "benchmarks"
RESULTS_DIR = BENCHMARK_DIR / "results"
SECONDS_PER_FRAME = 1 / 60


def map_text(width: int, height: int, cells: dict[tuple[int, int], str] | None = None) -> str:
    cells = cells or {}
    rows: list[str] = []

    for y in reversed(range(height)):
        row = "".join(cells.get((x, y), " ") for x in range(width))
        rows.append(row)

    return "\n".join((
        f"width: {width}",
        f"height: {height}",
        "switches: []",
        "gates: []",
        "---",
        *rows,
        "---",
    ))


def open_map_text(size: int) -> str:
    center = size // 2
    return map_text(size, size, {(center, center): "P"})


def blob_map_text(size: int, blob_count: int) -> str:
    center = size // 2
    cells: dict[tuple[int, int], str] = {(center, center): "P"}
    positions: list[tuple[int, int]] = [
        (x, y)
        for y in range(size)
        for x in range(size)
        if (x, y) != (center, center)
    ]
    positions.sort(key=lambda pos: (pos[0] - center) ** 2 + (pos[1] - center) ** 2)

    for position in positions[:blob_count]:
        cells[position] = "b"

    return map_text(size, size, cells)


def sample_seconds(action: Callable[[], None], repeats: int) -> float:
    samples: list[float] = []

    for _ in range(repeats):
        gc.collect()
        start = perf_counter()
        action()
        samples.append(perf_counter() - start)

    return median(samples)


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def svg_polyline(points: Sequence[tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def write_svg_line_chart(
    path: Path,
    title: str,
    x_label: str,
    y_label: str,
    series: Sequence[tuple[str, Sequence[tuple[float, float]], str]],
) -> None:
    width = 760
    height = 460
    left = 82
    right = 24
    top = 48
    bottom = 72

    all_points = [point for _, points, _ in series for point in points]
    max_x = max(x for x, _ in all_points)
    max_y = max(y for _, y in all_points)
    min_x = min(x for x, _ in all_points)
    min_y = 0.0

    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_to_px(x: float) -> float:
        if max_x == min_x:
            return left + plot_width / 2
        return left + (x - min_x) * plot_width / (max_x - min_x)

    def y_to_px(y: float) -> float:
        if max_y == min_y:
            return top + plot_height / 2
        return top + plot_height - (y - min_y) * plot_height / (max_y - min_y)

    y_ticks = [max_y * i / 4 for i in range(5)]
    x_ticks = [min_x + (max_x - min_x) * i / 4 for i in range(5)]

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,sans-serif;font-size:13px} .label{fill:#333} .grid{stroke:#ddd;stroke-width:1} .axis{stroke:#333;stroke-width:1.5}</style>',
        f'<text x="{width / 2}" y="24" text-anchor="middle" font-size="18" font-weight="700">{title}</text>',
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}"/>',
        f'<line class="axis" x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}"/>',
    ]

    for tick in y_ticks:
        y = y_to_px(tick)
        lines.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}"/>')
        lines.append(f'<text class="label" x="{left - 8}" y="{y + 4:.2f}" text-anchor="end">{tick:.3g}</text>')

    for tick in x_ticks:
        x = x_to_px(tick)
        lines.append(f'<line class="grid" x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}"/>')
        lines.append(f'<text class="label" x="{x:.2f}" y="{top + plot_height + 22}" text-anchor="middle">{tick:.3g}</text>')

    for index, (name, points, color) in enumerate(series):
        svg_points = [(x_to_px(x), y_to_px(y)) for x, y in points]
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{svg_polyline(svg_points)}"/>')
        for x, y in svg_points:
            lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="{color}"/>')
        legend_y = 48 + 22 * index
        lines.append(f'<rect x="{width - 180}" y="{legend_y - 10}" width="16" height="4" fill="{color}"/>')
        lines.append(f'<text class="label" x="{width - 158}" y="{legend_y - 5}">{name}</text>')

    lines.append(f'<text class="label" x="{left + plot_width / 2}" y="{height - 20}" text-anchor="middle">{x_label}</text>')
    lines.append(f'<text class="label" transform="translate(20 {top + plot_height / 2}) rotate(-90)" text-anchor="middle">{y_label}</text>')
    lines.append("</svg>")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def set_blobs_visible(world: LoadedWorld) -> None:
    for mob in world.mobs:
        if hasattr(mob, "sight_radius"):
            mob.sight_radius = 10_000


def build_physics_engine(world: LoadedWorld) -> arcade.PhysicsEngineSimple:
    obstacles = arcade.SpriteList()
    obstacles.extend(world.walls)
    obstacles.extend(world.closed_gates)
    return arcade.PhysicsEngineSimple(world.player, obstacles)


def update_world_once(
    world: LoadedWorld,
    physics_engine: arcade.PhysicsEngineSimple,
    delta_time: float,
) -> None:
    if world.weapon_controller.locks_player:
        world.player.change_x = 0
        world.player.change_y = 0
    else:
        world.player.update(delta_time)

    physics_engine.update()

    player_position = world.player.position
    for mob in world.mobs:
        mob.update_monster(delta_time, player_position)

    world.weapon_controller.update_weapon(world.weapon_context, delta_time)
    world.crystals.update_animation(delta_time)
    world.mobs.update_animation(delta_time)
    world.player_list.update_animation(delta_time)
    world.weapons.update_animation(delta_time)

    arcade.check_for_collision_with_list(world.player, world.trou)
    arcade.check_for_collision_with_list(world.player, world.mobs)
    arcade.check_for_collision_with_list(world.player, world.crystals)
    arcade.check_for_collision_with_list(world.player, world.exits)


def benchmark_loading() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for size in (5, 10, 20, 40, 80):
        raw = open_map_text(size)

        def action() -> None:
            WorldBuilder.build_from_string(raw)

        seconds = sample_seconds(action, repeats=5)
        world = WorldBuilder.build_from_string(raw)
        rows.append({
            "size": size,
            "cells": size * size,
            "navmesh_nodes": world.navmesh.node_count,
            "median_seconds": seconds,
            "median_ms": seconds * 1000,
        })

    return rows


def benchmark_on_update() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    size = 35

    for blob_count in (1, 3, 10, 30, 60, 120):
        raw = blob_map_text(size, blob_count)
        samples: list[float] = []

        for _ in range(7):
            world = WorldBuilder.build_from_string(raw)
            physics_engine = build_physics_engine(world)
            set_blobs_visible(world)
            gc.collect()
            start = perf_counter()
            update_world_once(world, physics_engine, SECONDS_PER_FRAME)
            samples.append(perf_counter() - start)

        seconds = median(samples)
        rows.append({
            "blobs": blob_count,
            "median_seconds": seconds,
            "median_ms": seconds * 1000,
        })

    return rows


def benchmark_closest_node() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for size in (5, 10, 20, 40, 80):
        game_map = Map.from_string(open_map_text(size))
        mesh = build_navmesh(game_map)
        queries = [
            arcade.Vec2((i * 17) % (size * 32), (i * 31) % (size * 32))
            for i in range(300)
        ]

        def current_action() -> None:
            for query in queries:
                mesh.closest_node(query)

        def legacy_action() -> None:
            for query in queries:
                mesh.closest_node_legacy(query)

        current_seconds = sample_seconds(current_action, repeats=9)
        legacy_seconds = sample_seconds(legacy_action, repeats=9)
        rows.append({
            "size": size,
            "cells": size * size,
            "navmesh_nodes": mesh.node_count,
            "queries": len(queries),
            "current_ms": current_seconds * 1000,
            "legacy_ms": legacy_seconds * 1000,
            "speedup": legacy_seconds / current_seconds,
        })

    return rows


def print_rows(title: str, rows: Iterable[dict[str, object]]) -> None:
    print(title)
    for row in rows:
        print(row)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    loading_rows = benchmark_loading()
    write_csv(RESULTS_DIR / "loading.csv", loading_rows)
    write_svg_line_chart(
        RESULTS_DIR / "loading.svg",
        "Chargement du monde",
        "cellules de map",
        "temps median (ms)",
        (("chargement", [(float(row["cells"]), float(row["median_ms"])) for row in loading_rows], "#2563eb"),),
    )

    update_rows = benchmark_on_update()
    write_csv(RESULTS_DIR / "on_update.csv", update_rows)
    write_svg_line_chart(
        RESULTS_DIR / "on_update.svg",
        "on_update avec blobs visibles",
        "nombre de blobs",
        "temps median (ms)",
        (("on_update", [(float(row["blobs"]), float(row["median_ms"])) for row in update_rows], "#16a34a"),),
    )

    closest_rows = benchmark_closest_node()
    write_csv(RESULTS_DIR / "closest_node.csv", closest_rows)
    write_svg_line_chart(
        RESULTS_DIR / "closest_node.svg",
        "Recherche du noeud le plus proche",
        "noeuds de navmesh",
        "temps median pour 300 requetes (ms)",
        (
            ("buckets", [(float(row["navmesh_nodes"]), float(row["current_ms"])) for row in closest_rows], "#7c3aed"),
            ("legacy", [(float(row["navmesh_nodes"]), float(row["legacy_ms"])) for row in closest_rows], "#dc2626"),
        ),
    )

    print_rows("loading", loading_rows)
    print_rows("on_update", update_rows)
    print_rows("closest_node", closest_rows)


if __name__ == "__main__":
    main()
