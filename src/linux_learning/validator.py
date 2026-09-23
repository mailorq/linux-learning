from dataclasses import dataclass
from enum import StrEnum

from linux_learning.command_parser import CommandSegment, ParsedCommandLine, parse_command
from linux_learning.errors import CommandParseError
from linux_learning.models import CommandRule, Scenario


class IssueKind(StrEnum):
    SYNTAX = "syntax"
    PIPELINE = "pipeline"
    WRONG_TOOL = "wrong_tool"
    MISSING_SUBCOMMAND = "missing_subcommand"
    MISSING_FLAG = "missing_flag"
    FORBIDDEN_FLAG = "forbidden_flag"
    MISSING_ARGUMENT = "missing_argument"
    EXTRA_ARGUMENT = "extra_argument"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    kind: IssueKind
    message: str
    segment_index: int | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...]
    parsed: ParsedCommandLine | None = None


def validate_command(text: str, scenario: Scenario) -> ValidationResult:
    try:
        value_flags_by_executable: dict[str, set[str]] = {}
        for rule in scenario.command_rules:
            for executable in (rule.executable, *rule.aliases):
                value_flags_by_executable.setdefault(executable, set()).update(rule.value_flags)
        parsed = parse_command(text, value_flags_by_executable=value_flags_by_executable)
    except CommandParseError as exc:
        issue = ValidationIssue(IssueKind.SYNTAX, str(exc))
        return ValidationResult(False, (issue,))

    issues: list[ValidationIssue] = []
    if len(parsed.segments) != len(scenario.command_rules):
        expected_count = len(scenario.command_rules)
        actual_count = len(parsed.segments)
        issues.append(
            ValidationIssue(
                IssueKind.PIPELINE,
                f"ожидалось элементов команды: {expected_count}, получено: {actual_count}",
            )
        )

    for index, (segment, rule) in enumerate(
        zip(parsed.segments, scenario.command_rules, strict=False)
    ):
        issues.extend(_validate_segment(segment, rule, index))

    if not issues:
        return ValidationResult(True, (), parsed)
    return ValidationResult(False, tuple(issues), parsed)


def _validate_segment(
    segment: CommandSegment,
    rule: CommandRule,
    index: int,
) -> tuple[ValidationIssue, ...]:
    if segment.executable not in (rule.executable, *rule.aliases):
        return (
            ValidationIssue(
                IssueKind.WRONG_TOOL,
                f"ожидалась утилита {rule.executable}, получена {segment.executable}",
                index,
            ),
        )

    issues: list[ValidationIssue] = []
    flags = {_canonical_flag(flag, rule) for flag in segment.flags}
    required_flags = {_canonical_flag(flag, rule) for flag in rule.required_flags}
    forbidden_flags = {_canonical_flag(flag, rule) for flag in rule.forbidden_flags}

    for subcommand in rule.required_subcommands:
        if subcommand not in segment.positionals:
            issues.append(
                ValidationIssue(
                    IssueKind.MISSING_SUBCOMMAND,
                    f"не найдена обязательная подкоманда {subcommand}",
                    index,
                )
            )
    for flag in sorted(required_flags - flags):
        issues.append(
            ValidationIssue(
                IssueKind.MISSING_FLAG,
                f"отсутствует обязательный флаг {flag}",
                index,
            )
        )
    for flag in sorted(forbidden_flags & flags):
        issues.append(
            ValidationIssue(
                IssueKind.FORBIDDEN_FLAG,
                f"использован запрещенный флаг {flag}",
                index,
            )
        )

    remaining = list(segment.positionals)
    for argument in (*rule.required_subcommands, *rule.required_arguments):
        if argument in remaining:
            remaining.remove(argument)
        else:
            issues.append(
                ValidationIssue(
                    IssueKind.MISSING_ARGUMENT,
                    f"отсутствует обязательный аргумент {argument}",
                    index,
                )
            )
    if remaining and not rule.allow_extra_arguments:
        issues.append(
            ValidationIssue(
                IssueKind.EXTRA_ARGUMENT,
                f"неожиданные позиционные аргументы: {', '.join(remaining)}",
                index,
            )
        )
    return tuple(issues)


def _canonical_flag(flag: str, rule: CommandRule) -> str:
    return rule.flag_aliases.get(flag, flag)
