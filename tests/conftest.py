import os
import tempfile

import pytest

os.environ.setdefault(
    "NUMBA_CACHE_DIR",
    os.path.join(tempfile.gettempdir(), "masonq-numba-cache"),
)
os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(tempfile.gettempdir(), "masonq-mpl-cache"),
)
os.environ.setdefault(
    "XDG_CACHE_HOME",
    os.path.join(tempfile.gettempdir(), "masonq-cache"),
)


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = str(item.path)
        if "/tests/system_tests/" in path:
            item.add_marker(pytest.mark.system)
            item.add_marker(pytest.mark.slow)
