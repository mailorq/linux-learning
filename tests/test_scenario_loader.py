from pathlib import Path
from uuid import uuid4

import pytest

from linux_learning.errors import ScenarioFormatError, ScenarioSourceError
from linux_learning.scenario_loader import load_scenario, load_scenarios


def _write_temp_scenario(content: str) -> Path:
    path = Path.cwd() / f".scenario-test-{uuid4().hex}.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_scenario_returns_validated_model() -> None:
    scenario = load_scenario(Path("scenarios/apt_install_nginx.yaml"))

    assert scenario.id == "packages.install_nginx"
    assert len(scenario.command_rules) == 1
    assert scenario.command_rules[0].required_subcommands == ("install",)
    assert {hint.level.value for hint in scenario.hints} == {"concept", "tools", "solution"}


def test_load_scenarios_rejects_duplicate_ids() -> None:
    source = Path("scenarios/apt_install_nginx.yaml").read_text(encoding="utf-8")
    first = _write_temp_scenario(source)
    second = _write_temp_scenario(source)

    try:
        with pytest.raises(ScenarioFormatError, match="повторяющиеся идентификаторы"):
            load_scenarios(Path.cwd())
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)


def test_load_scenario_rejects_invalid_yaml() -> None:
    path = _write_temp_scenario("id: [")

    try:
        with pytest.raises(ScenarioFormatError, match="некорректный yaml"):
            load_scenario(path)
    finally:
        path.unlink(missing_ok=True)


def test_load_scenarios_rejects_missing_directory() -> None:
    missing = Path.cwd() / f".missing-scenarios-{uuid4().hex}"

    with pytest.raises(ScenarioSourceError, match="каталог не найден"):
        load_scenarios(missing)
