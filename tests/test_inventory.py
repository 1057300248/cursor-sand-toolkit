import hashlib
from pathlib import Path

from cursor_sand_core.inventory import inventory


def test_inventory_reports_hash_and_missing_targets(tmp_path: Path) -> None:
    target = tmp_path / "out" / "main.js"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"hello")

    items = inventory(tmp_path, ("out/main.js", "out/missing.js"))
    assert items[0].exists
    assert items[0].size == 5
    assert items[0].sha256 == hashlib.sha256(b"hello").hexdigest()
    assert not items[1].exists
    assert items[1].sha256 is None
