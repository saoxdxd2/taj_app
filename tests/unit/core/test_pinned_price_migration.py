"""The pinned-price revision is the single Alembic head."""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_pinned_price_revision_is_single_head():
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["c2f9e1a4b7d6"]
    revision = script.get_revision("c2f9e1a4b7d6")
    assert revision.down_revision == "a1b2c3d4e5f6"
