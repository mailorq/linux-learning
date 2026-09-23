from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from linux_learning.scenario_generator import (
    ScenarioDraft,
    ScenarioGenerationError,
    generate_scenario_drafts,
)


def test_generate_scenario_drafts_from_local_tldr_pages() -> None:
    with TemporaryDirectory(dir=Path.cwd(), prefix=".scenario-generator-") as directory:
        root = Path(directory)
        source = root / "pages"
        output = root / "drafts"
        source.mkdir()
        (source / "apt.md").write_text(
            "# apt\n"
            "> package manager examples\n"
            "- refresh package indexes:\n"
            "`sudo apt update`\n"
            "- install a package:\n"
            "`sudo apt install {{package}}`\n",
            encoding="utf-8",
        )
        (source / "curl.md").write_text("# curl\n`curl https://example.test`\n", encoding="utf-8")
        (source / "tar.md").write_text(
            "# tar\n- create a compressed archive:\n`tar -czfarchive.tar.gz ./dir`\n",
            encoding="utf-8",
        )

        files = generate_scenario_drafts(source, output)

        assert len(files) == 3
        first_raw: object = yaml.safe_load(files[0].read_text(encoding="utf-8"))
        first = ScenarioDraft.model_validate(first_raw)
        assert first.source_command == "sudo apt update"
        assert first.scenario.command_rules[0].executable == "apt"
        assert first.scenario.command_rules[0].required_arguments == ("update",)
        assert first.scenario.id == "draft.apt.001"
        archive_raw: object = yaml.safe_load(files[2].read_text(encoding="utf-8"))
        archive = ScenarioDraft.model_validate(archive_raw)
        assert archive.scenario.command_rules[0].required_flags == ("-c", "-z", "-f")
        assert archive.scenario.command_rules[0].value_flags == ("-f",)
        assert archive.scenario.command_rules[0].required_arguments == (
            "archive.tar.gz",
            "./dir",
        )


def test_generate_scenario_drafts_does_not_overwrite_by_default() -> None:
    with TemporaryDirectory(dir=Path.cwd(), prefix=".scenario-generator-") as directory:
        root = Path(directory)
        source = root / "pages"
        output = root / "drafts"
        source.mkdir()
        (source / "apt.md").write_text("- refresh indexes:\n`apt update`\n", encoding="utf-8")
        files = generate_scenario_drafts(source, output)
        original = files[0].read_text(encoding="utf-8")

        with pytest.raises(ScenarioGenerationError, match="уже существуют"):
            generate_scenario_drafts(source, output)

        assert files[0].read_text(encoding="utf-8") == original
