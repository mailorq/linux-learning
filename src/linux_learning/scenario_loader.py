from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import ValidationError

from linux_learning.errors import ScenarioFormatError, ScenarioSourceError
from linux_learning.models import Scenario

_SCENARIO_SUFFIXES = {".yaml", ".yml"}


def load_scenario(path: Path) -> Scenario:
    """загрузить один сценарий"""

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ScenarioSourceError(path, "не удалось прочитать файл") from exc

    try:
        raw_data: object = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ScenarioFormatError(path, "некорректный yaml") from exc

    if not isinstance(raw_data, Mapping):
        raise ScenarioFormatError(path, "корневой элемент должен быть объектом")

    try:
        return Scenario.model_validate(raw_data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ScenarioFormatError(path, details) from exc


def load_scenarios(directory: Path) -> tuple[Scenario, ...]:
    """загрузить все сценарии из каталога"""

    if not directory.exists():
        raise ScenarioSourceError(directory, "каталог не найден")
    if not directory.is_dir():
        raise ScenarioSourceError(directory, "путь не является каталргом")

    try:
        paths = sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in _SCENARIO_SUFFIXES
        )
    except OSError as exc:
        raise ScenarioSourceError(directory, "не удалось прочитать каталог") from exc

    if not paths:
        raise ScenarioSourceError(directory, "каталог не содержит yaml сценариев")

    scenarios = tuple(load_scenario(path) for path in paths)
    ids = [scenario.id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        duplicates = sorted({scenario_id for scenario_id in ids if ids.count(scenario_id) > 1})
        names = ", ".join(duplicates)
        raise ScenarioFormatError(directory, f"повторяющиеся идентификаторы: {names}")
    return scenarios
