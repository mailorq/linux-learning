from pathlib import Path
from typing import NoReturn
from uuid import uuid4

import pytest

from linux_learning import cli
from linux_learning.models import Scenario, ScenarioLevel
from linux_learning.progress import ProgressStore
from linux_learning.scenario_loader import load_scenario


class PromptQueue:
    def __init__(self, commands: list[str]) -> None:
        self._commands = iter(commands)

    def prompt(self, _: str) -> str:
        return next(self._commands)


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


def test_default_scenario_directory_uses_packaged_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_is_dir = Path.is_dir

    def is_dir(path: Path) -> bool:
        return False if path == Path("scenarios") else original_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    scenario_directory = cli._default_scenario_dir()

    assert scenario_directory.is_dir()
    assert tuple(scenario_directory.glob("*.yaml"))


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


def test_run_session_saves_attempts_hints_and_topic_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = load_scenario(Path("scenarios/apt_install_nginx.yaml"))
    prompts = PromptQueue([":hint", ":hint", "apt remove nginx", "apt install nginx"])
    monkeypatch.setattr(cli, "_create_prompt_session", lambda *_: prompts)
    progress_path = Path.cwd() / f".session-test-{uuid4().hex}.sqlite3"
    store = ProgressStore(progress_path)

    try:
        assert cli.run_session((scenario,), Path("unused-history"), store) == 0
        summary_store = ProgressStore(progress_path)
        try:
            summary = summary_store.load_summary()
        finally:
            summary_store.close()
    finally:
        progress_path.unlink(missing_ok=True)

    assert summary.attempts == 2
    assert summary.solved == 1
    assert summary.solved_without_hints == 0
    assert summary.hints_used == 2
    assert summary.progress_penalty == 5
    assert summary.topic_errors == (("packages", 1),)
