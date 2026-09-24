# Сценарии

Каждый yaml-файл описывает одно задание. `command_rules` задает допустимую структуру команды, `hints` дает три уровня подсказки, а `success_explanation` поясняет принятое решение

`required_flags` задает обязательные флаги, `allowed_flags` явно разрешает дополнительные флаги, а `forbidden_flags` отклоняет нежелательные. Неуказанные флаги не принимаются, чтобы команда не меняла смысл задания

Данные вынесены в yaml, чтобы менять задания и добавлять новые без правок движка. При загрузке pydantic проверяет поля и типы, поэтому опечатка в конфигурации обнаруживается до начала сессии.

## Состав

### Пакеты

`apt_install_nginx.yaml` устанавливает пакет, `apt_update_index.yaml` обновляет индекс, `apt_simulate_upgrade.yaml` показывает план обновления без его применения

### Службы и Журналы

`systemctl_check_nginx.yaml` проверяет состояние nginx, `systemctl_restart_nginx.yaml` перезапускает службу, `services_enable_nginx.yaml` включает запуск при старте и запускает службу сейчас, `services_failed_units.yaml` показывает упавшие юниты, `services_reload_manager.yaml` перечитывает определения юнитов systemd

`journalctl_filter_nginx_errors.yaml` соединяет журнал, фильтр grep и перенаправление вывода. `logging_search_error_patterns.yaml` ищет несколько вариантов текста с учетом регистра и номеров строк

### Сеть

`ss_listening_tcp.yaml` показывает tcp-порты в состоянии ожидания, `ufw_allow_https.yaml` добавляет правило для https, `ip_show_routes.yaml` выводит таблицу маршрутизации

### Права и Файлы

`chmod_secure_config.yaml` задает режим доступа к конфигурации, `chown_web_root.yaml` меняет владельца веб-каталога, `tar_archive_web_root.yaml` создает архив каталога

### Диагностика и Контейнеры

`df_root_usage.yaml` проверяет занятое место файловой системы, `diagnostics_directory_usage.yaml` считает размер каталога, `diagnostics_memory_summary.yaml` показывает оперативную память, `processes_list_all.yaml` выводит снимок процессов, `storage_list_filesystems.yaml` показывает файловые системы блочных устройств, `users_show_identity.yaml` проверяет uid и группы пользователя

`containers_disk_usage.yaml` показывает использование диска Docker, `containers_list_dangling_volumes.yaml` находит неиспользуемые тома без удаления, `containers_prune_lab_volumes.yaml` удаляет только неиспользуемые тома с меткой учебного проекта на Docker API 1.42 или новее, `containers_prune_stopped.yaml` ограничивает очистку остановленных контейнеров возрастом, `containers_prune_build_cache.yaml` удаляет записи build cache, не использовавшиеся 24 часа. Команды очистки оставляют штатный запрос подтверждения

`docker_list_all.yaml` показывает работающие и остановленные контейнеры, `containers_inspect_web.yaml` выводит параметры контейнера
