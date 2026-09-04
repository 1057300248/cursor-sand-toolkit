from cursor_sand_core.profiles import BuildProfile, match_profile


def test_exact_profile_match() -> None:
    profiles = [
        BuildProfile("a", "1.0", {"main.js": "aaa", "workbench.js": "bbb"}),
        BuildProfile("b", "1.1", {"main.js": "ccc"}),
    ]
    result = match_profile({"main.js": "aaa", "workbench.js": "bbb"}, profiles)
    assert result.exact is True
    assert result.profile is not None
    assert result.profile.name == "a"


def test_best_partial_profile_match() -> None:
    profiles = [
        BuildProfile("a", "1.0", {"a": "1", "b": "2"}),
        BuildProfile("b", "1.1", {"a": "1", "b": "9", "c": "3"}),
    ]
    result = match_profile({"a": "1", "b": "2", "c": "x"}, profiles)
    assert result.profile is not None
    assert result.profile.name == "a"
    assert result.exact is True
