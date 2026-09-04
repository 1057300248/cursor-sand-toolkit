import json
from pathlib import Path

from cursor_sand_core.doctor_cli import main


def _write(root: Path, relative: str, content: str) -> None:
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _healthy_tree(root: Path) -> None:
    workbench = "/*SAND_TTFT_V1*//*SAND_USER_RULES_V1*/"
    _write(root, "out/vs/workbench/workbench.desktop.main.js", workbench)
    _write(root, "out/vs/workbench/workbench.glass.main.js", workbench)
    _write(
        root,
        "extensions/cursor-agent-exec/dist/main.js",
        "/*SAND_RULES_SKILLS_V4*/",
    )
    _write(
        root,
        "extensions/cursor-agent-host/dist/675.js",
        "/*SAND_MCP_FILESYSTEM_V1*/",
    )


def test_doctor_cli_strict_passes_for_healthy_tree(tmp_path: Path, capsys) -> None:
    _healthy_tree(tmp_path)
    assert main([str(tmp_path), "--strict"]) == 0
    output = capsys.readouterr().out
    assert "performance.ttft" in output
    assert "healthy" in output


def test_doctor_cli_strict_fails_when_feature_missing(tmp_path: Path) -> None:
    _healthy_tree(tmp_path)
    desktop = tmp_path / "out" / "vs" / "workbench" / "workbench.desktop.main.js"
    desktop.write_text("/*SAND_USER_RULES_V1*/", encoding="utf-8")
    assert main([str(tmp_path), "--strict"]) == 1


def test_doctor_cli_json_is_machine_readable(tmp_path: Path, capsys) -> None:
    _healthy_tree(tmp_path)
    assert main([str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == str(tmp_path.resolve())
    assert payload["features"]
    assert payload["inventory"]
