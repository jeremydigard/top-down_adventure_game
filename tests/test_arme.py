from collections.abc import Sequence
from textwrap import dedent

import arcade
import pytest

from arme import (
    Boomerang,
    BoomerangState,
    CollectCrystal,
    Epee,
    HitTarget,
    ToggleLever,
    WeaponContext,
    WeaponEffect,
)
from constants import (
    BOOMERANG_COOLDOWN,
    BOOMERANG_MOVEMENT_SPEED,
    SCALE,
    SECONDS_PER_FRAME,
    SWORD_COOLDOWN,
    SWORD_R,
    TILE_SIZE,
)
from gameview import GameView
from helper import grid_to_pixels
from player import Direction, Player
from portail import Lever
from weapon_hittable import WeaponHittable


class HittableSprite(arcade.SpriteSolidColor, WeaponHittable): # c quoi ce truc 
    def __init__(self, center_x: float, center_y: float) -> None:
        super().__init__(TILE_SIZE // 4, TILE_SIZE // 4, arcade.color.RED)
        self.center_x = center_x
        self.center_y = center_y
        self.hit_count = 0

    def on_weapon_hit(self) -> None:
        self.hit_count += 1


def make_player(direction: Direction = Direction.RIGHT) -> Player:
    player = Player(center_x=grid_to_pixels(3), center_y=grid_to_pixels(3), scale=SCALE)
    if direction != Direction.DOWN:
        player.handle_direction_key_press(direction)
        player.handle_direction_key_release(direction)
    return player


def sprite_list(*sprites: arcade.Sprite) -> arcade.SpriteList:
    sprites_list = arcade.SpriteList()
    for sprite in sprites:
        sprites_list.append(sprite)
    return sprites_list


def make_context(
    player: Player,
    *, # c quoi cette * 
    walls: arcade.SpriteList | None = None,
    mobs: arcade.SpriteList | None = None,
    levers: arcade.SpriteList | None = None,
    crystals: arcade.SpriteList | None = None,
) -> WeaponContext:
    return WeaponContext(
        player=player,
        walls=walls if walls is not None else arcade.SpriteList(),
        mobs=mobs if mobs is not None else arcade.SpriteList(),
        levers=levers if levers is not None else arcade.SpriteList(),
        crystals=crystals if crystals is not None else arcade.SpriteList(),
    )


def make_solid_sprite(center_x: float, center_y: float, size: int = TILE_SIZE // 2) -> arcade.Sprite:
    sprite = arcade.SpriteSolidColor(size, size, arcade.color.WHITE) # pq on a besoin de ces couleurs 
    sprite.center_x = center_x
    sprite.center_y = center_y
    return sprite


def update_n_times(weapon: Boomerang | Epee, context: WeaponContext, frame_count: int) -> list[WeaponEffect]:
    effects: list[WeaponEffect] = []
    for _ in range(frame_count):
        effects.extend(weapon.update_weapon(context, SECONDS_PER_FRAME))
    return effects


def assert_single_hit_target(effects: Sequence[WeaponEffect], target: HittableSprite) -> None:

    assert len(effects) == 1
    match effects[0]:
        case HitTarget(target=hit_target):
            assert hit_target is target
        case _:
            pytest.fail(f"Unexpected weapon effect: {effects[0]!r}")


def test_boomerang_starts_inactive_and_has_one_hidden_sprite() -> None:
    boomerang = Boomerang()

    assert boomerang.state == BoomerangState.INACTIVE
    assert not boomerang.is_active
    assert not boomerang.locks_player
    assert len(boomerang.sprites) == 1
    assert not boomerang.visible


def test_boomerang_launches_in_player_direction() -> None:
    player = make_player(Direction.RIGHT)
    context = make_context(player)
    boomerang = Boomerang()

    boomerang.use(context)

    assert boomerang.state == BoomerangState.LAUNCHING
    assert boomerang.visible
    assert boomerang.position == player.position
    assert boomerang.change_x == BOOMERANG_MOVEMENT_SPEED
    assert boomerang.change_y == 0


def test_boomerang_returns_after_max_distance_and_respects_cooldown() -> None:
    player = make_player(Direction.RIGHT)
    context = make_context(player)
    boomerang = Boomerang()

    boomerang.use(context)
    update_n_times(boomerang, context, 33)
    assert boomerang.state == BoomerangState.RETURNING

    update_n_times(boomerang, context, 32)
    assert boomerang.state == BoomerangState.INACTIVE
    assert not boomerang.visible

    boomerang.use(context)
    assert not boomerang.is_active

    update_n_times(boomerang, context, BOOMERANG_COOLDOWN)
    boomerang.use(context)
    assert boomerang.is_active


def test_boomerang_returns_when_it_hits_a_wall() -> None:
    player = make_player(Direction.RIGHT)
    wall = make_solid_sprite(player.center_x + BOOMERANG_MOVEMENT_SPEED, player.center_y)
    context = make_context(player, walls=sprite_list(wall))
    boomerang = Boomerang()

    boomerang.use(context)
    effects = list(boomerang.update_weapon(context, SECONDS_PER_FRAME))

    assert effects == []
    assert boomerang.state == BoomerangState.RETURNING


def test_boomerang_hits_target_and_starts_returning() -> None:
    player = make_player(Direction.RIGHT)
    target = HittableSprite(player.center_x + BOOMERANG_MOVEMENT_SPEED, player.center_y)
    context = make_context(player, mobs=sprite_list(target))
    boomerang = Boomerang()

    boomerang.use(context)
    effects = list(boomerang.update_weapon(context, SECONDS_PER_FRAME))

    assert_single_hit_target(effects, target)
    assert boomerang.state == BoomerangState.RETURNING


def test_sword_starts_hidden_and_locks_player_only_while_active() -> None:
    player = make_player(Direction.RIGHT)
    context = make_context(player)
    sword = Epee()

    assert not sword.is_active
    assert not sword.locks_player
    assert not sword.visible

    sword.use(context)
    assert sword.is_active
    assert sword.locks_player
    assert sword.visible
    assert not player.visible

    update_n_times(sword, context, 25)
    assert not sword.is_active
    assert not sword.locks_player
    assert not sword.visible
    assert player.visible


def test_sword_respects_cooldown_after_attack() -> None:
    player = make_player(Direction.RIGHT)
    context = make_context(player)
    sword = Epee()

    sword.use(context)
    update_n_times(sword, context, 25)

    sword.use(context)
    assert not sword.is_active

    update_n_times(sword, context, SWORD_COOLDOWN)
    sword.use(context)
    assert sword.is_active


def test_sword_hits_only_targets_in_attack_direction() -> None:
    player = make_player(Direction.RIGHT)
    target_in_front = HittableSprite(player.center_x + SWORD_R / 2, player.center_y)
    target_behind = HittableSprite(player.center_x - TILE_SIZE, player.center_y)
    context = make_context(player, mobs=sprite_list(target_in_front, target_behind))
    sword = Epee()

    sword.use(context)
    effects = list(sword.update_weapon(context, SECONDS_PER_FRAME))

    assert_single_hit_target(effects, target_in_front)


def test_sword_collects_crystal_in_attack_direction() -> None:
    player = make_player(Direction.RIGHT)
    crystal = make_solid_sprite(player.center_x + SWORD_R / 2, player.center_y, size=TILE_SIZE // 4)
    context = make_context(player, crystals=sprite_list(crystal))
    sword = Epee()

    sword.use(context)
    effects = list(sword.update_weapon(context, SECONDS_PER_FRAME))

    assert len(effects) == 1
    match effects[0]:
        case CollectCrystal(crystal=collected):
            assert collected is crystal
        case _:
            pytest.fail(f"Unexpected weapon effect: {effects[0]!r}")


def test_sword_toggles_each_lever_once_per_attack() -> None:
    player = make_player(Direction.RIGHT)
    lever = Lever(player.center_x + SWORD_R / 2, player.center_y, SCALE, "a")
    context = make_context(player, levers=sprite_list(lever))
    sword = Epee()

    sword.use(context)
    first_effects = list(sword.update_weapon(context, SECONDS_PER_FRAME))
    second_effects = list(sword.update_weapon(context, SECONDS_PER_FRAME))

    assert len(first_effects) == 1
    match first_effects[0]:
        case ToggleLever(lever=hit_lever):
            assert hit_lever is lever
        case _:
            pytest.fail(f"Unexpected weapon effect: {first_effects[0]!r}")
    assert second_effects == []


def test_gameview_from_string_builds_a_playable_weapon_world(window: arcade.Window) -> None:
    view = GameView.from_string(dedent("""\
        width: 3
        height: 3
        ---
        xxx
        xPx
        xxx
        ---"""))
    window.show_view(view)

    assert view.world.active_weapon is view.world.boomerang
    assert view.world.boomerang.sprite in view.world.weapons
    assert view.world.epee.sprite in view.world.weapons


def test_gameview_keyboard_attack_applies_weapon_effects(window: arcade.Window) -> None:
    view = GameView.from_string(dedent("""\
        width: 6
        height: 3
        ---
        xxxxxx
        xPs  x
        xxxxxx
        ---"""))
    window.show_view(view)

    view.on_key_press(arcade.key.R, 0)
    view.on_key_press(arcade.key.RIGHT, 0)
    window.test(2)
    view.on_key_release(arcade.key.RIGHT, 0)
    view.on_key_press(arcade.key.D, 0)
    window.test(1)

    assert len(view.world.mobs) == 0


def test_gameview_attack_uses_direction_changed_in_same_frame(window: arcade.Window) -> None:
    view = GameView.from_string(dedent("""\
        width: 11
        height: 11
        ---
        xxxxxxxxxxx
        x         x
        x         x
        x         x
        x         x
        x    P    x
        x         x
        x         x
        x         x
        x         x
        xxxxxxxxxxx
        ---"""))
    window.show_view(view)

    view.on_key_press(arcade.key.RIGHT, 0)
    view.on_key_press(arcade.key.D, 0)

    assert view.world.boomerang.change_x == BOOMERANG_MOVEMENT_SPEED
    assert view.world.boomerang.change_y == 0
