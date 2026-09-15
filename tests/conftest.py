import arcade
from arcade import gl
import pytest

# This file must be named 'conftest.py' and be located in the 'tests/' directory.
# It gets loaded automatically by pytest to provide "fixtures" available to all tests.
# In our context, it allows test functions to require a `window: arcade.Window`
# argument (the name is meaningful!). It will be the one and only Window used
# for testing. Tests are not allowed to create their own Window.
# We copied this from the arcade open source repository, and simplified it
# because we do not need all their configurations.
#
# You should not modify this file, and you do not need to understand what it does.

WINDOW: arcade.Window | None = None

def create_window() -> arcade.Window:
    global WINDOW
    if not WINDOW:
        WINDOW = arcade.Window(
            width=800, height=600, title="Testing", antialiasing=False
        )
    return WINDOW

def prepare_window(window: arcade.Window, caption: str) -> None:
    # Check if someone has been naughty
    if window.has_exit:
        raise RuntimeError("Please do not close the global test window :D")

    window.switch_to()
    window.set_size(800, 600)
    window.set_caption(caption)

    ctx = window.ctx
    arcade.SpriteList.DEFAULT_TEXTURE_FILTER = gl.LINEAR, gl.LINEAR
    window._start_finish_render_data = None
    window.hide_view()  # Disable views if any is active
    window.dispatch_pending_events()
    try:
        arcade.disable_timings()
    except Exception:
        pass

    # Reset context (various states)
    ctx.reset()
    window.set_vsync(False)
    window.flip()
    window.clear()
    window.default_camera.use()
    ctx.gc_mode = "context_gc"
    ctx.gc()

@pytest.fixture
def test_name(request: pytest.FixtureRequest) -> str:
    return f"Testing - {request.node.name}"

@pytest.fixture(scope="function")
def window(test_name: str) -> arcade.Window:
    """
    Global window that is shared between tests.

    This just returns the global window, but ensures that the context
    is reset between each test function and the window is flipped
    between each test function.
    """
    window = create_window()
    arcade.set_window(window)
    prepare_window(window, caption=test_name)
    return window
