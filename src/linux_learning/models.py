from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScenarioLevel(StrEnum):
    # сложность сценария
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class HintLevel(StrEnum):
    # уровень раскрытия подсказки
    CONCEPT = "concept"
    TOOLS = "tools"
    SOLUTION = "solution"


class Hint(BaseModel):
    """подсказка выдаваемая после запроса юзера"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    level: HintLevel
    text: str = Field(min_length=1)
    progress_penalty: int = Field(default=0, ge=0)


class RedirectionRule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_fd: int = Field(default=1, ge=0)
    operator: Literal[">", ">>", ">&"]
    target: str = Field(min_length=1)


class CommandRule(BaseModel):
    """ограничения для 1 элемента команды"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    executable: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    flag_aliases: dict[str, str] = Field(default_factory=dict)
    flag_descriptions: dict[str, str] = Field(default_factory=dict)
    required_subcommands: tuple[str, ...] = ()
    required_flags: tuple[str, ...] = ()
    forbidden_flags: tuple[str, ...] = ()
    conflicting_flag_pairs: tuple[tuple[str, str], ...] = ()
    value_flags: tuple[str, ...] = ()
    required_arguments: tuple[str, ...] = ()
    required_redirections: tuple[RedirectionRule, ...] = ()
    allow_extra_arguments: bool = True
    allow_extra_redirections: bool = True

    @field_validator(
        "aliases",
        "required_subcommands",
        "required_flags",
        "forbidden_flags",
        "value_flags",
        "required_arguments",
        mode="after",
    )
    @classmethod
    def validate_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value)
        if any(not item for item in cleaned):
            raise ValueError("элементы ограничений не могут быть пустыми")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("элементы ограничений не должны повторяться")
        return cleaned

    @field_validator("value_flags")
    @classmethod
    def validate_value_flags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            len(flag) != 2 or not flag.startswith("-") or flag.startswith("--") for flag in value
        ):
            raise ValueError("флаги со значением должны быть короткими")
        return value

    @field_validator("flag_aliases")
    @classmethod
    def validate_flag_aliases(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned = {key.strip(): alias.strip() for key, alias in value.items()}
        if any(not key or not alias for key, alias in cleaned.items()):
            raise ValueError("синонимы флагов не могут быть пустыми")
        if len(cleaned) != len(value):
            raise ValueError("синонимы флагов не должны повторяться")
        return cleaned

    @field_validator("flag_descriptions")
    @classmethod
    def validate_flag_descriptions(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned = {key.strip(): description.strip() for key, description in value.items()}
        if any(not key or not description for key, description in cleaned.items()):
            raise ValueError("описания флагов не могут быть пустыми")
        return cleaned

    @field_validator("conflicting_flag_pairs")
    @classmethod
    def validate_conflicting_flag_pairs(
        cls,
        value: tuple[tuple[str, str], ...],
    ) -> tuple[tuple[str, str], ...]:
        cleaned = tuple((first.strip(), second.strip()) for first, second in value)
        if any(not first or not second or first == second for first, second in cleaned):
            raise ValueError("пара конфликтующих флагов должна содержать два разных флага")
        if len({frozenset(pair) for pair in cleaned}) != len(cleaned):
            raise ValueError("пары конфликтующих флагов не должны повторяться")
        return cleaned

    @model_validator(mode="after")
    def validate_flags(self) -> Self:
        conflicts = set(self.required_flags) & set(self.forbidden_flags)
        if conflicts:
            names = ", ".join(sorted(conflicts))
            raise ValueError(f"флаг одновременно обязателен и запрещен: {names}")
        return self


class Scenario(BaseModel):
    """описание задания"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_.]*$")
    title: str = Field(min_length=1)
    level: ScenarioLevel
    topic: str = Field(min_length=1)
    role: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    command_rules: tuple[CommandRule, ...] = Field(min_length=1)
    hints: tuple[Hint, ...] = Field(min_length=3, max_length=3)
    success_explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_hints(self) -> Self:
        levels = {hint.level for hint in self.hints}
        expected = set(HintLevel)
        if levels != expected:
            missing = ", ".join(level.value for level in expected - levels)
            extra = ", ".join(level.value for level in levels - expected)
            details: list[str] = []
            if missing:
                details.append(f"отсутствуют: {missing}")
            if extra:
                details.append(f"неизвестные: {extra}")
            raise ValueError("набор подсказок должен содержать три уровня, " + "; ".join(details))
        return self
