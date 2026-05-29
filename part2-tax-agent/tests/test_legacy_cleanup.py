from pathlib import Path


def test_main_no_longer_uses_static_planner():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")

    assert "from planner import Planner" not in source
    assert "Planner()" not in source
