from cursor_sand_core import cli


def test_version_command(capsys) -> None:
    assert cli.main(["--version"]) == 0
    output = capsys.readouterr().out
    assert "1.6.0" in output
    assert "compat runtime 1.5.8" in output


def test_legacy_commands_are_forwarded(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_legacy(argv):
        seen.append(list(argv))
        return 17

    monkeypatch.setattr(cli.compat, "run_legacy", fake_legacy)
    assert cli.main(["install", "--transport", "direct"]) == 17
    assert seen == [["install", "--transport", "direct"]]


def test_doctor_is_routed_to_new_cli(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_doctor(argv):
        seen.append(list(argv))
        return 3

    monkeypatch.setattr(cli, "doctor_main", fake_doctor)
    assert cli.main(["doctor", "/tmp/app", "--json"]) == 3
    assert seen == [["/tmp/app", "--json"]]


def test_inventory_is_routed_to_new_cli(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_inventory(argv):
        seen.append(list(argv))
        return 4

    monkeypatch.setattr(cli, "inventory_main", fake_inventory)
    assert cli.main(["inventory", "/tmp/app"]) == 4
    assert seen == [["/tmp/app"]]
