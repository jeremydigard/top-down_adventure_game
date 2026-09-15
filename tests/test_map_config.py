from __future__ import annotations

from textwrap import dedent

import pytest

from map_config import (
    AndCondition,
    GateData,
    InvalidMapFileException,
    MapConfig,
    NotCondition,
    OrCondition,
    SwitchData,
    SwitchIsOnCondition,
    _load_yaml,
    evaluate_gate_condition,
    gate_condition_to_yaml_value,
    parse_config,
)


def test_parse_config_minimal_map() -> None:
    """
    Teste que parse_config peut traiter une
    carte minimale avec uniquement la largeur et la hauteur
    """
    config = parse_config(
        dedent("""\
            width: 3
            height: 2
            """),
    )

    assert config == MapConfig(
        width=3,
        height=2,
        switches=(),
        gates=(),
        next_map=None,
    )


def test_parse_config_with_switches_gates_and_next_map() -> None:
    """
    Teste que parse_config extrait correctement les leviers, les portes et la carte suivante
    """
    config = parse_config(
        dedent("""\
            width: 4
            height: 3
            next_map: next.txt
            switches:
              - id: a
                x: 1
                y: 0
                state: true
              - id: b
                x: 2
                y: 1
            gates:
              - x: 3
                y: 0
                open_if:
                  and:
                    - switch_is_on: a
                    - not:
                        - switch_is_on: b
            """),
    )

    assert config.switches == (
        SwitchData(id="a", x=1, y=0, state=True),
        SwitchData(id="b", x=2, y=1, state=False),
    )
    assert config.gates == (
        GateData(
            x=3,
            y=0,
            open_if=AndCondition(
                (
                    SwitchIsOnCondition("a"),
                    NotCondition(SwitchIsOnCondition("b")),
                )
            ),
        ),
    )
    assert config.next_map == "next.txt"


def test_evaluate_gate_condition_supports_nested_logic() -> None:
    """
    Teste que evaluate_gate_condition supporte la logique imbriquée (ET, OU, NON)
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

    assert evaluate_gate_condition(condition, {"a": True, "b": False, "c": False, "d": True}) is True
    assert evaluate_gate_condition(condition, {"a": True, "b": True, "c": False, "d": True}) is False


def test_gate_condition_to_yaml_value() -> None:
    """
    Teste que gate_condition_to_yaml_value convertit une condition en format YAML
    """
    condition = AndCondition(
        (
            SwitchIsOnCondition("a"),
            NotCondition(OrCondition((SwitchIsOnCondition("b"), SwitchIsOnCondition("c")))),
        )
    )

    assert gate_condition_to_yaml_value(condition) == {
        "and": [
            {"switch_is_on": "a"},
            {"not": [{"or": [{"switch_is_on": "b"}, {"switch_is_on": "c"}]}]},
        ]
    }


def test_parse_config_rejects_duplicate_switch_ids() -> None:
    """
    Teste que parse_config rejette les leviers avec des identifiants en doublon
    """
    with pytest.raises(InvalidMapFileException, match="même ID"):
        parse_config(
            dedent("""\
                width: 2
                height: 2
                switches:
                  - id: a
                    x: 0
                    y: 0
                  - id: a
                    x: 1
                    y: 1
                """),
        )


def test_parse_config_rejects_gate_reference_to_unknown_switch() -> None:
    """
    Teste que parse_config rejette une porte qui référence un levier inexistant
    """
    with pytest.raises(InvalidMapFileException, match="levier inconnu"):
        parse_config(
            dedent("""\
                width: 2
                height: 2
                switches:
                  - id: a
                    x: 0
                    y: 0
                gates:
                  - x: 1
                    y: 0
                    open_if:
                      switch_is_on: missing
                """),
        )


def test_parse_config_rejects_out_of_bounds_coordinates() -> None:
    """
    Teste que parse_config rejette les coordonnées des leviers en dehors des limites de la carte
    """
    with pytest.raises(InvalidMapFileException, match="hors des limites"):
        parse_config(
            dedent("""\
                width: 2
                height: 2
                switches:
                  - id: a
                    x: 2
                    y: 0
                """),
        )


def test_parse_config_rejects_empty_next_map() -> None:
    """
    Teste que parse_config rejette une valeur vide pour next_map
    """
    with pytest.raises(InvalidMapFileException, match="ne peut pas être vide"):
        parse_config(
            dedent("""\
                width: 1
                height: 1
                next_map: ""
                """),
        )


def test_load_yaml_rejects_duplicate_keys() -> None:
    """
    Teste que _load_yaml rejette les clés YAML dupliquées.
    """
    with pytest.raises(InvalidMapFileException, match="clé dupliquée"):
        _load_yaml(
            dedent("""\
                width: 1
                width: 2
                height: 1
                """),
        )


def test_evaluate_gate_condition_rejects_unknown_switch() -> None:
    """
    Teste que evaluate_gate_condition lève une exception si un levier référencé n'existe pas
    """
    with pytest.raises(ValueError, match="Levier inconnu"):
        evaluate_gate_condition(SwitchIsOnCondition("missing"), {})
