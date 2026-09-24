from linux_learning.models import (
    CommandRule,
    Hint,
    HintLevel,
    RedirectionRule,
    Scenario,
    ScenarioLevel,
)
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
        hints=tuple(Hint(level=level, text=level.value) for level in HintLevel),
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


def test_validate_command_accepts_attached_value_in_short_flag_group() -> None:
    scenario = make_scenario(
        CommandRule(
            executable="tar",
            value_flags=("-f",),
            required_flags=("-c", "-z", "-f"),
            required_arguments=("archive.tar.gz", "./dir"),
            allow_extra_arguments=False,
        )
    )

    result = validate_command("tar -czfarchive.tar.gz ./dir", scenario)

    assert result.valid


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
        CommandRule(executable="journalctl", allowed_flags=("-u",)),
        CommandRule(executable="grep", required_flags=("-i",)),
    )

    result = validate_command("journalctl -u nginx | grep -i error", scenario)

    assert result.valid


def test_validate_command_checks_redirections_for_each_pipeline_segment() -> None:
    scenario = make_scenario(
        CommandRule(executable="journalctl", allowed_flags=("-u",)),
        CommandRule(
            executable="grep",
            required_flags=("-i",),
            required_arguments=("error",),
            required_redirections=(
                RedirectionRule(operator=">>", target="errors.log"),
                RedirectionRule(source_fd=2, operator=">&", target="1"),
            ),
            allow_extra_redirections=False,
        ),
    )

    result = validate_command(
        "journalctl -u nginx | grep -i error >> errors.log 2>&1",
        scenario,
    )

    assert result.valid


def test_validate_command_reports_missing_and_extra_redirections() -> None:
    scenario = make_scenario(
        CommandRule(
            executable="echo",
            required_redirections=(RedirectionRule(operator=">", target="output.log"),),
            allow_extra_redirections=False,
        )
    )

    result = validate_command("echo ready > other.log", scenario)

    assert [issue.kind for issue in result.issues] == [
        IssueKind.MISSING_REDIRECTION,
        IssueKind.EXTRA_REDIRECTION,
    ]


def test_validate_command_reports_syntax_error() -> None:
    scenario = make_scenario(CommandRule(executable="echo"))

    result = validate_command('echo "broken', scenario)

    assert not result.valid
    assert result.issues[0].kind == IssueKind.SYNTAX


def test_validate_command_rejects_required_arguments_in_wrong_order() -> None:
    scenario = make_scenario(
        CommandRule(
            executable="chmod",
            required_arguments=("640", "/etc/app.conf"),
            allow_extra_arguments=False,
        )
    )

    result = validate_command("chmod /etc/app.conf 640", scenario)

    assert not result.valid
    assert result.issues[0].kind == IssueKind.ARGUMENT_ORDER


def test_validate_command_reports_conflicting_flags() -> None:
    scenario = make_scenario(
        CommandRule(
            executable="tar",
            value_flags=("-f",),
            allowed_flags=("-f",),
            conflicting_flag_pairs=(("-c", "-x"),),
        )
    )

    result = validate_command("tar -cxf archive.tar ./dir", scenario)

    assert not result.valid
    assert result.issues[0].kind == IssueKind.CONFLICTING_FLAGS


def test_validate_command_suggests_close_required_argument() -> None:
    scenario = make_scenario(
        CommandRule(
            executable="systemctl",
            required_subcommands=("restart",),
            required_arguments=("nginx",),
            allow_extra_arguments=False,
        )
    )

    result = validate_command("systemctl restart ngixn", scenario)
    missing_argument = next(
        issue for issue in result.issues if issue.kind == IssueKind.MISSING_ARGUMENT
    )

    assert not result.valid
    assert "возможно, вместо него указан ngixn" in missing_argument.message


def test_validate_command_rejects_unlisted_flags() -> None:
    scenario = make_scenario(
        CommandRule(
            executable="grep",
            required_flags=("-i",),
            required_arguments=("error",),
            allow_extra_arguments=False,
        )
    )

    result = validate_command("grep -iv error", scenario)

    assert not result.valid
    assert [issue.kind for issue in result.issues] == [IssueKind.EXTRA_FLAG]
