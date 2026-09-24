import shlex
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum

from linux_learning.errors import CommandParseError


class RedirectionOperator(StrEnum):
    WRITE = ">"
    APPEND = ">>"
    DUPLICATE = ">&"


@dataclass(frozen=True, slots=True)
class Redirection:
    source_fd: int | None
    operator: RedirectionOperator
    target: str


@dataclass(frozen=True, slots=True)
class CommandSegment:
    executable: str
    arguments: tuple[str, ...]
    flags: tuple[str, ...]
    positionals: tuple[str, ...]
    redirections: tuple[Redirection, ...]


@dataclass(frozen=True, slots=True)
class ParsedCommandLine:
    segments: tuple[CommandSegment, ...]


@dataclass(frozen=True, slots=True)
class _Token:
    value: str
    operator: bool
    fd: int | None = None


def parse_command(
    text: str,
    flag_aliases: Mapping[str, str] | None = None,
    value_flags_by_executable: Mapping[str, Collection[str]] | None = None,
) -> ParsedCommandLine:
    tokens = _tokenize(text)
    segments: list[CommandSegment] = []
    words: list[_Token] = []
    redirections: list[Redirection] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if token.operator and token.value == "|":
            if not words:
                raise CommandParseError("пайп не может начинаться или повторяться")
            segments.append(
                _build_segment(words, redirections, flag_aliases, value_flags_by_executable)
            )
            words = []
            redirections = []
            index += 1
            continue

        if token.operator and token.value in {">", ">>"}:
            source_fd = _pop_source_fd(words)
            target, index = _take_target(tokens, index)
            operator = RedirectionOperator(token.value)
            redirections.append(Redirection(source_fd, operator, target))
            continue

        if token.operator and token.value == ">&":
            source_fd = _pop_source_fd(words)
            if source_fd is None:
                source_fd = 1
            target, index = _take_target(tokens, index)
            if not target.isdigit():
                raise CommandParseError("дублирование потока требует номер файлового дескриптора")
            redirections.append(Redirection(source_fd, RedirectionOperator.DUPLICATE, target))
            continue

        if token.operator:
            raise CommandParseError(f"оператор не поддерживается: {token.value}")

        words.append(token)
        index += 1

    if not words:
        raise CommandParseError("команда отсутствует после пайпа")
    segments.append(_build_segment(words, redirections, flag_aliases, value_flags_by_executable))
    return ParsedCommandLine(tuple(segments))


def _tokenize(text: str) -> tuple[_Token, ...]:
    if not text.strip():
        raise CommandParseError("команда пуста")

    tokens: list[_Token] = []
    word: list[str] = []
    quote: str | None = None
    index = 0

    def flush_word() -> None:
        if not word:
            return
        raw = "".join(word)
        try:
            values = shlex.split(raw, posix=True)
        except ValueError as exc:
            raise CommandParseError("ошибка кавычек или экранирования") from exc
        if len(values) != 1:
            raise CommandParseError("не удалось выделить аргумент команды")
        fd = int(raw) if raw.isascii() and raw.isdigit() else None
        tokens.append(_Token(values[0], False, fd))
        word.clear()

    while index < len(text):
        char = text[index]
        if quote is None:
            if char.isspace():
                flush_word()
                index += 1
                continue
            if char in "|><&;":
                flush_word()
                operator = char
                if index + 1 < len(text):
                    pair = text[index : index + 2]
                    if pair in {"||", "&&", ">>", ">&", ";;"}:
                        operator = pair
                        index += 1
                tokens.append(_Token(operator, True))
                index += 1
                continue
            if char == "\\":
                if index + 1 == len(text):
                    raise CommandParseError("экранирование не завершено")
                word.extend((char, text[index + 1]))
                index += 2
                continue
            if char in "'\"":
                quote = char
            word.append(char)
            index += 1
            continue

        word.append(char)
        if quote == '"' and char == "\\":
            if index + 1 == len(text):
                raise CommandParseError("экранирование не завершено")
            word.append(text[index + 1])
            index += 2
            continue
        if char == quote:
            quote = None
        index += 1

    if quote is not None:
        raise CommandParseError("кавычка не закрыта")
    flush_word()
    return tuple(tokens)


def _pop_source_fd(words: list[_Token]) -> int | None:
    if words and words[-1].fd is not None:
        return words.pop().fd
    return None


def _take_target(tokens: tuple[_Token, ...], index: int) -> tuple[str, int]:
    target_index = index + 1
    if target_index >= len(tokens) or tokens[target_index].operator:
        raise CommandParseError("для перенаправления не указан поток или файл")
    return tokens[target_index].value, target_index + 1


def _build_segment(
    words: list[_Token],
    redirections: list[Redirection],
    flag_aliases: Mapping[str, str] | None,
    value_flags_by_executable: Mapping[str, Collection[str]] | None,
) -> CommandSegment:
    executable = words[0].value
    if not executable:
        raise CommandParseError("имя утилиты не может быть пустым")
    value_flags = (
        value_flags_by_executable.get(executable, ())
        if value_flags_by_executable is not None
        else ()
    )
    arguments = _normalize_arguments(
        tuple(word.value for word in words[1:]), flag_aliases, value_flags
    )
    flags: list[str] = []
    positionals: list[str] = []
    options = True
    for argument in arguments:
        if argument == "--" and options:
            options = False
            continue
        if options and argument.startswith("-") and argument != "-":
            flags.append(argument)
        else:
            positionals.append(argument)
    return CommandSegment(
        executable=executable,
        arguments=arguments,
        flags=tuple(flags),
        positionals=tuple(positionals),
        redirections=tuple(redirections),
    )


def _normalize_arguments(
    arguments: tuple[str, ...],
    flag_aliases: Mapping[str, str] | None,
    value_flags: Collection[str] = (),
) -> tuple[str, ...]:
    aliases = flag_aliases or {}
    value_options = {aliases.get(flag, flag) for flag in value_flags}
    normalized: list[str] = []
    options = True
    for argument in arguments:
        if not options:
            normalized.append(argument)
            continue
        if argument == "--":
            normalized.append(argument)
            options = False
            continue
        if argument.startswith("--") and "=" in argument:
            flag, value = argument.split("=", maxsplit=1)
            normalized.extend((aliases.get(flag, flag), value))
            continue

        argument = aliases.get(argument, argument)
        if len(argument) > 2 and argument.startswith("-") and not argument.startswith("--"):
            tail = argument[1:]
            expanded: list[str] = []
            for index, char in enumerate(tail):
                if not char.isascii() or not char.isalpha():
                    normalized.append(argument)
                    break
                flag = aliases.get(f"-{char}", f"-{char}")
                expanded.append(flag)
                if flag in value_options:
                    value = tail[index + 1 :]
                    if value.startswith("="):
                        value = value[1:]
                    if value:
                        expanded.append(value)
                    normalized.extend(expanded)
                    break
            else:
                normalized.extend(expanded)
            continue
        normalized.append(argument)
    return tuple(normalized)
