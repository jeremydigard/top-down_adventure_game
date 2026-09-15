import pytest

from constants import PLAYER_MOVEMENT_SPEED
from player import DIRECTION_DATA, Direction, Player


def test_direction_mapping_contains_expected_keys() -> None:
    assert DIRECTION_DATA[Direction.UP][0] == 0
    assert DIRECTION_DATA[Direction.DOWN][1] == -PLAYER_MOVEMENT_SPEED
    assert DIRECTION_DATA[Direction.LEFT][0] == -PLAYER_MOVEMENT_SPEED
    assert DIRECTION_DATA[Direction.RIGHT][0] == PLAYER_MOVEMENT_SPEED


def test_player_initial_state() -> None:
    player = Player(center_x=10, center_y=20, scale=1.0)

    assert player.center_x == 10
    assert player.center_y == 20
    assert player.direction == Direction.DOWN
    assert player.change_x == 0
    assert player.change_y == 0
    assert player.animation == DIRECTION_DATA[Direction.DOWN][3]


def test_player_key_press_updates_movement_immediately() -> None:
    player = Player(center_x=0, center_y=0, scale=1.0)

    player.handle_direction_key_press(Direction.RIGHT)

    assert player.change_x == PLAYER_MOVEMENT_SPEED
    assert player.change_y == 0
    assert player.direction == Direction.RIGHT
    assert player.animation == DIRECTION_DATA[Direction.RIGHT][2]


def test_player_update_diagonal_movement_is_normalized() -> None:
    player = Player(center_x=0, center_y=0, scale=1.0)
    player.handle_direction_key_press(Direction.RIGHT)
    player.handle_direction_key_press(Direction.UP)

    assert player.change_x == pytest.approx(PLAYER_MOVEMENT_SPEED / 2 ** 0.5)  
    assert player.change_y == pytest.approx(PLAYER_MOVEMENT_SPEED / 2 ** 0.5)
    assert player.direction == Direction.UP
    assert player.animation == DIRECTION_DATA[Direction.UP][2]


def test_player_update_idle_keeps_last_direction() -> None:
    player = Player(center_x=0, center_y=0, scale=1.0)
    player.handle_direction_key_press(Direction.LEFT)
    player.handle_direction_key_release(Direction.LEFT)

    assert player.direction == Direction.LEFT
    assert player.change_x == 0
    assert player.change_y == 0
    assert player.animation == DIRECTION_DATA[Direction.LEFT][3]


def test_player_update_keeps_state_consistent() -> None:
    player = Player(center_x=0, center_y=0, scale=1.0)
    player.handle_direction_key_press(Direction.UP)

    player.update()

    assert player.direction == Direction.UP
    assert player.change_x == 0
    assert player.change_y == PLAYER_MOVEMENT_SPEED
    assert player.animation == DIRECTION_DATA[Direction.UP][2]
