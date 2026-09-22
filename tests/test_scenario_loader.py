from pathlib import Path

import pytest

from linux_learning.errors import ScenarioFormatError, ScenarioSourceError
from linux_learning.scenario_loader import load_scenario, load_scenarios


def test_load_scenario_returns_validated_model() -> None:
    scenario = load_scenario(Path("scenarios/apt_install_nginx.yaml"))

    assert scenario.id == "packages.install_nginx"
    assert len(scenario.command_rules) == 1
    assert scenario.command_rules[0].required_subcommands == ("install",)
    assert {hint.level.value for hint in scenario.hints} == {"concept", "tools", "solution"}


def test_load_scenarios_rejects_duplicate_ids(tmp_path: Path) -> None:
    source = Path("scenarios/apt_install_nginx.yaml").read_text(encoding="utf-8")
    (tmp_path / "first.yaml").write_text(source, encoding="utf-8")
    (tmp_path / "second.yaml").write_text(source, encoding="utf-8")

    with pytest.raises(ScenarioFormatError, match="повторяющиеся идентификаторы"):
        load_scenarios(tmp_path)


def test_load_scenario_rejects_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("id: [", encoding="utf-8")

    with pytest.raises(ScenarioFormatError, match="некорректный yaml"):
        load_scenario(path)


def test_load_scenarios_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ScenarioSourceError, match="каталог не найден"):
        load_scenarios(tmp_path / "missing")
