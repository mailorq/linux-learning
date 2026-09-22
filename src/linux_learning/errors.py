from pathlib import Path


class ScenarioError(Exception):
    """базовая ошибка работы"""

class ScenarioSourceError(ScenarioError):
    """ошибка рида файла или каталога"""
    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


class ScenarioFormatError(ScenarioError):
    """ошибка структуры или содержимого"""
    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message
