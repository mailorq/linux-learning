from enum import StrEnum
from typing import Self

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


class CommandRule(BaseModel):
    """ограничения для 1 элемента команды"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    executable: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    required_subcommands: tuple[str, ...] = ()
    required_flags: tuple[str, ...] = ()
    forbidden_flags: tuple[str, ...] = ()
    required_arguments: tuple[str, ...] = ()
    allow_extra_arguments: bool = True

    @field_validator(
        "aliases",
        "required_subcommands",
        "required_flags",
        "forbidden_flags",
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
