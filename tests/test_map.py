"""Tests for map.py.

These tests target the current public API:
- Map(...)
- Map.from_string(...)
- Map.from_file(...)
"""

from pathlib import Path
from textwrap import dedent

import pytest

from map import (
    GridCell,
    InvalidMapFileException,
    Map,
    SYMBOL_TO_GRIDCELL,
)



def map_from_string(raw: str) -> Map:
    """Parse a full map-file string into a Map."""
    return Map.from_string(raw)


class TestMapInit:
    def test_basic_creation(self) -> None:
        m = Map(0, 0, ((GridCell.GRASS,),))
        assert m.width == 1
        assert m.height == 1
        assert m.player_start_x == 0
        assert m.player_start_y == 0

    def test_empty_matrix_raises(self) -> None:
        with pytest.raises(ValueError):
            Map(0, 0, ())

    def test_inconsistent_row_lengths_raises(self) -> None:
        with pytest.raises(ValueError):
            Map(0, 0, (
                (GridCell.GRASS, GridCell.GRASS),
                (GridCell.GRASS,),
            ))

    def test_player_start_out_of_bounds_raises(self) -> None:
        matrix = ((GridCell.GRASS, GridCell.GRASS),)
        with pytest.raises(ValueError):
            Map(-1, 0, matrix)
        with pytest.raises(ValueError):
            Map(0, -1, matrix)
        with pytest.raises(ValueError):
            Map(2, 0, matrix)
        with pytest.raises(ValueError):
            Map(0, 1, matrix)

    def test_get_returns_correct_cell(self) -> None:
        matrix = (
            (GridCell.GRASS, GridCell.BUISSON),
            (GridCell.CRYSTAL, GridCell.TROU),
        )
        m = Map(0, 0, matrix)
        assert m.get(0, 0) == GridCell.GRASS
        assert m.get(1, 0) == GridCell.BUISSON
        assert m.get(0, 1) == GridCell.CRYSTAL
        assert m.get(1, 1) == GridCell.TROU

    def test_get_out_of_bounds_raises(self) -> None:
        m = Map(0, 0, ((GridCell.GRASS,),))
        with pytest.raises(ValueError):
            m.get(-1, 0)
        with pytest.raises(ValueError):
            m.get(0, -1)
        with pytest.raises(ValueError):
            m.get(1, 0)
        with pytest.raises(ValueError):
            m.get(0, 1)


class TestFromStringSuccess:
    def test_minimal_map(self) -> None:
        m = map_from_string("width: 1\nheight: 1\n---\nP\n---")
        assert m.width == 1
        assert m.height == 1
        assert m.player_start_x == 0
        assert m.player_start_y == 0
        assert m.get(0, 0) == GridCell.GRASS

    def test_player_position_y_is_inverted_from_text(self) -> None:
        raw = dedent("""\
            width: 3
            height: 2
            ---
            xPx
            xxx
            ---""")
        m = map_from_string(raw)
        assert m.player_start_x == 1
        assert m.player_start_y == 1

    def test_player_on_bottom_line_has_y_zero(self) -> None:
        raw = dedent("""\
            width: 3
            height: 2
            ---
            xxx
            xPx
            ---""")
        m = map_from_string(raw)
        assert m.player_start_x == 1
        assert m.player_start_y == 0

    def test_short_lines_are_padded_with_grass(self) -> None:
        raw = "width: 5\nheight: 2\n---\nx\nP\n---"
        m = map_from_string(raw)
        assert m.width == 5
        assert m.get(0, 0) == GridCell.GRASS
        assert m.get(4, 0) == GridCell.GRASS
        assert m.get(0, 1) == GridCell.BUISSON
        assert m.get(4, 1) == GridCell.GRASS

    def test_empty_grid_lines_become_all_grass(self) -> None:
        raw = "width: 3\nheight: 3\n---\n\nP\n\n---"
        m = map_from_string(raw)
        assert m.get(0, 2) == GridCell.GRASS
        assert m.get(2, 2) == GridCell.GRASS
        assert m.get(0, 0) == GridCell.GRASS
        assert m.get(2, 0) == GridCell.GRASS

    def test_all_supported_cell_types_are_decoded(self) -> None:
        raw = dedent("""\
            width: 5
            height: 2
            ---
             x*sS
            P   O
            ---""")
        m = map_from_string(raw)
        assert m.get(0, 1) == GridCell.GRASS
        assert m.get(1, 1) == GridCell.BUISSON
        assert m.get(2, 1) == GridCell.CRYSTAL
        assert m.get(3, 1) == GridCell.SPINNEUR_HORIZONTAL
        assert m.get(4, 1) == GridCell.SPINNEUR_VERTICAL
        assert m.get(4, 0) == GridCell.TROU

    def test_repr_round_trip_preserves_map(self) -> None:
        raw = dedent("""\
            width: 4
            height: 3
            ---
            x*SO
            x Px
            xxxx
            ---""")
        m1 = map_from_string(raw)
        m2 = Map.from_string(repr(m1))
        assert repr(m2) == repr(m1)
        assert m2.width == m1.width
        assert m2.height == m1.height
        assert m2.player_start_x == m1.player_start_x
        assert m2.player_start_y == m1.player_start_y

    def test_repr_round_trip_preserves_switches_and_gates(self) -> None:
        raw = dedent("""\
            width: 4
            height: 2
            switches:
              - id: a
                x: 1
                y: 0
                state: true
            gates:
              - x: 2
                y: 0
                open_if:
                  switch_is_on: a
            ---
            xxxx
            P^|x
            ---""")
        m1 = map_from_string(raw)
        m2 = Map.from_string(repr(m1))

        assert repr(m2) == repr(m1)
        assert m2.switch_by_coords == m1.switch_by_coords
        assert m2.gates_by_coords == m1.gates_by_coords

    def test_repr_preserves_player_on_bottom_line(self) -> None:
        raw = dedent("""\
            width: 3
            height: 2
            ---
            xxx
            Pxx
            ---""")
        m1 = map_from_string(raw)
        m2 = Map.from_string(repr(m1))
        assert m2.player_start_x == 0
        assert m2.player_start_y == 0

    def test_large_map_has_no_off_by_one_error(self) -> None:
        width, height = 20, 10
        grid_lines: list[str] = []
        for y_from_top in range(height):
            y = height - 1 - y_from_top
            if y == 0:
                grid_lines.append("x" * (width - 1) + "P")
            else:
                grid_lines.append("x" * width)
        raw = f"width: {width}\nheight: {height}\n---\n" + "\n".join(grid_lines) + "\n---"
        m = map_from_string(raw)
        assert m.width == width
        assert m.height == height
        assert m.player_start_x == width - 1
        assert m.player_start_y == 0


class TestFromStringErrors:
    def test_empty_string_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("")

    def test_no_separator_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\nheight: 1\nP")

    def test_one_separator_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\nheight: 1\n---\nP")

    def test_three_separator_lines_raise(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\nheight: 1\n---\nP\n---\n---")

    def test_final_separator_must_terminate_file(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\nheight: 1\n---\nP\n---\nextra")

    def test_header_line_requires_exact_key_value_format(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width:1\nheight: 1\n---\nP\n---")

    def test_unknown_property_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\nheight: 1\nfoo: bar\n---\nP\n---")

    def test_duplicate_width_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\nwidth: 2\nheight: 1\n---\nP\n---")

    def test_duplicate_height_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\nheight: 1\nheight: 2\n---\nP\n---")

    def test_missing_width_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("height: 1\n---\nP\n---")

    def test_missing_height_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\n---\nP\n---")

    def test_zero_width_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 0\nheight: 1\n---\nP\n---")

    def test_negative_height_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: 1\nheight: -1\n---\nP\n---")

    def test_non_integer_width_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            map_from_string("width: abc\nheight: 1\n---\nP\n---")

    def test_too_many_grid_lines_raise(self) -> None:
        raw = "width: 3\nheight: 2\n---\nxxx\nxPx\nxxx\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_too_few_grid_lines_raise(self) -> None:
        raw = "width: 1\nheight: 2\n---\nP\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_grid_line_too_long_raises(self) -> None:
        raw = "width: 3\nheight: 1\n---\nxxPxx\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_no_player_raises(self) -> None:
        raw = "width: 3\nheight: 1\n---\nxxx\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_two_players_raise(self) -> None:
        raw = "width: 3\nheight: 1\n---\nP P\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_invalid_character_raises(self) -> None:
        raw = "width: 1\nheight: 1\n---\nQ\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_lever_symbol_without_config_raises(self) -> None:
        raw = "width: 2\nheight: 1\n---\nP^\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_configured_gate_without_gate_symbol_raises(self) -> None:
        raw = dedent("""\
            width: 3
            height: 1
            switches:
              - id: a
                x: 1
                y: 0
            gates:
              - x: 2
                y: 0
                open_if:
                  switch_is_on: a
            ---
            P^
            ---""")
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)


class TestFromFile:
    def test_load_from_file(self, tmp_path: Path) -> None:
        content = dedent("""\
            width: 5
            height: 3
            ---
            xxxxx
            x P x
            xxxxx
            ---""")
        map_file = tmp_path / "map.txt"
        map_file.write_text(content, encoding="utf-8")

        m = Map.from_file(str(map_file))
        assert m.width == 5
        assert m.height == 3
        assert m.player_start_x == 2
        assert m.player_start_y == 1

    def test_nonexistent_file_raises(self) -> None:
        with pytest.raises(InvalidMapFileException):
            Map.from_file("nonexistent_file_that_does_not_exist.txt")

    def test_non_txt_extension_raises(self, tmp_path: Path) -> None:
        map_file = tmp_path / "map.csv"
        map_file.write_text("width: 1\nheight: 1\n---\nP\n---", encoding="utf-8")
        with pytest.raises(InvalidMapFileException):
            Map.from_file(str(map_file))

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        map_file = tmp_path / "empty.txt"
        map_file.write_text("", encoding="utf-8")
        with pytest.raises(InvalidMapFileException):
            Map.from_file(str(map_file))

    def test_real_map1_file_loads_if_present(self) -> None:
        map_path = Path("maps/map1.txt")
        if not map_path.exists():
            pytest.skip("maps/map1.txt not found")

        m = Map.from_file(str(map_path))
        assert m.width == 40
        assert m.height == 15


class TestConstantsAndEnum:
    def test_expected_symbols_are_mapped(self) -> None:
        assert " " in SYMBOL_TO_GRIDCELL
        assert "x" in SYMBOL_TO_GRIDCELL
        assert "*" in SYMBOL_TO_GRIDCELL
        assert "s" in SYMBOL_TO_GRIDCELL
        assert "S" in SYMBOL_TO_GRIDCELL
        assert "O" in SYMBOL_TO_GRIDCELL

    def test_player_symbol_is_not_a_grid_cell_mapping(self) -> None:
        assert "P" not in SYMBOL_TO_GRIDCELL

    def test_symbol_mapping_is_immutable(self) -> None:
        with pytest.raises(TypeError):
            SYMBOL_TO_GRIDCELL["x"] = GridCell.GRASS  # type: ignore

    def test_gridcell_values_are_distinct(self) -> None:
        values = list(GridCell)
        assert len(values) == len(set(values))

class TestFromStringNextMapAndExit:
    def test_next_map_alone_raises(self) -> None:
        raw = "width: 1\nheight: 1\nnext_map: next.txt\n---\nP\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_exit_without_next_map_raises(self) -> None:
        raw = "width: 2\nheight: 1\n---\nPE\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)

    def test_next_map_and_single_exit_are_exposed(self) -> None:
        raw = "width: 2\nheight: 1\nnext_map: next.txt\n---\nPE\n---"
        m = map_from_string(raw)
        assert m.next_map == "next.txt"
        assert m.exit_coords == (1, 0)
        assert m.get(1, 0) == GridCell.EXIT
        assert not m.get(1, 0).is_player_obstacle

    def test_two_exits_raise(self) -> None:
        raw = "width: 3\nheight: 1\nnext_map: next.txt\n---\nPEE\n---"
        with pytest.raises(InvalidMapFileException):
            map_from_string(raw)
