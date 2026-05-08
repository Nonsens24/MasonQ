import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = str(item.path)
        if "/tests/system_tests/" in path:
            item.add_marker(pytest.mark.system)
            item.add_marker(pytest.mark.slow)
