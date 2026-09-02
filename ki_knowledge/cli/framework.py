"""Dynamic CLI framework based on YAML configuration.

This module allows defining CLI command hierarchies in YAML config files
and dynamically generating Click command groups and commands.

Example YAML config:
```yaml
cli:
  commands:
    infosite:
      help: "Knowledge Presentation (Infosite) Management"
      commands:
        init:
          help: "Initialize a new infosite project"
          callback: "ki_knowledge.cli.commands.infosite:init_project"
        generate:
          help: "Generate infosite from documents"
          callback: "ki_knowledge.cli.commands.infosite:generate_infosite"
        list:
          help: "List infosite projects"
          callback: "ki_knowledge.cli.commands.infosite:list_projects"
    knowledge:
      help: "Knowledge Base Management"
      commands:
        import:
          help: "Import knowledge documents"
          callback: "ki_knowledge.cli.commands.knowledge:import_docs"
```
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import click
import yaml


class CLICommandSpec:
    """Specification for a CLI command or group."""

    def __init__(
        self,
        name: str,
        help_text: str = "",
        callback: Optional[str] = None,
        commands: Optional[Dict[str, CLICommandSpec]] = None,
    ):
        """Initialize command spec.

        Args:
            name: Command name
            help_text: Help text for command
            callback: Python import path to callback function
            commands: Sub-commands
        """
        self.name = name
        self.help_text = help_text
        self.callback = callback
        self.commands = commands or {}

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> CLICommandSpec:
        """Create spec from dictionary.

        Args:
            name: Command name
            data: Configuration dictionary

        Returns:
            CLICommandSpec instance
        """
        sub_commands = {}
        if "commands" in data:
            for sub_name, sub_data in data["commands"].items():
                sub_commands[sub_name] = CLICommandSpec.from_dict(sub_name, sub_data)

        return cls(
            name=name,
            help_text=data.get("help", ""),
            callback=data.get("callback"),
            commands=sub_commands,
        )

    def is_group(self) -> bool:
        """Check if this is a command group."""
        return len(self.commands) > 0

    def load_callback(self) -> Optional[Callable]:
        """Load the callback function from import path.

        Returns:
            Callable or None if no callback

        Raises:
            ImportError: If callback cannot be imported
        """
        if not self.callback:
            return None

        module_path, func_name = self.callback.rsplit(":", 1)
        module = importlib.import_module(module_path)
        return getattr(module, func_name)


class CLIBuilder:
    """Builder for dynamic Click CLI from YAML config."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize builder.

        Args:
            config: Configuration dictionary with CLI structure
        """
        self.config = config
        self.cli_config = config.get("cli", {})
        self.commands_config = self.cli_config.get("commands", {})

    @classmethod
    def from_yaml_file(cls, file_path: Path) -> CLIBuilder:
        """Create builder from YAML file.

        Args:
            file_path: Path to YAML config file

        Returns:
            CLIBuilder instance
        """
        with file_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return cls(config)

    @classmethod
    def from_yaml_string(cls, yaml_content: str) -> CLIBuilder:
        """Create builder from YAML string.

        Args:
            yaml_content: YAML content as string

        Returns:
            CLIBuilder instance
        """
        config = yaml.safe_load(yaml_content) or {}
        return cls(config)

    def build_cli(self) -> click.Group:
        """Build Click CLI from configuration.

        Returns:
            Click command group
        """
        @click.group()
        def cli():
            """Dynamic CLI built from configuration."""
            pass

        # Add commands from config
        for cmd_name, cmd_config in self.commands_config.items():
            cmd_spec = CLICommandSpec.from_dict(cmd_name, cmd_config)
            click_cmd = self._build_command(cmd_spec)
            cli.add_command(click_cmd)

        return cli

    def _build_command(self, spec: CLICommandSpec) -> click.Command:
        """Build a Click command from spec.

        Args:
            spec: Command specification

        Returns:
            Click command or group
        """
        if spec.is_group():
            # Build group
            @click.group(name=spec.name, help=spec.help_text)
            def group():
                pass

            # Add sub-commands
            for sub_spec in spec.commands.values():
                sub_cmd = self._build_command(sub_spec)
                group.add_command(sub_cmd)

            return group
        else:
            # Build leaf command
            callback = spec.load_callback()

            if callback is None:
                # Default callback if none specified
                @click.command(name=spec.name, help=spec.help_text)
                def cmd():
                    click.echo(f"Command: {spec.name}")

                return cmd
            else:
                # If callback is already a Click command, use it directly
                if isinstance(callback, (click.Command, click.Group)):
                    # Already a Click command, just set name and return
                    callback.name = spec.name
                    return callback
                else:
                    # Otherwise wrap it
                    @click.command(name=spec.name, help=spec.help_text)
                    @click.pass_context
                    def cmd(ctx):
                        try:
                            callback()
                        except Exception as e:
                            click.echo(f"Error: {e}", err=True)
                            ctx.exit(1)

                    return cmd


def build_cli_from_config(config_path: Optional[Path] = None) -> click.Group:
    """Build CLI from configuration file.

    Args:
        config_path: Path to config file (auto-discovered if None)

    Returns:
        Click command group
    """
    if config_path is None:
        # Try to find config file
        candidates = [
            Path("ki.yaml"),
            Path("kicli.yaml"),
            Path("config.yaml"),
            Path("cli.yaml"),
            Path(".ki.yaml"),
            Path.home() / ".config" / "ki" / "cli.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = candidate
                break

    if config_path is None:
        raise FileNotFoundError("No CLI config file found")

    builder = CLIBuilder.from_yaml_file(config_path)
    return builder.build_cli()
