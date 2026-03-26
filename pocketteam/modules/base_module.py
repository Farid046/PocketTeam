"""
Base Module — interface for PocketTeam extension modules.

Modules extend PocketTeam with optional capabilities like:
- AutoResearch (experiment loops, metric optimization)
- Custom integrations (Slack, Linear, etc.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ModuleConfig:
    """Configuration for a module."""
    name: str
    enabled: bool = True
    settings: dict[str, Any] = None

    def __post_init__(self):
        if self.settings is None:
            self.settings = {}


class BaseModule(ABC):
    """
    Base class for PocketTeam modules.

    Modules are optional extensions that add capabilities.
    They register themselves during `pocketteam init` and
    can be enabled/disabled per project.
    """

    def __init__(self, project_root: Path, config: ModuleConfig | None = None) -> None:
        self.project_root = project_root
        self.config = config or ModuleConfig(name=self.module_name)

    @property
    @abstractmethod
    def module_name(self) -> str:
        """Unique module identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...

    @abstractmethod
    async def setup(self) -> bool:
        """
        Interactive setup wizard.
        Called during `pocketteam init` when user opts in.
        Returns True if setup was successful.
        """
        ...

    @abstractmethod
    async def run(self, **kwargs: Any) -> dict:
        """
        Execute the module's main functionality.
        Returns a result dict.
        """
        ...

    def is_enabled(self) -> bool:
        return self.config.enabled
