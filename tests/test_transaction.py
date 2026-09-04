from pathlib import Path

from cursor_sand_core.transaction import FileTransaction


def test_transaction_commit(tmp_path: Path) -> None:
    target = tmp_path / "bundle.js"
    target.write_bytes(b"before")
    tx = FileTransaction()
    tx.stage(target, b"after")
    tx.commit()
    assert target.read_bytes() == b"after"
