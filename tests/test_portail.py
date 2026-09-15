from __future__ import annotations

from map_config import AndCondition, NotCondition, OrCondition, SwitchIsOnCondition
from portail import Gate, Lever
from textures import GATE_TEXTURES, LEVER_TEXTURES


def test_lever_switch_state_toggles_state_and_texture() -> None:
    """
    Teste que switch_state bascule l'état du levier et met à jour sa texture
    """
    lever = Lever(center_x=10, center_y=20, scale=1.0, id="a")

    assert lever.state is False
    assert lever.texture == LEVER_TEXTURES[False]

    lever.switch_state()

    assert lever.state is True
    assert lever.texture == LEVER_TEXTURES[True]

    lever.switch_state()

    assert lever.state is False
    assert lever.texture == LEVER_TEXTURES[False]


def test_gate_update_state_follows_simple_switch_condition() -> None:
    """
    Teste que update_state d'une porte suit correctement une condition simple de levier
    """
    gate = Gate(
        center_x=10,
        center_y=20,
        scale=1.0,
        open_conditions=SwitchIsOnCondition("a"),
    )

    assert gate.is_closed is True
    assert gate.texture == GATE_TEXTURES[False]

    changed = gate.update_state({"a": False})
    assert changed is False
    assert gate.is_closed is True
    assert gate.texture == GATE_TEXTURES[False]

    changed = gate.update_state({"a": True})
    assert changed is True
    assert gate.is_open is True
    assert gate.texture == GATE_TEXTURES[True]

    changed = gate.update_state({"a": True})
    assert changed is False


def test_gate_update_state_supports_nested_conditions() -> None:
    """
    Teste que update_state d'une porte supporte les conditions imbriquées (ET, OU, NON)
    """
    condition = AndCondition(
        (
            SwitchIsOnCondition("a"),
            NotCondition(SwitchIsOnCondition("b")),
            OrCondition(
                (
                    SwitchIsOnCondition("c"),
                    SwitchIsOnCondition("d"),
                )
            ),
        )
    )
    gate = Gate(center_x=0, center_y=0, scale=1.0, open_conditions=condition)

    assert gate.update_state({"a": True, "b": False, "c": False, "d": True}) is True
    assert gate.is_open is True

    assert gate.update_state({"a": True, "b": False, "c": False, "d": True}) is False


def test_gate_update_state_raises_for_unknown_switch() -> None:
    """
    Teste que update_state d'une porte lève une exception si un levier référencé n'existe pas
    """
    gate = Gate(
        center_x=0,
        center_y=0,
        scale=1.0,
        open_conditions=SwitchIsOnCondition("missing"),
    )

    try:
        gate.update_state({})
    except ValueError as error:
        assert "missing" in str(error)
    else:
        raise AssertionError("Expected ValueError")
