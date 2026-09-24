from pathlib import Path

from linux_learning.feedback import FeedbackKind, build_feedback
from linux_learning.scenario_loader import load_scenario
from linux_learning.validator import validate_command


def test_build_feedback_explains_successful_command() -> None:
    scenario = load_scenario(Path("scenarios/apt_install_nginx.yaml"))
    result = validate_command("apt install nginx", scenario)

    feedback = build_feedback(result, scenario)

    assert feedback.kind is FeedbackKind.SUCCESS
    assert feedback.title == "команда принята"
    assert "утилита apt" in feedback.details[0]
    assert "nginx" in feedback.explanation


def test_build_feedback_classifies_wrong_tool() -> None:
    scenario = load_scenario(Path("scenarios/apt_install_nginx.yaml"))
    result = validate_command("service nginx restart", scenario)

    feedback = build_feedback(result, scenario)

    assert feedback.kind is FeedbackKind.ERROR
    assert feedback.title == "неверная утилита"
    assert feedback.details == ("ожидалась утилита apt, получена service",)


def test_build_feedback_classifies_wrong_argument_order() -> None:
    scenario = load_scenario(Path("scenarios/chmod_secure_config.yaml"))
    result = validate_command("chmod /etc/app.conf 640", scenario)

    feedback = build_feedback(result, scenario)

    assert feedback.kind is FeedbackKind.ERROR
    assert feedback.title == "неверный порядок аргументов"
    assert feedback.details == (
        "позиционные аргументы указаны не в требуемом порядке: 640 /etc/app.conf",
    )


def test_build_feedback_classifies_conflicting_flags() -> None:
    scenario = load_scenario(Path("scenarios/tar_archive_web_root.yaml"))
    result = validate_command("tar -czxf /var/backups/site.tar.gz /var/www/html", scenario)

    feedback = build_feedback(result, scenario)

    assert feedback.kind is FeedbackKind.ERROR
    assert feedback.title == "конфликтующие флаги"
    assert feedback.details == ("несовместимые флаги указаны вместе: -c и -x",)
