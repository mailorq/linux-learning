from pathlib import Path

from linux_learning.scenario_loader import load_scenarios
from linux_learning.validator import IssueKind, validate_command

_REFERENCE_SOLUTIONS = {
    "packages.install_nginx": "apt install nginx",
    "packages.update_index": "apt update",
    "services.restart_nginx": "systemctl restart nginx",
    "services.check_nginx": "systemctl is-active nginx",
    "services.enable_nginx": "systemctl enable --now nginx",
    "services.failed_units": "systemctl --failed --no-pager",
    "services.reload_manager": "systemctl daemon-reload",
    "logging.filter_nginx_errors": (
        "journalctl -u nginx | grep -i error > /var/log/nginx-errors.log 2>&1"
    ),
    "logging.search_error_patterns": "grep -Ein 'error|failed' /var/log/syslog",
    "network.listening_tcp": "ss -ltnp",
    "network.allow_https": "ufw allow 443/tcp",
    "network.show_routes": "ip route show",
    "permissions.secure_config": "chmod 640 /etc/app.conf",
    "permissions.change_web_owner": "chown www-data:www-data /var/www/html",
    "files.archive_web_root": "tar -czf /var/backups/site.tar.gz /var/www/html",
    "diagnostics.root_usage": "df --human-readable /",
    "containers.list_all": "docker ps --all",
    "containers.inspect_web": "docker inspect web",
    "packages.simulate_upgrade": "apt-get -s upgrade",
    "diagnostics.directory_usage": "du -sh /var/log",
    "diagnostics.memory_summary": "free -h",
    "processes.list_all": "ps -ef",
    "storage.list_filesystems": "lsblk -f",
    "users.show_identity": "id www-data",
    "containers.disk_usage": "docker system df",
    "containers.list_dangling_volumes": "docker volume ls --filter dangling=true",
    "containers.prune_lab_volumes": ("docker volume prune --all --filter label=project=lab"),
    "containers.prune_stopped": "docker container prune --filter until=24h",
    "containers.prune_build_cache": "docker buildx prune --filter until=24h",
}


def test_reference_solutions_match_all_scenarios() -> None:
    scenarios = load_scenarios(Path("scenarios"))
    by_id = {scenario.id: scenario for scenario in scenarios}

    assert set(by_id) == set(_REFERENCE_SOLUTIONS)
    for scenario_id, command in _REFERENCE_SOLUTIONS.items():
        result = validate_command(command, by_id[scenario_id])

        assert result.valid, f"{scenario_id}: {result.issues}"


def test_scenarios_reject_flags_that_change_the_requested_action() -> None:
    scenarios = {scenario.id: scenario for scenario in load_scenarios(Path("scenarios"))}
    commands = {
        "packages.install_nginx": "apt install nginx -s",
        "diagnostics.root_usage": "df -ih /",
        "services.failed_units": "systemctl --failed --no-pager --user",
        "network.show_routes": "ip -6 route show",
        "network.listening_tcp": "ss -ltnp -K",
        "logging.search_error_patterns": "grep -Einv 'error|failed' /var/log/syslog",
        "containers.prune_lab_volumes": (
            "docker volume prune --all --filter label=project=lab --force"
        ),
        "containers.prune_stopped": "docker container prune --filter until=24h --force",
        "containers.prune_build_cache": "docker buildx prune --filter until=24h --force",
    }

    for scenario_id, command in commands.items():
        result = validate_command(command, scenarios[scenario_id])

        assert not result.valid, f"{scenario_id} accepted {command}"
        assert any(issue.kind is IssueKind.EXTRA_FLAG for issue in result.issues)


def test_volume_filter_alias_is_allowed_but_force_is_not() -> None:
    scenarios = {scenario.id: scenario for scenario in load_scenarios(Path("scenarios"))}
    list_result = validate_command(
        "docker volume ls -f dangling=true",
        scenarios["containers.list_dangling_volumes"],
    )
    prune_result = validate_command(
        "docker volume prune --all --filter label=project=lab -f",
        scenarios["containers.prune_lab_volumes"],
    )

    assert list_result.valid
    assert not prune_result.valid
    assert any(issue.kind is IssueKind.EXTRA_FLAG for issue in prune_result.issues)
