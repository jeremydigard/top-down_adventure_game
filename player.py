import arcade
from collections.abc import Mapping
from enum import Enum, auto
from types import MappingProxyType
from typing import Final
from textures import *
from constants import *
from math import sqrt


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()

# Déterminer la direction visuelle (priorité : DOWN < UP < LEFT < RIGHT)
PRIORITY: Final[tuple[Direction, ...]] = (Direction.DOWN, Direction.UP, Direction.LEFT, Direction.RIGHT)


KEY_TO_DIRECTION: Final[Mapping[int, Direction]] = {
    arcade.key.UP: Direction.UP,
    arcade.key.DOWN: Direction.DOWN,
    arcade.key.LEFT: Direction.LEFT,
    arcade.key.RIGHT: Direction.RIGHT,
}

DIRECTION_DATA: Final[Mapping[Direction, tuple[float, float, arcade.TextureAnimation, arcade.TextureAnimation]]] = MappingProxyType({
    #                              dx   dy   run_animation              idle_animation
    Direction.UP:    ( 0, +PLAYER_MOVEMENT_SPEED, ANIMATION_PLAYER_RUN_UP,    ANIMATION_PLAYER_IDLE_UP),
    Direction.DOWN:  ( 0, -PLAYER_MOVEMENT_SPEED, ANIMATION_PLAYER_RUN_DOWN,  ANIMATION_PLAYER_IDLE_DOWN),
    Direction.LEFT:  (-PLAYER_MOVEMENT_SPEED, 0,  ANIMATION_PLAYER_RUN_LEFT,  ANIMATION_PLAYER_IDLE_LEFT),
    Direction.RIGHT: (+PLAYER_MOVEMENT_SPEED, 0,  ANIMATION_PLAYER_RUN_RIGHT, ANIMATION_PLAYER_IDLE_RIGHT),
})

class Player(arcade.TextureAnimationSprite):
    __direction: Direction
    __directions_pressed: set[Direction]

    def __init__(
        self,
        center_x: int,
        center_y: int,
        scale : float,
    ) -> None:

        super().__init__(animation=ANIMATION_PLAYER_IDLE_DOWN, center_x=center_x, center_y=center_y, scale=scale)
        self.__direction = Direction.DOWN
        self.__directions_pressed = set()

    @property
    def direction(self) -> Direction:
        return self.__direction

    def handle_direction_key_press(self, direction: Direction) -> None:
        self.__directions_pressed.add(direction)
        self.__update_movement()


    def handle_direction_key_release(self, direction: Direction) -> None:
        self.__directions_pressed.discard(direction)
        self.__update_movement()

    def __update_movement(self) -> None:
        """Recalcule vitesse + animation en fonction de toutes les directions pressées."""

        # Reset vitesses
        self.change_x = 0
        self.change_y = 0

        for d in self.__directions_pressed:
            dx, dy, _, _ = DIRECTION_DATA[d]
            self.change_x += dx
            self.change_y += dy

        if self.change_x != 0 and self.change_y != 0:
            self.change_x /= sqrt(2)
            self.change_y /= sqrt(2)
        for d in PRIORITY:
            if d in self.__directions_pressed:
                self.__direction = d
                break
        # Si rien n'est pressé : self.direction reste inchangée (comportement voulu)

        # Choisir l'animation
        is_moving = (self.change_x != 0 or self.change_y != 0)
        _, _, run_anim, idle_anim = DIRECTION_DATA[self.__direction]
        nouvelle_animation = run_anim if is_moving else idle_anim
        if self.animation != nouvelle_animation:
            self.animation = nouvelle_animation

    def update(self, delta_time: float = 1/60, *args : object, **kwargs : object) -> None:
        self.__update_movement()

    def __repr__(self) -> str:
        pressed = ", ".join(direction.name for direction in sorted(self.__directions_pressed, key=PRIORITY.index))
        return (
            f"Player("
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"direction={self.__direction.name}, "
            f"velocity=({self.change_x:.1f}, {self.change_y:.1f}), "
            f"pressed=[{pressed}]"
            ")"
        )
