import pytest

from linux_learning.command_parser import RedirectionOperator, parse_command
from linux_learning.errors import CommandParseError


def test_parse_command_splits_flags_and_applies_aliases() -> None:
    command = parse_command("ls -lah --all ./logs", {"--all": "-a"})

    segment = command.segments[0]
    assert segment.executable == "ls"
    assert segment.flags == ("-l", "-a", "-h", "-a")
    assert segment.positionals == ("./logs",)


def test_parse_command_preserves_pipeline_and_redirections() -> None:
    command = parse_command("journalctl -u nginx | grep -i error >> errors.log 2>&1")

    assert len(command.segments) == 2
    assert command.segments[0].executable == "journalctl"
    assert command.segments[1].executable == "grep"
    assert len(command.segments[1].redirections) == 2
    assert command.segments[1].redirections[0].operator == RedirectionOperator.APPEND
    assert command.segments[1].redirections[1].source_fd == 2
    assert command.segments[1].redirections[1].target == "1"


def test_parse_command_keeps_quoted_operators_as_arguments() -> None:
    command = parse_command('grep "error | warning" /var/log/syslog')

    assert len(command.segments) == 1
    assert command.segments[0].positionals == ("error | warning", "/var/log/syslog")


@pytest.mark.parametrize(
    "text, message",
    [
        ("grep \"error", "кавычка не закрыта"),
        ("journalctl |", "команда отсутствует после пайпа"),
        ("cat >", "для перенаправления не указан поток или файл"),
        ("echo one && echo two", "оператор не поддерживается: &&"),
    ],
)
def test_parse_command_rejects_invalid_syntax(text: str, message: str) -> None:
    with pytest.raises(CommandParseError, match=message):
        parse_command(text)
