# linux learning

Консольный тренажер командной строки

## Зачем нужен проект

Тренажер помогает перейти от чтения справки к безопасной практике. Каждое задание описывает рабочую ситуацию на debian или ubuntu. Пользователь вводит команду, а приложение проверяет ее, показывает результат и объясняет ошибки

## Установка

Требуется python 3.14

```text
python -m venv .venv
```

Активация окружения в powershell:

```text
.\.venv\Scripts\Activate.ps1
```

Активация окружения в bash:

```text
source .venv/bin/activate
```

Установка проекта вместе с инструментами разработки:

```text
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Запуск

Приложение стартует командой:

```text
linux-learning
```

## Генерация черновиков сценариев

Генератор читает локальные markdown-страницы tldr для Linux. Сеть ему не нужна. Черновики создаются отдельно от каталога `scenarios` и не используются тренажером до редакторской проверки.

```text
python -m linux_learning.scenario_generator путь/к/tldr/pages/linux --output-dir scenario-drafts
```

По умолчанию выбираются страницы `apt`, `systemctl`, `journalctl`, `ip`, `ss`, `ufw`, `chmod`, `chown`, `tar`, `grep`, `sed`, `awk` и `docker`. Повторная генерация не перезаписывает существующие черновики; для явной перезаписи передайте `--overwrite`.

## Проверка качества

```text
ruff check .
ruff format --check .
mypy src
pytest
```
