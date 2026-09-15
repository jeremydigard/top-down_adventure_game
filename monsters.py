from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Final
import random
import math
import arcade
from navmesh import NavMesh

from textures import SPINNER_ANIMATION, BAT_ANIMATION, BLOB_ANIMATION
from helper import Pixel, PixelPosition, Tile, TileBounds, TilePosition, grid_to_pixels
from constants import (
    SCALE,
    SPINNER_MOVEMENT_SPEED,
    BAT_MOVEMENT_SPEED,
    BAT_FRAMES_DIR_CHANGE,
    BAT_PATROL_HALF_SIZE,
    BAT_DIRECTION_SIGMA,
    BAT_RETURN_TO_CENTER_SIGMA,
    BLOB_MOVEMENT_SPEED,
    BLOB_ACTION_RADIUS,
    BLOB_TARGET_RECOMPUTE_DISTANCE,
    PLAYER_HEALTH,
)

from weapon_hittable import WeaponHittable
from map import Map



class ContactDamaging(ABC):
    """Interface for entities that can damage on contact."""

    @property
    @abstractmethod
    def contact_damage(self) -> int:
        ...

class Monster(arcade.TextureAnimationSprite, ABC):
    """Base class for all monsters in the game."""

    def speed_update(self) -> None: # vu qu'on a enlevé la dépendance de spinner à ca, c plus opti de le garder
        self.center_x += self.change_x
        self.center_y += self.change_y

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"velocity=({self.change_x:.1f}, {self.change_y:.1f})"
            ")"
        )

    @abstractmethod
    def update_monster(self, delta_time: float, player_position: PixelPosition) -> None:
        ...

class Enemy(Monster, ContactDamaging, WeaponHittable):
    """Base class for all enemies that can damage the player and be hit by weapons."""
    @property
    @abstractmethod
    def contact_damage(self) -> int:
        ...
    def on_weapon_hit(self) -> None:
        self.remove_from_sprite_lists()




class Spinner(Enemy):
    boundary_min: Final[float]
    boundary_max: Final[float]

    def __init__(self, grid_x: Tile, grid_y: Tile, boundary_cells: TileBounds) -> None:
        super().__init__(
            animation=SPINNER_ANIMATION,
            scale=SCALE,
            center_x=grid_to_pixels(grid_x),
            center_y=grid_to_pixels(grid_y),
        )
        min_cell, max_cell = boundary_cells
        self.boundary_min = grid_to_pixels(min_cell)
        self.boundary_max = grid_to_pixels(max_cell)

    @property
    def contact_damage(self) -> int:
        return 2

    def _next_axis_position_and_speed(self, position: Pixel, speed: Pixel) -> tuple[Pixel, Pixel]:
        next_position = position + speed

        # On clamp sur la borne avant d'inverser la vitesse: sinon un spinner
        # dont min == max oscille de quelques pixels dans le mur.
        if next_position < self.boundary_min:
            return self.boundary_min, abs(speed)
        if next_position > self.boundary_max:
            return self.boundary_max, -abs(speed)
        return next_position, speed

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"bounds=({self.boundary_min:.1f}, {self.boundary_max:.1f}), "
            f"velocity=({self.change_x:.1f}, {self.change_y:.1f})"
            ")"
        )

class SpinnerHorizontal(Spinner):
    def __init__(self, grid_x: Tile, grid_y: Tile, game_map: Map) -> None:
        super().__init__(
            grid_x,
            grid_y,
            compute_horizontal_bounds(game_map, grid_x, grid_y),
        )
        self.change_x = SPINNER_MOVEMENT_SPEED
        self.change_y = 0

    def update_monster(self, delta_time: float, player_position: PixelPosition) -> None:
        self.center_x, self.change_x = self._next_axis_position_and_speed(self.center_x, self.change_x)


class SpinnerVertical(Spinner):
    def __init__(self, grid_x: Tile, grid_y: Tile, game_map: Map) -> None:
        super().__init__(
            grid_x,
            grid_y,
            compute_vertical_bounds(game_map, grid_x, grid_y),
        )
        self.change_x = 0
        self.change_y = SPINNER_MOVEMENT_SPEED

    def update_monster(self, delta_time: float, player_position: PixelPosition) -> None:
        self.center_y, self.change_y = self._next_axis_position_and_speed(self.center_y, self.change_y)


def _find_bound(
    game_map: Map,
    x: Tile,
    y: Tile,
    dx: int,
    dy: int,
) -> TilePosition:
    current_x = x
    current_y = y

    while True:
        next_x = current_x + dx
        next_y = current_y + dy

        if not (0 <= next_x < game_map.width and 0 <= next_y < game_map.height):
            return current_x, current_y

        # Les bornes sont calculées une fois depuis la Map, indépendamment des
        # sprites Arcade. Les spinners traversent les entités non bloquantes
        # comme les cristaux et les autres spinners.
        if game_map.get(next_x, next_y).blocks_spinner:
            return current_x, current_y

        current_x = next_x
        current_y = next_y

def compute_horizontal_bounds(game_map: Map, x: Tile, y: Tile) -> TileBounds:
    left_x, _ = _find_bound(game_map, x, y, dx=-1, dy=0)
    right_x, _ = _find_bound(game_map, x, y, dx=1, dy=0)
    return left_x, right_x

def compute_vertical_bounds(game_map: Map, x: Tile, y: Tile) -> TileBounds:
    _, bottom_y = _find_bound(game_map, x, y, dx=0, dy=-1)
    _, top_y = _find_bound(game_map, x, y, dx=0, dy=1)
    return bottom_y, top_y


class Bat(Enemy):
    __border: Final[arcade.Rect]
    __angle: float
    __dir_frames_counter: int
    __random: random.Random

    def __init__(
        self,
        center_x: Pixel,
        center_y: Pixel,
        world_width: Pixel,
        world_height: Pixel,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(animation=BAT_ANIMATION, scale=SCALE, center_x=center_x, center_y=center_y)

        if rng is not None:
            self.__random = rng
        else:
            self.__random = random.Random(None)

        self.__border = arcade.LRBT(
            max(0, center_x - BAT_PATROL_HALF_SIZE),
            min(world_width, center_x + BAT_PATROL_HALF_SIZE),
            max(0, center_y - BAT_PATROL_HALF_SIZE),
            min(world_height, center_y + BAT_PATROL_HALF_SIZE),
        )
        self.__angle = self.__random.uniform(0, 2 * math.pi)
        self.__dir_frames_counter = BAT_FRAMES_DIR_CHANGE

    @property
    def contact_damage(self) -> int:
        return 1

    def new_dir(self) -> None:
        self.__angle = (self.__angle + self.__random.gauss(0, BAT_DIRECTION_SIGMA)) % (2 * math.pi)
        self.__dir_frames_counter = BAT_FRAMES_DIR_CHANGE

    def __turn_toward_center(self) -> None:
        center = arcade.Vec2(self.__border.center_x, self.__border.center_y)
        to_center = center - self.position
        self.__angle = (
            math.atan2(to_center.y, to_center.x)
            + self.__random.gauss(0, BAT_RETURN_TO_CENTER_SIGMA)
        ) % (2 * math.pi)
        self.__dir_frames_counter = BAT_FRAMES_DIR_CHANGE

    def update_monster(self, delta_time: float, player_position: PixelPosition) -> None:
        self.__dir_frames_counter -= 1
        if self.__dir_frames_counter <= 0:
            self.new_dir()

        self.__set_velocity_from_angle()
        next_position = arcade.Vec2(self.center_x + self.change_x, self.center_y + self.change_y)
        if not self.__border.point_in_rect(next_position):
            self.__turn_toward_center()
            self.__set_velocity_from_angle()

        self.speed_update()
        self.__clamp_to_border()

    def __set_velocity_from_angle(self) -> None:
        self.change_x = BAT_MOVEMENT_SPEED * math.cos(self.__angle)
        self.change_y = BAT_MOVEMENT_SPEED * math.sin(self.__angle)

    def __clamp_to_border(self) -> None:
        self.center_x = min(max(self.center_x, self.__border.left), self.__border.right)
        self.center_y = min(max(self.center_y, self.__border.bottom), self.__border.top)

    def __repr__(self) -> str:
        return (
            f"Bat("
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"angle={self.__angle:.2f}, "
            f"velocity=({self.change_x:.1f}, {self.change_y:.1f}), "
            f"border={self.__border}"
            ")"
        )



class Blob(Enemy):
    __origin: Final[arcade.Vec2]
    __destination: arcade.Vec2
    __navmesh: Final[NavMesh]
    __path: list[arcade.Vec2]
    __possible_destinations: Final[tuple[arcade.Vec2, ...]]
    __random: random.Random
    __path_index: int
    __sight_radius: Final[float]
    __vision_blockers: Final[arcade.SpriteSequence[arcade.BasicSprite]]

    def __init__(
        self,
        origine: arcade.Vec2,
        navmesh: NavMesh,
        possible_destinations: Sequence[arcade.Vec2],
        sight_radius: Pixel,
        vision_blockers: arcade.SpriteSequence[arcade.BasicSprite],
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(
            animation=BLOB_ANIMATION,
            scale=SCALE,
            center_x=origine.x,
            center_y=origine.y,
        )

        if len(possible_destinations) == 0:
            raise ValueError("Blob must have at least one possible destination.")
        if sight_radius <= 0:
            raise ValueError("Sight radius must be positive.")
        self.__origin = arcade.Vec2(origine.x, origine.y)
        self.__destination = arcade.Vec2(self.__origin.x, self.__origin.y)
        self.__path = [arcade.Vec2(self.__origin.x, self.__origin.y)]
        self.__path_index = 1
        self.__possible_destinations = tuple(
            arcade.Vec2(destination.x, destination.y)
            for destination in possible_destinations
        )
        self.__sight_radius = sight_radius
        self.__navmesh = navmesh
        self.__vision_blockers = vision_blockers
        if rng is not None:
            self.__random = rng
        else:
            self.__random = random.Random(None)

        self._choose_new_patrol_destination()

    @property
    def _current_position(self) -> arcade.Vec2:
        return arcade.Vec2(self.center_x, self.center_y)

    def _distance_to(self, point: arcade.Vec2) -> Pixel:
        return math.hypot(self.center_x - point.x, self.center_y - point.y)

    def _choose_new_patrol_destination(self) -> None:
        if not self.__possible_destinations:
            self.__destination = self._current_position
            self.__path = [self._current_position]
            self.__path_index = 1
            return

        candidates = list(self.__possible_destinations)
        self.__random.shuffle(candidates)

        current_position = self._current_position

        for destination in candidates:
            if self.__origin.distance(destination) > BLOB_ACTION_RADIUS:
                continue

            path = self.__navmesh.path_between(current_position, destination)
            if path is None:
                continue

            self.__destination = arcade.Vec2(destination.x, destination.y)
            self.__path = path
            self.__path_index = 1
            return

        self.__destination = current_position
        self.__path = [current_position]
        self.__path_index = 1

    def _has_reached_destination(self) -> bool:
        return self.__path_index >= len(self.__path) and self._distance_to(self.__destination) <= 2.0

    def _move_along_path(self) -> None:
        remaining = BLOB_MOVEMENT_SPEED

        while remaining > 0 and self.__path_index < len(self.__path):
            target = self.__path[self.__path_index]
            dx = target.x - self.center_x
            dy = target.y - self.center_y
            distance = math.hypot(dx, dy)

            if distance == 0:
                self.__path_index += 1
                continue

            if distance <= remaining:
                self.center_x = target.x
                self.center_y = target.y
                remaining -= distance
                self.__path_index += 1
            else:
                self.center_x += remaining * dx / distance
                self.center_y += remaining * dy / distance
                remaining = 0

    def update_monster(self, delta_time: float, player_position: PixelPosition) -> None:
        player_pos = arcade.Vec2(*player_position)
        if self._can_see_player(player_pos):
            if (self.__destination - player_pos).length_squared() > BLOB_TARGET_RECOMPUTE_DISTANCE ** 2:
                self._set_destination(player_pos)
        else:
            if self._has_reached_destination():
                self._choose_new_patrol_destination()

        self._move_along_path()

    @staticmethod
    def patrol_destinations(
        game_map: Map,
        origin_x: Tile,
        origin_y: Tile,
        is_walkable_for_blob: Callable[[Map, Tile, Tile], bool],
        navmesh: NavMesh | None = None,
        radius_cells: Tile = 3,
    ) -> Sequence[arcade.Vec2]:
        destinations: list[arcade.Vec2] = []
        origin = arcade.Vec2(grid_to_pixels(origin_x), grid_to_pixels(origin_y))

        for y in range(origin_y - radius_cells, origin_y + radius_cells + 1):
            for x in range(origin_x - radius_cells, origin_x + radius_cells + 1):
                if not (0 <= x < game_map.width and 0 <= y < game_map.height):
                    continue
                if not is_walkable_for_blob(game_map, x, y):
                    continue

                destination = arcade.Vec2(grid_to_pixels(x), grid_to_pixels(y))
                if navmesh is not None and not navmesh.can_reach(origin, destination):
                    continue

                destinations.append(destination)

        return destinations

    def _can_see_player(self, player_pos: arcade.Vec2) -> bool:
        if self._distance_to(player_pos) > self.__sight_radius:
            return False
        return arcade.has_line_of_sight(
            (self.center_x, self.center_y),
            (player_pos.x, player_pos.y),
            self.__vision_blockers,
            self.__sight_radius,
        )

    def _set_destination(self, destination: arcade.Vec2) -> None:
        path = self.__navmesh.path_between(self._current_position, destination)
        if path is None:
            return
        self.__destination = arcade.Vec2(destination.x, destination.y)
        self.__path = path
        self.__path_index = 1

    def __repr__(self) -> str:
        return (
            f"Blob("
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"destination=({self.__destination.x:.1f}, {self.__destination.y:.1f}), "
            f"path_index={self.__path_index}, "
            f"path_len={len(self.__path)}"
            ")"
        )

    @property
    def contact_damage(self) -> int:
        return 3
