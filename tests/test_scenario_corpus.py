from pathlib import Path

from linux_learning.scenario_loader import load_scenarios
from linux_learning.validator import validate_command

_REFERENCE_SOLUTIONS = {
    "packages.install_nginx": "apt install nginx",
    "services.restart_nginx": "systemctl restart nginx",
    "logging.filter_nginx_errors": (
        "journalctl -u nginx | grep -i error > /var/log/nginx-errors.log 2>&1"
    ),
    "network.listening_tcp": "ss -ltnp",
    "network.allow_https": "ufw allow 443/tcp",
    "permissions.secure_config": "chmod 640 /etc/app.conf",
    "files.archive_web_root": "tar -czf /var/backups/site.tar.gz /var/www/html",
    "diagnostics.root_usage": "df --human-readable /",
}


def test_reference_solutions_match_all_scenarios() -> None:
    scenarios = load_scenarios(Path("scenarios"))
    by_id = {scenario.id: scenario for scenario in scenarios}

    assert set(by_id) == set(_REFERENCE_SOLUTIONS)
    for scenario_id, command in _REFERENCE_SOLUTIONS.items():
        result = validate_command(command, by_id[scenario_id])

        assert result.valid, f"{scenario_id}: {result.issues}"
