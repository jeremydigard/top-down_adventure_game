from pathlib import Path
from textwrap import dedent

import arcade

from gameview import GameView
from helper import grid_to_pixels


def test_exit_loads_next_map_relative_to_current_map(window: arcade.Window, tmp_path: Path) -> None:
    map1 = tmp_path / "map1.txt"
    map2 = tmp_path / "map2.txt"

    map1.write_text(
        dedent("""\
            width: 4
            height: 3
            next_map: map2.txt
            ---
            xxxx
            xPEx
            xxxx
            ---"""),
        encoding="utf-8",
    )
    map2.write_text(
        dedent("""\
            width: 3
            height: 3
            ---
            xxx
            xPx
            xxx
            ---"""),
        encoding="utf-8",
    )

    view = GameView.from_file(str(map1))
    window.show_view(view)
    assert len(view.world.exits) == 1

    view.world.player.position = (grid_to_pixels(2), grid_to_pixels(1))
    view.on_update(1 / 60)

    current_view = window.current_view
    assert isinstance(current_view, GameView)
    assert Path(current_view.file_map) == map2
