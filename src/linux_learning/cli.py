import argparse
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory, History, InMemoryHistory
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from linux_learning.errors import ScenarioError
from linux_learning.feedback import FeedbackKind, build_feedback
from linux_learning.models import Scenario, ScenarioLevel
from linux_learning.progress import ProgressStore, ProgressStoreError, ProgressSummary
from linux_learning.scenario_loader import load_scenarios
from linux_learning.validator import validate_command


@dataclass
class SessionStats:
    attempts: int = 0
    solved: int = 0
    solved_without_hints: int = 0
    hints_used: int = 0
    progress_penalty: int = 0
    topic_errors: Counter[str] = field(default_factory=Counter)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="linux-learning")
    parser.add_argument("--scenario-dir", type=Path, default=Path("scenarios"))
    parser.add_argument(
        "--level",
        choices=[level.value for level in ScenarioLevel],
        help="показывать сценарии выбранного уровня",
    )
    parser.add_argument("--topic", help="показывать сценарии выбранной темы")
    parser.add_argument(
        "--history-file",
        type=Path,
        default=Path.home() / ".linux-learning" / "history",
    )
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=Path.home() / ".linux-learning" / "progress.sqlite3",
    )
    args = parser.parse_args(argv)

    try:
        all_scenarios = load_scenarios(args.scenario_dir)
    except ScenarioError as exc:
        Console().print(f"[red]{exc}[/red]")
        return 2

    console = Console()
    if args.topic is not None and not args.topic.strip():
        console.print("[red]тема не может быть пустой[/red]")
        return 2

    level = ScenarioLevel(args.level) if args.level is not None else None
    scenarios = select_scenarios(all_scenarios, level=level, topic=args.topic)
    if not scenarios:
        filters = []
        if level is not None:
            filters.append(f"уровень {level.value}")
        if args.topic is not None:
            filters.append(f"тема {args.topic.strip()}")
        console.print(f"[red]не найдены сценарии: {', '.join(filters)}[/red]")
        console.print(
            "доступные темы: " + ", ".join(sorted({scenario.topic for scenario in all_scenarios}))
        )
        console.print(
            "доступные уровни: "
            + ", ".join(sorted({scenario.level.value for scenario in all_scenarios}))
        )
        return 2

    try:
        progress_store = ProgressStore(args.progress_file)
    except ProgressStoreError as exc:
        console.print(f"[yellow]{exc}; прогресс не будет сохранен[/yellow]")
        progress_store = None
    return run_session(scenarios, args.history_file, progress_store)


def select_scenarios(
    scenarios: Sequence[Scenario],
    *,
    level: ScenarioLevel | None = None,
    topic: str | None = None,
) -> tuple[Scenario, ...]:
    normalized_topic = topic.strip().casefold() if topic is not None else None
    return tuple(
        scenario
        for scenario in scenarios
        if (level is None or scenario.level is level)
        and (normalized_topic is None or scenario.topic.casefold() == normalized_topic)
    )


def run_session(
    scenarios: Sequence[Scenario],
    history_file: Path,
    progress_store: ProgressStore | None = None,
) -> int:
    console = Console()
    stats = SessionStats()
    session = _create_prompt_session(scenarios, history_file)

    for scenario in scenarios:
        _show_task(console, scenario)
        hints_used = 0
        while True:
            try:
                value = session.prompt(f"{scenario.role} ")
            except EOFError, KeyboardInterrupt:
                console.print("сессия завершена")
                _finish_session(console, stats, progress_store)
                return 0

            command = value.strip()
            if command in {":quit", ":exit"}:
                _finish_session(console, stats, progress_store)
                return 0
            if command == ":help":
                console.print("[dim]:hint подсказка, :skip пропустить, :quit выйти[/dim]")
                continue
            if command == ":hint":
                if hints_used == len(scenario.hints):
                    console.print("[yellow]подсказки закончились[/yellow]")
                    continue
                hint = scenario.hints[hints_used]
                hints_used += 1
                stats.hints_used += 1
                stats.progress_penalty += hint.progress_penalty
                console.print(Panel(hint.text, title=f"подсказка {hints_used}"))
                continue
            if command == ":skip":
                console.print("[yellow]сценарий пропущен[/yellow]")
                break

            stats.attempts += 1
            result = validate_command(command, scenario)
            feedback = build_feedback(result, scenario)
            _show_feedback(
                console,
                feedback.kind,
                feedback.title,
                feedback.details,
                feedback.explanation,
            )
            if feedback.kind is FeedbackKind.SUCCESS:
                stats.solved += 1
                if hints_used == 0:
                    stats.solved_without_hints += 1
                break
            stats.topic_errors[scenario.topic] += 1

    _finish_session(console, stats, progress_store)
    return 0


def _create_prompt_session(
    scenarios: Sequence[Scenario],
    history_file: Path,
) -> PromptSession[str]:
    words = {":help", ":hint", ":skip", ":quit", ":exit"}
    words.update(rule.executable for scenario in scenarios for rule in scenario.command_rules)
    completer = WordCompleter(sorted(words), sentence=True)
    history: History
    try:
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history = FileHistory(str(history_file))
    except OSError:
        history = InMemoryHistory()
    return PromptSession(history=history, completer=completer)


def _show_task(console: Console, scenario: Scenario) -> None:
    text = f"{scenario.title}\n{scenario.objective}\nтема: {scenario.topic}\nроль: {scenario.role}"
    console.print(Panel(text, title="задание", border_style="cyan"))


def _show_feedback(
    console: Console,
    kind: FeedbackKind,
    title: str,
    details: tuple[str, ...],
    explanation: str,
) -> None:
    style = "green" if kind is FeedbackKind.SUCCESS else "red"
    text = "\n".join((*details, explanation))
    console.print(Panel(text, title=title, border_style=style))


def _finish_session(
    console: Console,
    stats: SessionStats,
    progress_store: ProgressStore | None,
) -> None:
    summary = None
    if progress_store is not None:
        if stats.attempts or stats.hints_used:
            try:
                progress_store.save_session(
                    attempts=stats.attempts,
                    solved=stats.solved,
                    solved_without_hints=stats.solved_without_hints,
                    hints_used=stats.hints_used,
                    progress_penalty=stats.progress_penalty,
                    topic_errors=stats.topic_errors,
                )
            except ProgressStoreError as exc:
                console.print(f"[yellow]{exc}[/yellow]")
        try:
            summary = progress_store.load_summary()
        except ProgressStoreError as exc:
            console.print(f"[yellow]{exc}[/yellow]")
        finally:
            progress_store.close()
    _show_stats(console, stats, summary)


def _show_stats(
    console: Console,
    stats: SessionStats,
    summary: ProgressSummary | None,
) -> None:
    table = Table(title="статистика")
    table.add_column("показатель")
    table.add_column("значение")
    table.add_row("попытки", str(stats.attempts))
    table.add_row("решено", str(stats.solved))
    table.add_row("решено без подсказок", str(stats.solved_without_hints))
    table.add_row("подсказки", str(stats.hints_used))
    table.add_row("штраф прогресса", str(stats.progress_penalty))
    rate = 0 if stats.solved == 0 else round(stats.solved_without_hints / stats.solved * 100)
    table.add_row("процент без подсказок", f"{rate}%")
    console.print(table)
    if summary is not None:
        console.print(
            f"всего сессий: {summary.sessions}, попыток: {summary.attempts}, "
            f"решено: {summary.solved}, штраф прогресса: {summary.progress_penalty}"
        )
    topic_errors = (
        summary.topic_errors if summary is not None else tuple(stats.topic_errors.items())
    )
    if topic_errors:
        weak_topics = ", ".join(f"{topic}: {count}" for topic, count in topic_errors)
        console.print(f"слабые темы: {weak_topics}")
