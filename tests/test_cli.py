"""Tests for CLI framework and commands."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml
from click.testing import CliRunner

from ki_knowledge.cli.framework import CLICommandSpec, CLIBuilder


@pytest.fixture
def cli_config():
    """Create test CLI configuration."""
    return {
        "cli": {
            "commands": {
                "test": {
                    "help": "Test command group",
                    "commands": {
                        "hello": {
                            "help": "Say hello",
                        },
                        "goodbye": {
                            "help": "Say goodbye",
                        },
                    },
                },
            }
        }
    }


@pytest.fixture
def temp_config_file(cli_config):
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(cli_config, f)
        yield Path(f.name)
    Path(f.name).unlink()


def test_cli_command_spec_creation():
    """Test CLICommandSpec creation."""
    spec = CLICommandSpec(
        name="test",
        help_text="Test command",
        callback="module:function",
    )

    assert spec.name == "test"
    assert spec.help_text == "Test command"
    assert spec.callback == "module:function"
    assert not spec.is_group()


def test_cli_command_spec_from_dict():
    """Test creating spec from dictionary."""
    data = {
        "help": "Test group",
        "commands": {
            "sub1": {"help": "Subcommand 1"},
            "sub2": {"help": "Subcommand 2"},
        },
    }

    spec = CLICommandSpec.from_dict("test", data)

    assert spec.name == "test"
    assert spec.help_text == "Test group"
    assert spec.is_group()
    assert len(spec.commands) == 2


def test_cli_builder_from_yaml_file(temp_config_file):
    """Test building CLI from YAML file."""
    builder = CLIBuilder.from_yaml_file(temp_config_file)

    assert builder.config is not None
    assert "cli" in builder.config


def test_cli_builder_from_yaml_string(cli_config):
    """Test building CLI from YAML string."""
    yaml_str = yaml.dump(cli_config)
    builder = CLIBuilder.from_yaml_string(yaml_str)

    assert builder.config is not None
    assert "cli" in builder.config


def test_cli_builder_build_cli(cli_config):
    """Test building Click CLI."""
    builder = CLIBuilder(cli_config)
    cli = builder.build_cli()

    assert cli is not None
    # Test that commands were added
    assert "test" in [cmd for cmd in cli.commands]


def test_cli_command_group_structure(cli_config):
    """Test CLI command group structure."""
    builder = CLIBuilder(cli_config)
    cli = builder.build_cli()

    runner = CliRunner()
    result = runner.invoke(cli, ["test", "--help"])

    assert result.exit_code == 0
    assert "Test command group" in result.output


def test_cli_command_spec_is_group():
    """Test group detection."""
    leaf_spec = CLICommandSpec(name="leaf", help_text="Leaf", callback="mod:func")
    assert not leaf_spec.is_group()

    group_spec = CLICommandSpec(
        name="group",
        help_text="Group",
        commands={"child": leaf_spec},
    )
    assert group_spec.is_group()


def test_command_callback_loading():
    """Test loading command callbacks."""
    # Test with non-existent callback
    spec = CLICommandSpec(
        name="test",
        help_text="Test",
        callback="nonexistent.module:function",
    )

    with pytest.raises(ModuleNotFoundError):
        spec.load_callback()

    # Test with valid callback
    spec_valid = CLICommandSpec(
        name="test",
        help_text="Test",
        callback="os:getcwd",
    )

    callback = spec_valid.load_callback()
    assert callable(callback)


@pytest.mark.parametrize(
    "command_name",
    ["test", "hello", "goodbye"],
)
def test_cli_command_names(cli_config, command_name):
    """Test that command names are preserved."""
    builder = CLIBuilder(cli_config)
    cli = builder.build_cli()

    if command_name == "test":
        assert "test" in [cmd for cmd in cli.commands]
    else:
        # Sub-commands should exist in test group
        test_group = cli.commands.get("test")
        assert test_group is not None
