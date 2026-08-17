from __future__ import annotations

import importlib.util


def test_python_runtime_uses_the_version_neutral_serenity_core_namespace() -> None:
    assert importlib.util.find_spec("serenity_core") is not None
    assert importlib.util.find_spec("serenity_" + "v2") is None
