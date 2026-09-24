from pathlib import Path

from linux_learning.scenario_loader import load_scenarios
from linux_learning.validator import validate_command

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
}


def test_reference_solutions_match_all_scenarios() -> None:
    scenarios = load_scenarios(Path("scenarios"))
    by_id = {scenario.id: scenario for scenario in scenarios}

    assert set(by_id) == set(_REFERENCE_SOLUTIONS)
    for scenario_id, command in _REFERENCE_SOLUTIONS.items():
        result = validate_command(command, by_id[scenario_id])

        assert result.valid, f"{scenario_id}: {result.issues}"
