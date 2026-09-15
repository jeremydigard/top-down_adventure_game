import arcade
from textwrap import dedent

from gameview import GameView


# ===================================================================
# Test des cristaux
# ===================================================================

def test_collect_crystals(window: arcade.Window) -> None:

    raw = dedent("""\
            width: 4
            height: 4
            ---
            xxxx
            x *x
            xP*x
            xxxx
            ---""")

    view = GameView.from_string(raw)
    window.show_view(view)

    INITIAL_CRYSTAL_COUNT = 2

    # On devrait commencer avec autant de cristaux que de * sur la map
    assert len(view.world.crystals) == INITIAL_CRYSTAL_COUNT

    # On déplace player vers la droite
    view.on_key_press(arcade.key.RIGHT, 0)

    # Laisse rouler le jeu une seconde
    window.test(60)

    # On devrait collecter le premier cristal
    assert len(view.world.crystals) == INITIAL_CRYSTAL_COUNT - 1

    # Arrete le mouvement a droite et commence le mouvement vers le haut
    view.on_key_release(arcade.key.RIGHT, 0)
    view.on_key_press(arcade.key.UP, 0)

    # On roule une seconde de plus
    window.test(60)

    # On devrait collecter le deuxieme cristal
    assert len(view.world.crystals) == INITIAL_CRYSTAL_COUNT - 2
