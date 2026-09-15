from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import Enum, auto
import math
from typing import Final

import arcade

from constants import (
    BOOMERANG_COOLDOWN,
    BOOMERANG_MOVEMENT_SPEED,
    SCALE,
    SWORD_ACTIVE_DURATION,
    SWORD_COOLDOWN,
    SWORD_R,
    TILE_SIZE,
    SECONDS_PER_FRAME,
)
from player import Direction, Player
from portail import Lever
from textures import BOOMERANG_ANIMATION, SWORD_ATTACK_ANIMATIONS
from weapon_hittable import WeaponHittable


SWORD_ACTIVE_SECONDS: Final[float] = SWORD_ACTIVE_DURATION / 1000


def _frames_to_seconds(frame_count: int) -> float:
    return frame_count * SECONDS_PER_FRAME


class Cooldown:
    __remaining: float

    def __init__(self) -> None:
        self.__remaining = 0.0

    @property
    def ready(self) -> bool:
        return self.__remaining <= 0.0

    def start(self, duration: float) -> None:
        self.__remaining = max(0.0, duration)

    def update(self, delta_time: float) -> None:
        self.__remaining = max(0.0, self.__remaining - delta_time)

    def __repr__(self) -> str:
        return f"Cooldown(remaining={self.__remaining:.3f})"


@dataclass(frozen=True)
class WeaponContext:
    player: Player
    walls: arcade.SpriteSequence[arcade.Sprite]
    mobs: arcade.SpriteSequence[arcade.Sprite]
    levers: arcade.SpriteSequence[arcade.Sprite]
    crystals: arcade.SpriteSequence[arcade.Sprite]


@dataclass(frozen=True)
class HitTarget:
    target: WeaponHittable


@dataclass(frozen=True)
class ToggleLever:
    lever: Lever


@dataclass(frozen=True)
class CollectCrystal:
    crystal: arcade.Sprite


WeaponEffect = HitTarget | ToggleLever | CollectCrystal


class Arme(ABC):
    """Interface métier commune aux armes.
    """

    _cooldown: Final[Cooldown]

    def __init__(self) -> None:
        self._cooldown = Cooldown()

    @property
    @abstractmethod
    def sprites(self) -> tuple[arcade.Sprite, ...]:
        ...

    @property
    def sprite(self) -> arcade.Sprite:
        return self.sprites[0]

    @property
    @abstractmethod
    def is_active(self) -> bool:
        ...

    @property
    def can_use(self) -> bool:
        return self._cooldown.ready and not self.is_active

    @property
    @abstractmethod
    def locks_player(self) -> bool:
        ...

    @abstractmethod
    def use(self, context: WeaponContext) -> None:
        ...

    @abstractmethod
    def update_weapon(self, context: WeaponContext, delta_time: float) -> Iterator[WeaponEffect]:
        ...

    @property
    def visible(self) -> bool:
        return self.sprite.visible

    @property
    def change_x(self) -> float:
        return self.sprite.change_x

    @property
    def change_y(self) -> float:
        return self.sprite.change_y

    @property
    def center_x(self) -> float:
        return self.sprite.center_x

    @property
    def center_y(self) -> float:
        return self.sprite.center_y

    @property
    def position(self) -> tuple[float, float]:
        return self.sprite.position

    def draw_hit_box(self, color: arcade.types.Color = arcade.color.BLACK, line_thickness: float = 1) -> None:
        self.sprite.draw_hit_box(color=color, line_thickness=line_thickness)


class BoomerangState(Enum):
    INACTIVE = auto()
    LAUNCHING = auto()
    RETURNING = auto()


DIRECTION_TO_UNIT: Final[Mapping[Direction, tuple[float, float]]] = {
    Direction.UP: (0.0, 1.0),
    Direction.DOWN: (0.0, -1.0),
    Direction.LEFT: (-1.0, 0.0),
    Direction.RIGHT: (1.0, 0.0),
}


class Boomerang(Arme):
    __sprite: Final[arcade.TextureAnimationSprite]
    __distance_traveled: float
    __state: BoomerangState
    __hit_lever_ids: set[str]

    def __init__(self) -> None:
        super().__init__()
        self.__sprite = arcade.TextureAnimationSprite(
            animation=BOOMERANG_ANIMATION,
            scale=SCALE,
        )
        self.__distance_traveled = 0.0
        self.__state = BoomerangState.INACTIVE
        self.__hit_lever_ids = set()
        self.__sprite.visible = False

    @property
    def sprites(self) -> tuple[arcade.Sprite, ...]:
        return (self.__sprite,)

    @property
    def is_active(self) -> bool:
        return self.__state != BoomerangState.INACTIVE

    @property
    def locks_player(self) -> bool:
        return False

    @property
    def state(self) -> BoomerangState:
        return self.__state

    def use(self, context: WeaponContext) -> None:
        if not self.can_use:
            return

        self.__state = BoomerangState.LAUNCHING
        self.__distance_traveled = 0.0
        self.__hit_lever_ids.clear()
        self.__sprite.position = context.player.position

        dx, dy = DIRECTION_TO_UNIT[context.player.direction]
        self.__sprite.change_x = dx * BOOMERANG_MOVEMENT_SPEED
        self.__sprite.change_y = dy * BOOMERANG_MOVEMENT_SPEED
        self.__sprite.visible = True

    def update_weapon(self, context: WeaponContext, delta_time: float) -> Iterator[WeaponEffect]:
        self._cooldown.update(delta_time)

        match self.__state:
            case BoomerangState.INACTIVE:
                return
            case BoomerangState.LAUNCHING:
                for effect in self.__update_launching(context):
                    yield effect
            case BoomerangState.RETURNING:
                for effect in self.__update_returning(context):
                    yield effect

    def __update_launching(self, context: WeaponContext) -> Iterator[WeaponEffect]:
        self.__sprite.center_x += self.__sprite.change_x
        self.__sprite.center_y += self.__sprite.change_y
        self.__distance_traveled += BOOMERANG_MOVEMENT_SPEED

        should_return = False
        for effect in self.__hit_mobs(context):
            should_return = True
            yield effect
        for effect in self.__hit_levers(context):
            should_return = True
            yield effect

        if should_return or self.__distance_traveled >= 8 * TILE_SIZE or self.__hits_wall(context):
            self.__start_returning()

    def __update_returning(self, context: WeaponContext) -> Iterator[WeaponEffect]:
        dx = context.player.center_x - self.__sprite.center_x
        dy = context.player.center_y - self.__sprite.center_y
        dist = math.hypot(dx, dy)

        if dist <= TILE_SIZE // 2:
            self.__deactivate()
            return

        self.__sprite.change_x = (dx / dist) * BOOMERANG_MOVEMENT_SPEED
        self.__sprite.change_y = (dy / dist) * BOOMERANG_MOVEMENT_SPEED
        self.__sprite.center_x += self.__sprite.change_x
        self.__sprite.center_y += self.__sprite.change_y

        for effect in self.__hit_mobs(context):
            yield effect
        for effect in self.__hit_levers(context):
            yield effect

    def __hit_mobs(self, context: WeaponContext) -> Iterator[WeaponEffect]:
        for mob in arcade.check_for_collision_with_list(self.__sprite, context.mobs):
            match mob:
                case WeaponHittable():
                    yield HitTarget(mob)

    def __hit_levers(self, context: WeaponContext) -> Iterator[WeaponEffect]:
        for lever_sprite in arcade.check_for_collision_with_list(self.__sprite, context.levers):
            match lever_sprite:
                case Lever() as lever:
                    if lever.id in self.__hit_lever_ids:
                        continue
                    self.__hit_lever_ids.add(lever.id)
                    yield ToggleLever(lever)

    def __hits_wall(self, context: WeaponContext) -> bool:
        return bool(arcade.check_for_collision_with_list(self.__sprite, context.walls))

    def __start_returning(self) -> None:
        self.__state = BoomerangState.RETURNING

    def __deactivate(self) -> None:
        self.__state = BoomerangState.INACTIVE
        self.__sprite.visible = False
        self.__sprite.change_x = 0
        self.__sprite.change_y = 0
        self._cooldown.start(_frames_to_seconds(BOOMERANG_COOLDOWN))

    def __repr__(self) -> str:
        return (
            f"Boomerang("
            f"state={self.__state.name}, "
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"velocity=({self.change_x:.1f}, {self.change_y:.1f}), "
            f"distance_traveled={self.__distance_traveled:.1f}, "
            f"visible={self.visible}"
            ")"
        )


_DIRECTION_TO_ANIM_KEY: Final[Mapping[Direction, str]] = {
    Direction.UP: "up",
    Direction.DOWN: "down",
    Direction.LEFT: "left",
    Direction.RIGHT: "right",
}

_DIRECTION_TO_SWORD_HITBOX_OFFSET: Final[Mapping[Direction, tuple[tuple[int, int], ...]]] = {
    Direction.UP: ((-SWORD_R, 0), (SWORD_R, 0), (SWORD_R, SWORD_R), (-SWORD_R, SWORD_R)),
    Direction.DOWN: ((-SWORD_R, 0), (SWORD_R, 0), (SWORD_R, -SWORD_R), (-SWORD_R, -SWORD_R)),
    Direction.LEFT: ((0, -SWORD_R), (0, SWORD_R), (-SWORD_R, SWORD_R), (-SWORD_R, -SWORD_R)),
    Direction.RIGHT: ((0, -SWORD_R), (0, SWORD_R), (SWORD_R, SWORD_R), (SWORD_R, -SWORD_R)),
}


class Epee(Arme):
    __sprite: Final[arcade.TextureAnimationSprite]
    __active: bool
    __elapsed: float
    __hit_lever_ids: set[str]

    def __init__(self) -> None:
        super().__init__()
        self.__sprite = arcade.TextureAnimationSprite(
            animation=SWORD_ATTACK_ANIMATIONS["down"],
            scale=SCALE,
        )
        self.__active = False
        self.__elapsed = 0.0
        self.__hit_lever_ids = set()
        self.__sprite.visible = False

    @property
    def sprites(self) -> tuple[arcade.Sprite, ...]:
        return (self.__sprite,)

    @property
    def is_active(self) -> bool:
        return self.__active

    @property
    def locks_player(self) -> bool:
        return self.__active

    def use(self, context: WeaponContext) -> None:
        if not self.can_use:
            return

        direction = context.player.direction
        self.__sprite.animation = SWORD_ATTACK_ANIMATIONS[_DIRECTION_TO_ANIM_KEY[direction]]
        self.__sprite.position = context.player.position
        self.__sprite.hit_box = arcade.hitbox.HitBox(
            _DIRECTION_TO_SWORD_HITBOX_OFFSET[direction],
            position=self.__sprite.position,
        )
        self.__sprite.time = 0.0

        self.__active = True
        self.__elapsed = 0.0
        self.__hit_lever_ids.clear()
        self.__sprite.visible = True
        context.player.visible = False

    def update_weapon(self, context: WeaponContext, delta_time: float) -> Iterator[WeaponEffect]:
        self._cooldown.update(delta_time)

        if not self.__active:
            return

        self.__elapsed += delta_time
        self.__sprite.position = context.player.position

        for effect in self.__hit_mobs(context):
            yield effect
        for effect in self.__hit_levers(context):
            yield effect
        for effect in self.__collect_crystals(context):
            yield effect

        if self.__elapsed >= SWORD_ACTIVE_SECONDS:
            self.__deactivate(context.player)

    def __hit_mobs(self, context: WeaponContext) -> Iterator[WeaponEffect]:
        for mob in arcade.check_for_collision_with_list(self.__sprite, context.mobs):
            match mob:
                case WeaponHittable():
                    yield HitTarget(mob)

    def __hit_levers(self, context: WeaponContext) -> Iterator[WeaponEffect]:
        for lever_sprite in arcade.check_for_collision_with_list(self.__sprite, context.levers):
            match lever_sprite:
                case Lever() as lever:
                    if lever.id in self.__hit_lever_ids:
                        continue
                    self.__hit_lever_ids.add(lever.id)
                    yield ToggleLever(lever)

    def __collect_crystals(self, context: WeaponContext) -> Iterator[WeaponEffect]:
        for crystal in arcade.check_for_collision_with_list(self.__sprite, context.crystals):
            yield CollectCrystal(crystal)

    def __deactivate(self, player: Player) -> None:
        self.__active = False
        self.__sprite.visible = False
        player.visible = True
        self._cooldown.start(_frames_to_seconds(SWORD_COOLDOWN))

    def __repr__(self) -> str:
        return (
            f"Epee("
            f"active={self.__active}, "
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"elapsed={self.__elapsed:.3f}, "
            f"visible={self.visible}"
            ")"
        )


class WeaponController:
    """Inventaire actif du joueur"""

    __weapons: Final[tuple[Arme, ...]]
    __active_index: int

    def __init__(self, weapons: tuple[Arme, ...]) -> None:
        if len(weapons) == 0:
            raise ValueError("WeaponController requires at least one weapon.")
        self.__weapons = weapons
        self.__active_index = 0

    @property
    def weapons(self) -> tuple[Arme, ...]:
        return self.__weapons

    @property
    def active_weapon(self) -> Arme:
        return self.__weapons[self.__active_index]

    @property
    def locks_player(self) -> bool:
        for weapon in self.__weapons:
            if weapon.locks_player:
                return True
        return False

    def switch_weapon(self) -> None:
        for weapon in self.__weapons:
            if weapon.is_active:
                return
        self.__active_index = (self.__active_index + 1) % len(self.__weapons)

    def use_active_weapon(self, context: WeaponContext) -> None:
        self.active_weapon.use(context)

    def update_weapon(self, context: WeaponContext, delta_time: float) -> Iterator[WeaponEffect]:
        for weapon in self.__weapons:
            for effect in weapon.update_weapon(context, delta_time):
                yield effect

    def __repr__(self) -> str:
        weapon_names = ", ".join(type(weapon).__name__ for weapon in self.__weapons)
        return (
            f"WeaponController("
            f"active_index={self.__active_index}, "
            f"active_weapon={type(self.active_weapon).__name__}, "
            f"weapons=[{weapon_names}]"
            ")"
        )
