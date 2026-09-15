
import arcade
from collections.abc import Mapping
from typing import Final

from textures import (
    LEVER_TEXTURES,
    GATE_TEXTURES
)
from map_config import GateCondition, evaluate_gate_condition


class Lever(arcade.Sprite): # ca n'a pas de sens de définir les leviers icis 
    """
    Leviers utilisés pour ouvrir ou fermer les portails.
    Utilisations de bools pour indiquer leur état: on -> True, off -> False
    """
    id : Final[str]
    __state: bool

    def __init__(self, center_x: float, center_y: float, scale: float, id: str, state: bool = False) -> None:
        super().__init__(LEVER_TEXTURES[state], scale=scale, center_x=center_x, center_y=center_y)

        self.id = id
        self.__state = state

    @property
    def state(self) -> bool:
        return self.__state

    def switch_state(self) -> None:
        self.__state = not self.__state
        self.texture = LEVER_TEXTURES[self.__state]

    def __repr__(self) -> str:
        return (
            f"Lever("
            f"id={self.id!r}, "
            f"state={self.__state}, "
            f"center=({self.center_x:.1f}, {self.center_y:.1f})"
            ")"
        )


class Gate(arcade.Sprite):
    """
    Portails, qui peuvent être ouverts ou fermés dépendant des états des leviers et
    des paramètres prédéfinis de la map (conditions d'ouverture).
    """
    open_conditions: Final[GateCondition]
    __is_open: bool

    def __init__(self, center_x: float, center_y: float, scale: float, open_conditions: GateCondition) -> None:
        super().__init__(GATE_TEXTURES[False], scale=scale, center_x=center_x, center_y=center_y)

        self.__is_open = False
        self.open_conditions = open_conditions

    @property
    def is_open(self) -> bool:
        return self.__is_open

    @property
    def is_closed(self) -> bool:
        return not self.__is_open

    def _set_open(self, is_open: bool) -> None:
        self.__is_open = is_open
        self.texture = GATE_TEXTURES[self.__is_open]


    def update_state(self, lever_states: Mapping[str, bool]) -> bool:
        """
        Fonction appelée par le gameview.
        Lance la vérification de l'état que devrait avoir le portail.
        Si l'état calculé est différent de l'état actuel, le changement est effectué.
        Renvoie True ssi l'état est changé.
        """
        should_be_open = evaluate_gate_condition(self.open_conditions, lever_states)
        if should_be_open != self.is_open:
            self._set_open(should_be_open)
            return True

        return False

    def __repr__(self) -> str:
        return (
            f"Gate("
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"is_open={self.__is_open}, "
            f"open_conditions={self.open_conditions!r}"
            ")"
        )
