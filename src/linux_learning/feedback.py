from dataclasses import dataclass
from enum import StrEnum

from linux_learning.command_parser import (
    CommandSegment,
    ParsedCommandLine,
    Redirection,
    RedirectionOperator,
)
from linux_learning.models import CommandRule, Scenario
from linux_learning.validator import IssueKind, ValidationIssue, ValidationResult


class FeedbackKind(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Feedback:
    kind: FeedbackKind
    title: str
    details: tuple[str, ...]
    explanation: str
    issues: tuple[ValidationIssue, ...] = ()


_ISSUE_TITLES = {
    IssueKind.SYNTAX: "ошибка синтаксиса",
    IssueKind.PIPELINE: "ошибка структуры команды",
    IssueKind.WRONG_TOOL: "неверная утилита",
    IssueKind.MISSING_SUBCOMMAND: "пропущена подкоманда",
    IssueKind.MISSING_FLAG: "пропущен обязательный флаг",
    IssueKind.FORBIDDEN_FLAG: "использован запрещенный флаг",
    IssueKind.MISSING_ARGUMENT: "пропущен обязательный аргумент",
    IssueKind.EXTRA_ARGUMENT: "лишний аргумент",
}


def build_feedback(result: ValidationResult, scenario: Scenario) -> Feedback:
    if not result.valid:
        title = _ISSUE_TITLES[result.issues[0].kind]
        return Feedback(
            kind=FeedbackKind.ERROR,
            title=title,
            details=tuple(issue.message for issue in result.issues),
            explanation="исправь указанную часть команды и повтори попытку",
            issues=result.issues,
        )

    if result.parsed is None:
        raise ValueError("для успешного результата отсутствует разобранная команда")
    return Feedback(
        kind=FeedbackKind.SUCCESS,
        title="команда принята",
        details=(_describe_pipeline(result.parsed, scenario),),
        explanation=scenario.success_explanation,
    )


def _describe_pipeline(parsed: ParsedCommandLine, scenario: Scenario) -> str:
    parts = [
        _describe_segment(segment, rule)
        for segment, rule in zip(parsed.segments, scenario.command_rules, strict=False)
    ]
    return " вывод передан через пайп. ".join(parts)


def _describe_segment(segment: CommandSegment, rule: CommandRule) -> str:
    result = [f"утилита {segment.executable}"]
    if segment.flags:
        flags = []
        for flag in segment.flags:
            canonical = rule.flag_aliases.get(flag, flag)
            description = rule.flag_descriptions.get(canonical, "флаг передан")
            flags.append(f"{canonical}: {description}")
        result.append("флаги: " + ", ".join(flags))
    if segment.positionals:
        result.append("аргументы: " + ", ".join(segment.positionals))
    if segment.redirections:
        descriptions = ", ".join(
            _describe_redirection(redirection) for redirection in segment.redirections
        )
        result.append("перенаправления: " + descriptions)
    return "; ".join(result)


def _describe_redirection(redirection: Redirection) -> str:
    operator = redirection.operator
    if operator is RedirectionOperator.WRITE:
        return f"вывод в {redirection.target}"
    if operator is RedirectionOperator.APPEND:
        return f"добавление вывода в {redirection.target}"
    return f"дескриптор {redirection.source_fd} направлен в {redirection.target}"
