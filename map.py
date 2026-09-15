from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from types import MappingProxyType
from typing import Final
import yaml

from helper import Tile, TilePosition
from map_config import (
    GateData,
    InvalidMapFileException,
    MapConfig,
    SwitchData,
    gate_condition_to_yaml_value,
    parse_config,
)

class GridCell(Enum):
    GRASS = auto()
    BUISSON = auto() # renommer en mur ?
    CRYSTAL = auto()
    SPINNEUR_HORIZONTAL = auto()
    SPINNEUR_VERTICAL = auto()
    BAT = auto()
    TROU = auto()
    BLOB = auto()
    LEVER = auto()
    GATE = auto()
    EXIT = auto()

    @property
    def is_player_obstacle(self) -> bool:
        return self in {GridCell.BUISSON, GridCell.GATE}  # seulement fermé dynamiquement côté sprite
    @property
    def is_blob_nav_obstacle(self) -> bool:
        return self in {GridCell.BUISSON, GridCell.TROU, GridCell.GATE}
    @property
    def is_static_sight_blocker(self) -> bool:
        return self == GridCell.BUISSON

    @property
    def blocks_spinner(self) -> bool:
        # GridCell mélange terrain et entités posées sur le terrain.
        # Pour les spinners, on encode donc la règle métier "bloque-t-il ?"
        # plutôt que "est-ce littéralement de l'herbe ?".
        return self in {GridCell.BUISSON, GridCell.TROU, GridCell.GATE}

type Matrix = tuple[tuple[GridCell, ...], ...]

PLAYER_SYMBOL: Final[str] = "P"
EXIT_SYMBOL: Final[str] = "E"
SECTION_SEPARATOR: Final[str] = "---"


SYMBOL_TO_GRIDCELL: Final[Mapping[str, GridCell]] = MappingProxyType({
    " ": GridCell.GRASS,
    "x": GridCell.BUISSON,
    "*": GridCell.CRYSTAL,
    "s": GridCell.SPINNEUR_HORIZONTAL,
    "S": GridCell.SPINNEUR_VERTICAL,
    "v": GridCell.BAT,
    "O": GridCell.TROU,
    "b": GridCell.BLOB,
    "^": GridCell.LEVER,
    "|": GridCell.GATE,
    EXIT_SYMBOL: GridCell.EXIT,
})

GRIDCELL_TO_SYMBOL: Final[Mapping[GridCell, str]] = MappingProxyType({
    gridcell: symbol for symbol, gridcell in SYMBOL_TO_GRIDCELL.items()
})

@dataclass(frozen=True)
class _MapMetadata:
    width: int
    height: int
    switches_by_coords: Mapping[TilePosition, SwitchData]
    gates_by_coords: Mapping[TilePosition, GateData]
    next_map: str | None


@dataclass(frozen=True)
class _MapFullData:
    metadata: _MapMetadata
    player_start_x: Tile
    player_start_y: Tile
    exit_coords: TilePosition | None
    matrix: Matrix


def _read_text_file(path: str) -> str:
    """
    Lit le contenu d'un fichier texte à partir d'un chemin donné

    Vérifie que le fichier possède bien l'extension .txt et gère les erreurs
    d'entrée/sortie en les encapsulant dans une InvalidMapFileException

    Args:
        path: Le chemin vers le fichier de carte
    """
    file_path = Path(path)

    if file_path.suffix != ".txt":
        raise InvalidMapFileException("Le fichier doit être en format .txt")

    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise InvalidMapFileException(f"Le fichier de carte '{path}' n'existe pas.") from error
    except OSError as error:
        raise InvalidMapFileException(f"Incapable de lire le fichier de carte '{path}'.") from error


def _split_sections(raw: str) -> tuple[str, list[str]]:
    """
    Sépare le contenu du fichier en deux sections
    Le format attendu utilise "---" comme séparateur

    Sortie:
        Un tuple contenant deux strings (lignes de YAML, lignes des symboles de la map)
    """
    if not raw.strip():
        raise InvalidMapFileException("Le fichier map est vide.")

    lines = raw.splitlines()
    separators = [i for i, line in enumerate(lines) if line == SECTION_SEPARATOR]

    if len(separators) != 2:
        raise InvalidMapFileException("Le fichier map doit contenir exactement deux séparateurs '---'.")

    first, second = separators

    if second != len(lines) - 1:
        raise InvalidMapFileException("Le dernier séparateur '---' doit être à la fin du fichier.")

    YAML_text = "\n".join(lines[:first])
    grid_lines = lines[first + 1:second]
    return YAML_text, grid_lines


def _build_metadata(config: MapConfig) -> _MapMetadata:
    """
    Construit l'objet de métadonnées contenant toute les infos traitées du texte YAML.
    S'assure les dimensions sont correctement écrites.
    """
    switches_by_coords: dict[TilePosition, SwitchData] = {}
    for switch in config.switches:
        switch_coords: TilePosition = (switch.x, switch.y)
        if switch_coords in switches_by_coords:
            raise InvalidMapFileException(f"Deux leviers sont configurés à la coordonnée {switch_coords}.")
        switches_by_coords[switch_coords] = switch

    gates_by_coords: dict[TilePosition, GateData] = {}
    for gate in config.gates:
        gate_coords: TilePosition = (gate.x, gate.y)
        if gate_coords in gates_by_coords:
            raise InvalidMapFileException(f"Deux portails sont configurés à la coordonnée {gate_coords}.")
        gates_by_coords[gate_coords] = gate

    return _MapMetadata(
        width=config.width,
        height=config.height,
        switches_by_coords=MappingProxyType(switches_by_coords),
        gates_by_coords=MappingProxyType(gates_by_coords),
        next_map=config.next_map,
    )


def _validate_grid_shape(grid_lines: list[str], metadata: _MapMetadata) -> None:
    """
    Vérifie que la forme de la grille textuelle correspond aux dimensions
    déclarées dans la première section (largeur et hauteur)
    """
    if len(grid_lines) != metadata.height:
        raise InvalidMapFileException(
            f"La map doit contenir exactement {metadata.height} lignes de symboles."
        )

    for line in grid_lines:
        if len(line) > metadata.width:
            raise InvalidMapFileException(
                "Une ligne de la map contient plus de caractères que la largeur déclarée."
            )


def _decode_grid(grid_lines: list[str], metadata: _MapMetadata) -> _MapFullData:
    """
    Transforme les caractères de la grille en une matrice d'énumérations GridCell.

    Localise également la position de départ unique du joueur ('P')

    On inverse l'ordre des lignes (`reversed`) pour que l'index [0][0] de la matrice
    corresponde au coin inférieur gauche (coordonnées cartésiennes)
    """
    rows: list[tuple[GridCell, ...]] = []
    player_start_x: Tile | None = None
    player_start_y: Tile | None = None
    exit_coords: TilePosition | None = None

    for y, line in enumerate(reversed(grid_lines)):
        row: list[GridCell] = []

        for x, char in enumerate(line):
            match char:
                case "P":
                    if player_start_x is not None:
                        raise InvalidMapFileException(
                            "La map doit contenir uniquement un player représenté par 'P'."
                        )
                    player_start_x = x
                    player_start_y = y
                    row.append(GridCell.GRASS)

                case "E":
                    if exit_coords is not None:
                        raise InvalidMapFileException("La map doit contenir au plus une sortie représentée par 'E'.")
                    exit_coords = (x, y)
                    row.append(GridCell.EXIT)

                case _:
                    cell = SYMBOL_TO_GRIDCELL.get(char)
                    if cell is None:
                        raise InvalidMapFileException(f"Invalid character {char!r} in map grid.")
                    row.append(cell)

        missing_cells = metadata.width - len(line)
        row.extend([GridCell.GRASS] * missing_cells)
        rows.append(tuple(row))

    if player_start_x is None or player_start_y is None:
        raise InvalidMapFileException(
            "La map doit contenir un player représenté par le caractère 'P'."
        )

    # Le changement de map est opt-in: `next_map` et la sortie `E` doivent
    # apparaître ensemble, afin de ne pas changer le format canonique par accident.
    if metadata.next_map is None and exit_coords is not None:
        raise InvalidMapFileException("Une sortie 'E' doit être accompagnée d'un champ 'next_map'.")
    if metadata.next_map is not None and exit_coords is None:
        raise InvalidMapFileException("Le champ 'next_map' requiert une sortie 'E' dans la grille.")

    return _MapFullData(
        metadata=metadata,
        player_start_x=player_start_x,
        player_start_y=player_start_y,
        exit_coords=exit_coords,
        matrix=tuple(rows),
    )


def _validate_config_matches_grid(map_data: _MapFullData) -> None:
    """
    Vérifie les invariants qui demandent à connaître à la fois la grille et la
    config YAML.

    Après cette fonction, le reste du programme peut supposer qu'un symbole '^'
    possède une entrée `SwitchData`, et qu'un symbole '|' possède une `GateData`.
    """
    matrix = map_data.matrix
    metadata = map_data.metadata

    for switch_coords in metadata.switches_by_coords:
        x, y = switch_coords
        if matrix[y][x] != GridCell.LEVER:
            raise InvalidMapFileException(
                f"Le levier configuré à ({x}, {y}) ne correspond pas à un symbole '^' dans la grille."
            )

    for gate_coords in metadata.gates_by_coords:
        x, y = gate_coords
        if matrix[y][x] != GridCell.GATE:
            raise InvalidMapFileException(
                f"Le portail configuré à ({x}, {y}) ne correspond pas à un symbole '|' dans la grille."
            )

    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            match cell:
                case GridCell.LEVER if (x, y) not in metadata.switches_by_coords:
                    raise InvalidMapFileException(f"Levier '^' à ({x}, {y}) absent de la config.")
                case GridCell.GATE if (x, y) not in metadata.gates_by_coords:
                    raise InvalidMapFileException(f"Portail '|' à ({x}, {y}) absent de la config.")
                case _:
                    pass


def _parse_map_text(raw: str) -> _MapFullData:
    """
    Orchestre le pipeline complet d'analyse du texte de la carte

    Enchaîne : découpage -> lecture du YAML -> construction métadonnées ->
    validation de forme -> décodage de la grille
    """
    YAML_str, grid_lines = _split_sections(raw)

    config = parse_config(YAML_str)
    metadata = _build_metadata(config)

    _validate_grid_shape(grid_lines, metadata)
    map_data = _decode_grid(grid_lines, metadata)
    _validate_config_matches_grid(map_data)
    return map_data


def _empty_metadata(width: int, height: int) -> _MapMetadata:
    return _MapMetadata(
        width=width,
        height=height,
        switches_by_coords=MappingProxyType({}),
        gates_by_coords=MappingProxyType({}),
        next_map=None,
    )


class Map:
    """ Représente la structure logique et immuable du monde du jeu """
    __matrix: Final[Matrix]
    width: Final[int]
    height: Final[int]
    player_start_x: Final[Tile]
    player_start_y: Final[Tile]
    exit_coords: Final[TilePosition | None]
    next_map: Final[str | None]
    switch_by_coords: Final[Mapping[TilePosition, SwitchData]]
    gates_by_coords: Final[Mapping[TilePosition, GateData]]

    def __init__(
        self,
        player_start_x: Tile,
        player_start_y: Tile,
        matrix: Matrix,
        metadata: _MapMetadata | None = None,
        exit_coords: TilePosition | None = None,
    ) -> None:
        if not matrix or not matrix[0]:
            raise ValueError("Matrice map vide.")

        width = len(matrix[0])
        if any(len(row) != width for row in matrix):
            raise ValueError("Toute les lignes de la map doivent avoir la même longueur.")

        height = len(matrix)
        if not (0 <= player_start_x < width and 0 <= player_start_y < height):
            raise ValueError("Coordonnées de départ du joueur hors limites de la map.")

        if metadata is None:
            metadata = _empty_metadata(width, height)
        elif metadata.width != width or metadata.height != height:
            raise ValueError("Les métadonnées de map ne correspondent pas aux dimensions de la matrice.")

        if metadata.next_map is None and exit_coords is not None:
            raise ValueError("Une sortie ne peut pas être définie sans map suivante.")
        if metadata.next_map is not None and exit_coords is None:
            raise ValueError("Une map suivante requiert une coordonnée de sortie.")
        if exit_coords is not None:
            exit_x, exit_y = exit_coords
            if not (0 <= exit_x < width and 0 <= exit_y < height):
                raise ValueError("Coordonnées de sortie hors limites de la map.")
            if matrix[exit_y][exit_x] != GridCell.EXIT:
                raise ValueError("La coordonnée de sortie doit pointer sur une cellule EXIT.")

        self.width = width
        self.height = height

        self.switch_by_coords = metadata.switches_by_coords
        self.gates_by_coords = metadata.gates_by_coords
        self.next_map = metadata.next_map
        self.exit_coords = exit_coords

        self.player_start_x = player_start_x
        self.player_start_y = player_start_y
        self.__matrix = matrix


    def get(self, x: Tile, y: Tile) -> GridCell:
        """
        Récupère le type de cellule à une coordonnée (x, y) de la map
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError("Coordinates must be within the map boundaries.")
        return self.__matrix[y][x]

    @staticmethod
    def from_string(raw: str) -> Map:
        """
        Transforme le texte (string) en map utilisable
        """
        map_data: _MapFullData = _parse_map_text(raw)
        return Map(
            map_data.player_start_x,
            map_data.player_start_y,
            map_data.matrix,
            map_data.metadata,
            map_data.exit_coords,
        )

    @staticmethod
    def from_file(path: str) -> Map:
        """
        Enclenche la transformation du fichier .txt en map utilisable
        """
        raw = _read_text_file(path)
        return Map.from_string(raw)

    def _config_as_yaml(self) -> str:
        config: dict[str, object] = {
            "width": self.width,
            "height": self.height,
        }
        if self.next_map is not None:
            config["next_map"] = self.next_map

        switches = [
            {
                "id": switch.id,
                "x": switch.x,
                "y": switch.y,
                "state": switch.state,
            }
            for switch in self.switch_by_coords.values()
        ]
        if switches:
            config["switches"] = switches

        gates = [
            {
                "x": gate.x,
                "y": gate.y,
                "open_if": gate_condition_to_yaml_value(gate.open_if),
            }
            for gate in self.gates_by_coords.values()
        ]
        if gates:
            config["gates"] = gates

        return yaml.safe_dump(config, sort_keys=False, allow_unicode=True).strip()

    def __repr__(self) -> str:
        lines = self._config_as_yaml().splitlines()
        lines.append(SECTION_SEPARATOR)
        for index_from_top, row in enumerate(reversed(self.__matrix)):
            y = self.height - 1 - index_from_top
            line = "".join(
                PLAYER_SYMBOL if cell == GridCell.GRASS and (x, y) == (self.player_start_x, self.player_start_y)
                else GRIDCELL_TO_SYMBOL[cell]
                for x, cell in enumerate(row)
            )
            lines.append(line)
        lines.append(SECTION_SEPARATOR)
        return "\n".join(lines)
