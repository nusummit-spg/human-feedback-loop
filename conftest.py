# Root conftest.py — blocks the broken langsmith pytest plugin that ships
# with this host environment.  The plugin crashes on import because of a
# pydantic_core version mismatch unrelated to this package.
# This file is intentionally at the project root (not inside tests/) so
# pytest processes it before attempting to load registered entry points.

collect_ignore_glob = []  # keep pytest happy with an empty root conftest


def pytest_configure(config):
    """Unregister the langsmith plugin before it tries to import."""
    try:
        config.pluginmanager.set_blocked("langsmith_plugin")
    except Exception:
        pass
