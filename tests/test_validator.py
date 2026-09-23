from linux_learning.models import CommandRule, Hint, HintLevel, Scenario, ScenarioLevel
from linux_learning.validator import IssueKind, validate_command


def make_scenario(*rules: CommandRule) -> Scenario:
    return Scenario(
        id="test.scenario",
        title="тест",
        level=ScenarioLevel.BEGINNER,
        topic="test",
        role="root@test:~#",
        objective="проверить команду",
        command_rules=rules,
        hints=tuple(
            Hint(level=level, text=level.value)
            for level in HintLevel
        ),
        success_explanation="команда корректна",
    )


def test_validate_command_accepts_flag_order_and_aliases() -> None:
    scenario = make_scenario(
        CommandRule(
            executable="grep",
            required_flags=("-i", "-n"),
            flag_aliases={"--ignore-case": "-i"},
            required_arguments=("error", "/var/log/syslog"),
            allow_extra_arguments=False,
        )
    )

    result = validate_command("grep -ni --ignore-case error /var/log/syslog", scenario)

    assert result.valid
    assert result.issues == ()


def test_validate_command_reports_wrong_tool() -> None:
    scenario = make_scenario(CommandRule(executable="systemctl"))

    result = validate_command("service nginx restart", scenario)

    assert not result.valid
    assert result.issues[0].kind == IssueKind.WRONG_TOOL


def test_validate_command_reports_missing_and_forbidden_flags() -> None:
    scenario = make_scenario(
        CommandRule(
            executable="grep",
            required_flags=("-i",),
            forbidden_flags=("-r",),
        )
    )

    result = validate_command("grep -r error", scenario)

    assert [issue.kind for issue in result.issues] == [
        IssueKind.MISSING_FLAG,
        IssueKind.FORBIDDEN_FLAG,
    ]


def test_validate_command_checks_pipeline_shape() -> None:
    scenario = make_scenario(
        CommandRule(executable="journalctl"),
        CommandRule(executable="grep", required_flags=("-i",)),
    )

    result = validate_command("journalctl -u nginx | grep -i error", scenario)

    assert result.valid


def test_validate_command_reports_syntax_error() -> None:
    scenario = make_scenario(CommandRule(executable="echo"))

    result = validate_command('echo "broken', scenario)

    assert not result.valid
    assert result.issues[0].kind == IssueKind.SYNTAX
