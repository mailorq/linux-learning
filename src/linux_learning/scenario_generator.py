import argparse
import re
import sys
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from linux_learning.command_parser import CommandSegment, parse_command
from linux_learning.errors import CommandParseError
from linux_learning.models import (
    CommandRule,
    Hint,
    HintLevel,
    RedirectionRule,
    Scenario,
    ScenarioLevel,
)

_SUPPORTED_TOPICS = {
    "apt": "packages",
    "apt-get": "packages",
    "systemctl": "services",
    "journalctl": "logging",
    "ip": "network",
    "ss": "network",
    "ufw": "network",
    "chmod": "permissions",
    "chown": "permissions",
    "tar": "files",
    "grep": "text",
    "sed": "text",
    "awk": "text",
    "docker": "containers",
}
_VALUE_FLAGS_BY_COMMAND = {
    "apt": ("-o",),
    "apt-get": ("-o",),
    "systemctl": ("-H", "-M", "-p", "-t"),
    "journalctl": ("-b", "-n", "-p", "-u"),
    "ip": ("-f",),
    "ss": ("-f",),
    "tar": ("-f",),
    "grep": ("-A", "-B", "-C", "-e", "-f", "-m"),
    "sed": ("-e", "-f"),
    "awk": ("-F", "-v"),
    "docker": ("-f", "-H"),
}
_INLINE_CODE = re.compile(r"`([^`\n]+)`")


class ScenarioDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_page: str
    source_line: int = Field(ge=1)
    source_instruction: str
    source_command: str
    scenario: Scenario


class ScenarioGenerationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _Example:
    instruction: str
    command: str
    line: int


def generate_scenario_drafts(
    source_dir: Path,
    output_dir: Path,
    commands: Collection[str] = tuple(_SUPPORTED_TOPICS),
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    if not source_dir.is_dir():
        raise ScenarioGenerationError(f"{source_dir}: каталог tldr не найден")
    unsupported = set(commands) - set(_SUPPORTED_TOPICS)
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ScenarioGenerationError(f"неподдерживаемые команды: {names}")

    try:
        pages = sorted(
            path for path in source_dir.rglob("*.md") if path.is_file() and path.stem in commands
        )
    except OSError as exc:
        raise ScenarioGenerationError(f"{source_dir}: не удалось прочитать каталог") from exc

    drafts: list[tuple[Path, str]] = []
    for page in pages:
        try:
            content = page.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ScenarioGenerationError(f"{page}: не удалось прочитать страницу") from exc

        relative_page = page.relative_to(source_dir).as_posix()
        slug = _make_slug(page.relative_to(source_dir).with_suffix("").as_posix())
        example_number = 0
        for example in _extract_examples(content):
            command = _without_sudo(example.command, page.stem)
            try:
                parsed = parse_command(
                    command,
                    value_flags_by_executable=_VALUE_FLAGS_BY_COMMAND,
                )
            except CommandParseError as exc:
                if _starts_with_page_command(command, page.stem):
                    raise ScenarioGenerationError(
                        f"{relative_page}:{example.line}: неподдерживаемый синтаксис команды"
                    ) from exc
                continue
            if not parsed.segments or parsed.segments[0].executable != page.stem:
                continue
            if any(
                len(set(segment.positionals)) != len(segment.positionals)
                for segment in parsed.segments
            ):
                message = (
                    f"{relative_page}:{example.line}: "
                    "повторяющиеся аргументы нельзя представить в черновике"
                )
                raise ScenarioGenerationError(message)

            example_number += 1
            try:
                draft = _build_draft(
                    relative_page,
                    example_number,
                    page.stem,
                    slug,
                    example,
                    parsed.segments,
                )
            except ValidationError as exc:
                raise ScenarioGenerationError(
                    f"{relative_page}:{example.line}: не удалось сформировать сценарий"
                ) from exc
            file_path = output_dir / f"{slug}_{example_number:03d}.yaml"
            content = yaml.safe_dump(
                draft.model_dump(mode="json"),
                allow_unicode=True,
                sort_keys=False,
            )
            drafts.append((file_path, content))

    if not drafts:
        return ()
    if len({path for path, _ in drafts}) != len(drafts):
        raise ScenarioGenerationError("страницы источника формируют одинаковые имена файлов")

    if not overwrite:
        existing = tuple(path for path, _ in drafts if path.exists())
        if existing:
            names = ", ".join(str(path) for path in existing)
            raise ScenarioGenerationError(f"файлы черновиков уже существуют: {names}")

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        for path, content in drafts:
            if overwrite:
                path.write_text(content, encoding="utf-8")
            else:
                with path.open("x", encoding="utf-8") as output:
                    output.write(content)
    except OSError as exc:
        raise ScenarioGenerationError(f"{output_dir}: не удалось записать черновики") from exc

    return tuple(path for path, _ in drafts)


def _extract_examples(content: str) -> tuple[_Example, ...]:
    description = " ".join(
        line.strip().removeprefix(">").strip()
        for line in content.splitlines()
        if line.lstrip().startswith(">")
    )
    instruction = ""
    examples: list[_Example] = []
    for number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("- "):
            instruction = stripped[2:].rstrip(": ").strip()
        for match in _INLINE_CODE.finditer(line):
            command = match.group(1).strip()
            if command:
                examples.append(_Example(instruction or description or command, command, number))
    return tuple(examples)


def _without_sudo(command: str, page_command: str) -> str:
    prefix = f"sudo {page_command}"
    if command.startswith(prefix) and (
        len(command) == len(prefix) or command[len(prefix)].isspace()
    ):
        return command[len("sudo ") :]
    return command


def _starts_with_page_command(command: str, page_command: str) -> bool:
    return any(
        command == prefix or command.startswith(f"{prefix} ")
        for prefix in (page_command, f"sudo {page_command}")
    )


def _make_slug(value: str) -> str:
    normalized = value.replace("/", ".")
    return re.sub(r"[^a-z0-9_.]+", "_", normalized.lower()).strip("._")


def _build_draft(
    source_page: str,
    number: int,
    page_command: str,
    slug: str,
    example: _Example,
    segments: tuple[CommandSegment, ...],
) -> ScenarioDraft:
    command_rules = tuple(
        CommandRule(
            executable=segment.executable,
            required_flags=tuple(dict.fromkeys(segment.flags)),
            value_flags=_VALUE_FLAGS_BY_COMMAND.get(segment.executable, ()),
            required_arguments=segment.positionals,
            required_redirections=tuple(
                RedirectionRule(
                    source_fd=1 if redirection.source_fd is None else redirection.source_fd,
                    operator=redirection.operator.value,
                    target=redirection.target,
                )
                for redirection in segment.redirections
            ),
            allow_extra_arguments=False,
            allow_extra_redirections=False,
        )
        for segment in segments
    )
    executables = ", ".join(rule.executable for rule in command_rules)
    flags = tuple(dict.fromkeys(flag for rule in command_rules for flag in rule.required_flags))
    flag_text = ", ".join(flags) if flags else "не требуются"
    scenario = Scenario(
        id=f"draft.{slug}.{number:03d}",
        title=f"черновик {page_command} {number}",
        level=ScenarioLevel.BEGINNER,
        topic=_SUPPORTED_TOPICS[page_command],
        role="root@ubuntu-srv-01:~#",
        objective=f"уточнить задачу по исходному пункту: {example.instruction}",
        command_rules=command_rules,
        hints=(
            Hint(level=HintLevel.CONCEPT, text="сформулировать подсказку о принципе действия"),
            Hint(
                level=HintLevel.TOOLS,
                text=f"использовать утилиты {executables} и флаги {flag_text}",
                progress_penalty=5,
            ),
            Hint(
                level=HintLevel.SOLUTION,
                text=f"пример из {source_page}: {example.command}",
                progress_penalty=15,
            ),
        ),
        success_explanation="добавить разбор действия команды и использованных флагов",
    )
    return ScenarioDraft(
        source_page=source_page,
        source_line=example.line,
        source_instruction=example.instruction,
        source_command=example.command,
        scenario=scenario,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="linux-learning-generate")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("scenario-drafts"))
    parser.add_argument(
        "--command",
        action="append",
        choices=tuple(_SUPPORTED_TOPICS),
        dest="commands",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    try:
        files = generate_scenario_drafts(
            args.source_dir,
            args.output_dir,
            args.commands or tuple(_SUPPORTED_TOPICS),
            overwrite=args.overwrite,
        )
    except ScenarioGenerationError as exc:
        print(exc, file=sys.stderr)
        return 2

    if not files:
        print("подходящие примеры команд не найдены", file=sys.stderr)
        return 1
    print(f"создано черновиков: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
