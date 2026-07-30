import importlib


def test_server_exports_serve():
    """Smoke test that release.olive.server exports serve."""
    m = importlib.import_module("release.olive.server")
    assert hasattr(m, "serve")
