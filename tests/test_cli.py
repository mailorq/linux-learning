from pathlib import Path
from typing import NoReturn

import pytest

from linux_learning import cli
from linux_learning.models import Scenario, ScenarioLevel
from linux_learning.scenario_loader import load_scenario


@pytest.fixture
def scenarios() -> tuple[Scenario, ...]:
    base = load_scenario(Path("scenarios/apt_install_nginx.yaml"))
    network = base.model_copy(
        update={"id": "network.status", "level": ScenarioLevel.INTERMEDIATE, "topic": "network"}
    )
    advanced = base.model_copy(
        update={"id": "packages.remove_nginx", "level": ScenarioLevel.ADVANCED}
    )
    return base, network, advanced


def test_select_scenarios_filters_by_level_and_topic(scenarios: tuple[Scenario, ...]) -> None:
    selected = cli.select_scenarios(
        scenarios,
        level=ScenarioLevel.INTERMEDIATE,
        topic=" NETWORK ",
    )

    assert tuple(scenario.id for scenario in selected) == ("network.status",)


def test_select_scenarios_preserves_order(scenarios: tuple[Scenario, ...]) -> None:
    selected = cli.select_scenarios(scenarios, topic="packages")

    assert tuple(scenario.id for scenario in selected) == (
        "packages.install_nginx",
        "packages.remove_nginx",
    )


def test_select_scenarios_returns_empty_for_unknown_topic(
    scenarios: tuple[Scenario, ...],
) -> None:
    assert cli.select_scenarios(scenarios, topic="unknown") == ()


def test_main_does_not_open_progress_store_when_no_scenarios_match(
    monkeypatch: pytest.MonkeyPatch,
    scenarios: tuple[Scenario, ...],
) -> None:
    monkeypatch.setattr(cli, "load_scenarios", lambda _: scenarios)

    def fail_progress_store(path: Path) -> NoReturn:
        raise AssertionError(f"unexpected progress store for {path}")

    monkeypatch.setattr(cli, "ProgressStore", fail_progress_store)

    assert cli.main(["--topic", "unknown"]) == 2


def test_main_rejects_blank_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "load_scenarios",
        lambda _: (load_scenario(Path("scenarios/apt_install_nginx.yaml")),),
    )

    def fail_progress_store(path: Path) -> NoReturn:
        raise AssertionError(f"unexpected progress store for {path}")

    monkeypatch.setattr(cli, "ProgressStore", fail_progress_store)

    assert cli.main(["--topic", "  "]) == 2
