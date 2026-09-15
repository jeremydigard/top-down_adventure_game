from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, assert_never

import yaml

from helper import Tile


class InvalidMapFileException(Exception):
    pass


type YamlValue = str | int | bool | list[YamlValue] | dict[str, YamlValue] | None
type YamlMapping = dict[str, YamlValue]

@dataclass(frozen=True)
class SwitchIsOnCondition:
    switch_id: str

@dataclass(frozen=True)
class AndCondition:
    conditions: tuple[GateCondition, ...]

@dataclass(frozen=True)
class OrCondition:
    conditions: tuple[GateCondition, ...]

@dataclass(frozen=True)
class NotCondition:
    condition: GateCondition

type GateCondition = SwitchIsOnCondition | NotCondition | AndCondition | OrCondition

@dataclass(frozen=True)
class SwitchData:
    id: str
    x: Tile
    y: Tile
    state: bool= False

@dataclass(frozen=True)
class GateData:
    x: Tile
    y: Tile
    open_if: GateCondition

@dataclass(frozen=True)
class MapConfig:
    width: int
    height: int
    switches: tuple[SwitchData, ...]
    gates: tuple[GateData, ...]
    next_map: str | None


REQUIRED_YAML_KEYS: Final[frozenset[str]] = frozenset({"width", "height"})
OPTIONAL_YAML_KEYS: Final[frozenset[str]] = frozenset({"switches", "gates", "next_map"})
YAML_KEYS: Final[frozenset[str]] = REQUIRED_YAML_KEYS | OPTIONAL_YAML_KEYS
SWITCH_KEYS: Final[frozenset[str]] = frozenset({"id", "x", "y", "state"})
GATE_KEYS: Final[frozenset[str]] = frozenset({"x", "y", "open_if"})


class UniqueKeyLoader(yaml.SafeLoader): # pas de underscore pour le nom
    """
    Loader PyYAML qui refuse les clés dupliquées au lieu de garder silencieusement
    la dernière valeur, ce qui masquerait des erreurs dans la config de map.
    """
    def construct_mapping(self, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[object, object]:
        match node:
            case yaml.nodes.MappingNode():
                pass
            case _:
                raise InvalidMapFileException("Le YAML contient un noeud invalide.")

        mapping: dict[object, object] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                is_duplicate: bool = key in mapping
            except TypeError as error:
                raise InvalidMapFileException("Les clés YAML doivent être hashables.") from error

            if is_duplicate:
                raise InvalidMapFileException(f"Le YAML contient une clé dupliquée: {key!r}.")

            mapping[key] = self.construct_object(value_node, deep=deep)

        return mapping


def _load_yaml(yaml_str: str) -> object:
    """
    Charge le YAML brut en objets Python, sans encore valider le schéma métier.
    La seule validation faite ici est syntaxique, avec le refus des clés dupliquées.
    """
    try:
        return yaml.load(yaml_str, Loader=UniqueKeyLoader)
    except yaml.YAMLError as error:
        raise InvalidMapFileException(f"Erreur de lecture du YAML: {error}") from error


def _normalize_yaml_value(value: object, path: str) -> YamlValue:
    """
    Ramène les objets quelconques produits par PyYAML dans le sous-ensemble de
    types que le parseur de config accepte ensuite.

    `path` garde une trace lisible de l'endroit où l'erreur a été trouvée.
    """
    match value:
        case str() | bool() | None:
            return value
        case int() as number if type(number) is int:
            return number
        case list() as values:
            return [_normalize_yaml_value(item, f"{path}[]") for item in values]
        case dict() as values:
            normalized: YamlMapping = {}
            for key, item in values.items():
                match key:
                    case str() as key_str:
                        normalized[key_str] = _normalize_yaml_value(item, f"{path}.{key_str}")
                    case _:
                        raise InvalidMapFileException(f"La clé YAML '{path}' doit être une string.")
            return normalized
        case _:
            raise InvalidMapFileException(f"Valeur YAML invalide à '{path}': {value}.")


def _require_mapping(value: YamlValue, path: str) -> YamlMapping:
    match value:
        case dict() as mapping:
            return mapping
        case _:
            raise InvalidMapFileException(f"La section '{path}' doit être un dictionnaire YAML.")


def _require_list(value: YamlValue, path: str) -> list[YamlValue]:
    match value:
        case list() as values:
            return values
        case _:
            raise InvalidMapFileException(f"La section '{path}' doit être une liste YAML.")


def _require_str(value: YamlValue, path: str) -> str:
    match value:
        case str() as text:
            return text
        case _:
            raise InvalidMapFileException(f"La valeur '{path}' doit être une string.")


def _require_int(value: YamlValue, path: str) -> int:
    match value:
        case int() as number if type(number) is int:
            return number
        case _:
            raise InvalidMapFileException(f"La valeur '{path}' doit être un nombre entier.")


def _require_bool(value: YamlValue, path: str) -> bool:
    match value:
        case bool() as boolean:
            return boolean
        case _:
            raise InvalidMapFileException(f"La valeur '{path}' doit être un booléen.")



def _parse_next_map(value: YamlValue, path: str) -> str:
    next_map = _require_str(value, path)
    if next_map == "":
        raise InvalidMapFileException("La valeur 'next_map' ne peut pas être vide.")
    return next_map


def _reject_unknown_keys(mapping: Mapping[str, YamlValue], allowed_keys: frozenset[str], path: str) -> None:
    unknown_keys = set(mapping) - allowed_keys
    if unknown_keys:
        unknown_key = sorted(unknown_keys)[0]
        raise InvalidMapFileException(f"Clé inconnue dans '{path}': {unknown_key}.")


def _parse_condition(value: YamlValue, path: str) -> GateCondition:
    """
    Parse récursivement l'arbre logique d'ouverture d'un portail.
    Chaque niveau doit contenir un seul connecteur: switch_is_on, not, and ou or.
    """
    condition_data = _require_mapping(value, path)
    if len(condition_data) != 1:
        raise InvalidMapFileException(
            f"La condition '{path}' doit contenir exactement un connecteur logique."
        )

    match condition_data:
        case {"switch_is_on": str(switch_id)}:
            return SwitchIsOnCondition(switch_id)

        case {"not": list() as subconditions}:
            if len(subconditions) != 1:
                raise InvalidMapFileException(f"La condition '{path}.not' doit contenir une seule condition.")
            return NotCondition(_parse_condition(subconditions[0], f"{path}.not[0]"))

        case {"and": list() as subconditions}:
            if not subconditions:
                raise InvalidMapFileException(f"La condition '{path}.and' doit contenir au moins une condition.")
            return AndCondition(tuple(
                _parse_condition(condition, f"{path}.and[{index}]")
                for index, condition in enumerate(subconditions)
            ))

        case {"or": list() as subconditions}:
            if not subconditions:
                raise InvalidMapFileException(f"La condition '{path}.or' doit contenir au moins une condition.")
            return OrCondition(tuple(
                _parse_condition(condition, f"{path}.or[{index}]")
                for index, condition in enumerate(subconditions)
            ))

        case {"switch_is_on": _}:
            raise InvalidMapFileException(f"La valeur '{path}.switch_is_on' doit être une string.")
        case {"not": _}:
            raise InvalidMapFileException(f"La section '{path}.not' doit être une liste YAML.")
        case {"and": _}:
            raise InvalidMapFileException(f"La section '{path}.and' doit être une liste YAML.")
        case {"or": _}:
            raise InvalidMapFileException(f"La section '{path}.or' doit être une liste YAML.")
        case _:
            condition_type = next(iter(condition_data))
            raise InvalidMapFileException(f"Condition inconnue dans la config des portails: {condition_type}.")


def _condition_switch_ids(condition: GateCondition) -> tuple[str, ...]:
    """
    Extrait tous les IDs de leviers mentionnés dans une condition récursive,
    afin de vérifier ensuite qu'ils existent bien dans la config.
    """
    match condition:
        case SwitchIsOnCondition(switch_id=switch_id):
            return (switch_id,)
        case NotCondition(condition=subcondition):
            return _condition_switch_ids(subcondition)
        case AndCondition(conditions=subconditions) | OrCondition(conditions=subconditions):
            return tuple(
                switch_id
                for subcondition in subconditions
                for switch_id in _condition_switch_ids(subcondition)
            )
        case _:
            assert_never(condition)


def evaluate_gate_condition(condition: GateCondition, switch_states: Mapping[str, bool]) -> bool:
    """
    Évalue une condition de portail sans dépendre d'Arcade.

    Comme dans la correction, la logique métier reste dans le modèle pur; les
    sprites ne font ensuite que refléter l'état calculé.
    """
    match condition:
        case SwitchIsOnCondition(switch_id=switch_id):
            if switch_id not in switch_states:
                raise ValueError(f"Levier inconnu dans l'état des leviers: {switch_id}")
            return switch_states[switch_id]
        case NotCondition(condition=subcondition):
            return not evaluate_gate_condition(subcondition, switch_states)
        case AndCondition(conditions=subconditions):
            return all(evaluate_gate_condition(subcondition, switch_states) for subcondition in subconditions)
        case OrCondition(conditions=subconditions):
            return any(evaluate_gate_condition(subcondition, switch_states) for subcondition in subconditions)
        case _:
            assert_never(condition)


def gate_condition_to_yaml_value(condition: GateCondition) -> YamlMapping:
    """
    Convertit une condition typée en structure YAML canonique.

    Cette fonction sert à sérialiser les maps sans faire dépendre `Map.__repr__`
    des détails de chaque sous-classe de condition.
    """
    match condition:
        case SwitchIsOnCondition(switch_id=switch_id):
            return {"switch_is_on": switch_id}
        case NotCondition(condition=subcondition):
            return {"not": [gate_condition_to_yaml_value(subcondition)]}
        case AndCondition(conditions=subconditions):
            return {"and": [
                gate_condition_to_yaml_value(subcondition)
                for subcondition in subconditions
            ]}
        case OrCondition(conditions=subconditions):
            return {"or": [
                gate_condition_to_yaml_value(subcondition)
                for subcondition in subconditions
            ]}
        case _:
            assert_never(condition)


def _parse_switch(value: YamlValue, path: str) -> SwitchData:
    """
    Valide une entrée de `switches` et applique l'état par défaut du levier.
    """
    switch_data = _require_mapping(value, path)
    _reject_unknown_keys(switch_data, SWITCH_KEYS, path)

    for required_key in ("id", "x", "y"):
        if required_key not in switch_data:
            raise InvalidMapFileException(f"Le levier '{path}' ne contient pas la clé '{required_key}'.")

    state = _require_bool(switch_data["state"], f"{path}.state") if "state" in switch_data else False

    match switch_data:
        case {"id": str(switch_id), "x": int() as x, "y": int() as y} if type(x) is int and type(y) is int:
            return SwitchData(id=switch_id, x=x, y=y, state=state)
        case {"id": _, "x": _, "y": _}:
            raise InvalidMapFileException(f"Le levier '{path}' contient une valeur de mauvais type.")
        case _:
            raise InvalidMapFileException(f"Le levier '{path}' est invalide.")



def _parse_gate(value: YamlValue, path: str) -> GateData:
    """
    Valide une entrée de `gates` et transforme sa condition `open_if` en arbre typé.
    """
    gate_data = _require_mapping(value, path)
    _reject_unknown_keys(gate_data, GATE_KEYS, path)

    for required_key in ("x", "y", "open_if"):
        if required_key not in gate_data:
            raise InvalidMapFileException(f"Le portail '{path}' ne contient pas la clé '{required_key}'.")

    match gate_data:
        case {"x": int() as x, "y": int() as y, "open_if": open_if} if type(x) is int and type(y) is int:
            return GateData(x=x, y=y, open_if=_parse_condition(open_if, f"{path}.open_if"))
        case {"x": _, "y": _, "open_if": _}:
            raise InvalidMapFileException(f"Le portail '{path}' contient une valeur de mauvais type.")
        case _:
            raise InvalidMapFileException(f"Le portail '{path}' est invalide.")


def _validate_config_coords(x: Tile, y: Tile, width: int, height: int, label: str) -> None:
    if not (0 <= x < width and 0 <= y < height):
        raise InvalidMapFileException(f"{label} à ({x}, {y}) est hors des limites de la map.")


def parse_config(yaml_str: str) -> MapConfig:
    """
    Fonction qui orchestre le processing de la config de map.
    Transforme la configuration YAML non fiable en objets immuables et typés.

    Cette fonction est la frontière de confiance: après son retour, le reste du
    programme peut utiliser `MapConfig` sans manipuler de dictionnaires bruts.
    """
    normalized_yaml = _normalize_yaml_value(_load_yaml(yaml_str), "yaml")
    yaml_dict = _require_mapping(normalized_yaml, "yaml")

    # Première passe: forme générale de la config.
    _reject_unknown_keys(yaml_dict, YAML_KEYS, "yaml")

    for entry in REQUIRED_YAML_KEYS:
        if entry not in yaml_dict:
            raise InvalidMapFileException(f"Le fichier map ne contient pas la section '{entry}'")

    width = _require_int(yaml_dict["width"], "width")
    height = _require_int(yaml_dict["height"], "height")

    if width <= 0 or height <= 0:
        raise InvalidMapFileException("Les valeurs de 'width' et 'height' doivent strictement positifs.")

    # Deuxième passe: conversion des listes YAML vers les objets métier typés.
    switches = tuple(
        _parse_switch(switch, f"switches[{index}]")
        for index, switch in enumerate(_require_list(yaml_dict.get("switches", []), "switches"))
    )
    gates = tuple(
        _parse_gate(gate, f"gates[{index}]")
        for index, gate in enumerate(_require_list(yaml_dict.get("gates", []), "gates"))
    )
    next_map = None
    if "next_map" in yaml_dict:
        next_map = _parse_next_map(yaml_dict["next_map"], "next_map")

    switch_ids = {switch.id for switch in switches} # le set élimine les doublons d'ID
    if len(switch_ids) != len(switches):
        raise InvalidMapFileException("Deux leviers ne peuvent pas avoir le même ID.")

    # Dernière passe: validations qui dépendent de plusieurs sections à la fois.
    for switch in switches:
        _validate_config_coords(switch.x, switch.y, width, height, "Levier")

    for gate in gates:
        _validate_config_coords(gate.x, gate.y, width, height, "Portail")
        missing_ids = set(_condition_switch_ids(gate.open_if)) - switch_ids
        if missing_ids: # True si il y a un ID qui manque
            missing_id = sorted(missing_ids)[0]
            raise InvalidMapFileException(
                f"Le portail à ({gate.x}, {gate.y}) référence un levier inconnu: {missing_id}."
            )

    return MapConfig(width=width, height=height, switches=switches, gates=gates, next_map=next_map)
