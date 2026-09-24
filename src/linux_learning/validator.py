from dataclasses import dataclass
from difflib import get_close_matches
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
    CONFLICTING_FLAGS = "conflicting_flags"
    MISSING_ARGUMENT = "missing_argument"
    ARGUMENT_ORDER = "argument_order"
    EXTRA_ARGUMENT = "extra_argument"
    EXTRA_FLAG = "extra_flag"
    MISSING_REDIRECTION = "missing_redirection"
    EXTRA_REDIRECTION = "extra_redirection"


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
        known_flags_by_executable: dict[str, set[str]] = {}
        for rule in scenario.command_rules:
            for executable in (rule.executable, *rule.aliases):
                value_flags_by_executable.setdefault(executable, set()).update(rule.value_flags)
                known_flags_by_executable.setdefault(executable, set()).update(
                    (
                        *rule.required_flags,
                        *rule.allowed_flags,
                        *rule.forbidden_flags,
                        *(flag for pair in rule.conflicting_flag_pairs for flag in pair),
                        *rule.flag_aliases.keys(),
                        *rule.flag_aliases.values(),
                    )
                )
        parsed = parse_command(
            text,
            value_flags_by_executable=value_flags_by_executable,
            known_flags_by_executable=known_flags_by_executable,
        )
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
    known_flags = (
        required_flags
        | forbidden_flags
        | {_canonical_flag(flag, rule) for flag in rule.allowed_flags}
    )
    known_flags.update(
        _canonical_flag(flag, rule) for pair in rule.conflicting_flag_pairs for flag in pair
    )
    for flag in sorted(flags - known_flags):
        issues.append(
            ValidationIssue(
                IssueKind.EXTRA_FLAG,
                f"неожиданный флаг {flag}",
                index,
            )
        )
    for first, second in rule.conflicting_flag_pairs:
        canonical_first = _canonical_flag(first, rule)
        canonical_second = _canonical_flag(second, rule)
        if canonical_first in flags and canonical_second in flags:
            issues.append(
                ValidationIssue(
                    IssueKind.CONFLICTING_FLAGS,
                    f"несовместимые флаги указаны вместе: {canonical_first} и {canonical_second}",
                    index,
                )
            )

    expected_arguments = (*rule.required_subcommands, *rule.required_arguments)
    remaining = list(segment.positionals)
    missing_arguments = False
    for argument in expected_arguments:
        if argument in remaining:
            remaining.remove(argument)
        else:
            missing_arguments = True
            message = f"отсутствует обязательный аргумент {argument}"
            suggestions = get_close_matches(argument, remaining, n=1, cutoff=0.75)
            if suggestions:
                message += f"; возможно, вместо него указан {suggestions[0]}"
            issues.append(
                ValidationIssue(
                    IssueKind.MISSING_ARGUMENT,
                    message,
                    index,
                )
            )
    if (
        expected_arguments
        and not missing_arguments
        and not _is_subsequence_arguments(expected_arguments, segment.positionals)
    ):
        issues.append(
            ValidationIssue(
                IssueKind.ARGUMENT_ORDER,
                "позиционные аргументы указаны не в требуемом порядке: "
                + " ".join(expected_arguments),
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
    issues.extend(_validate_redirections(segment, rule, index))
    return tuple(issues)


def _validate_redirections(
    segment: CommandSegment,
    rule: CommandRule,
    index: int,
) -> tuple[ValidationIssue, ...]:
    expected = tuple(
        (redirection.source_fd, redirection.operator, redirection.target)
        for redirection in rule.required_redirections
    )
    actual = tuple(
        (
            1 if redirection.source_fd is None else redirection.source_fd,
            redirection.operator.value,
            redirection.target,
        )
        for redirection in segment.redirections
    )
    issues: list[ValidationIssue] = []

    if expected and not _is_subsequence(expected, actual):
        description = ", ".join(_format_redirection(*item) for item in expected)
        issues.append(
            ValidationIssue(
                IssueKind.MISSING_REDIRECTION,
                f"ожидалась последовательность перенаправлений: {description}",
                index,
            )
        )
    if not rule.allow_extra_redirections and not _is_subsequence(actual, expected):
        description = ", ".join(_format_redirection(*item) for item in actual)
        issues.append(
            ValidationIssue(
                IssueKind.EXTRA_REDIRECTION,
                f"неожиданная последовательность перенаправлений: {description}",
                index,
            )
        )
    return tuple(issues)


def _is_subsequence(
    candidate: tuple[tuple[int, str, str], ...],
    sequence: tuple[tuple[int, str, str], ...],
) -> bool:
    position = 0
    for item in sequence:
        if position < len(candidate) and candidate[position] == item:
            position += 1
    return position == len(candidate)


def _is_subsequence_arguments(candidate: tuple[str, ...], sequence: tuple[str, ...]) -> bool:
    position = 0
    for argument in sequence:
        if position < len(candidate) and candidate[position] == argument:
            position += 1
    return position == len(candidate)


def _format_redirection(source_fd: int, operator: str, target: str) -> str:
    prefix = "" if source_fd == 1 and operator != ">&" else str(source_fd)
    return f"{prefix}{operator}{target}"


def _canonical_flag(flag: str, rule: CommandRule) -> str:
    return rule.flag_aliases.get(flag, flag)
