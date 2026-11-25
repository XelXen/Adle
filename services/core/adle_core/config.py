"""Runtime settings for the core service.

Settings are resolved once at startup and passed explicitly to the pieces that
need them. Nothing in the domain layer reads environment variables directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from adle_core.generation.provider import ProviderCatalogue, ProviderConfigError

DATA_DIR_ENV = "ADLE_DATA_DIR"


class SettingsError(RuntimeError):
    """Raised when the service cannot determine a safe configuration."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Filesystem layout of the app-controlled data directory.

    Everything Adle persists lives under ``data_dir``. No user-supplied path is
    ever used as a storage location (see SECURITY.md, "Files and paths").
    """

    data_dir: Path
    #: Where model requests can go: the providers the learner chooses between, unless a
    #: developer set something else before launch.
    providers: ProviderCatalogue = field(default_factory=ProviderCatalogue)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "adle.db"

    @property
    def sources_dir(self) -> Path:
        """Imported source files, stored under generated names."""
        return self.data_dir / "sources"

    @property
    def assets_dir(self) -> Path:
        """Generated lesson assets (scene sources, audio)."""
        return self.data_dir / "assets"

    @property
    def item_key_path(self) -> Path:
        """A secret of this installation, for naming what the page must not tell apart."""
        return self.data_dir / "items.key"

    @property
    def backups_dir(self) -> Path:
        """Automatic pre-migration database backups."""
        return self.data_dir / "backups"

    @property
    def handover_dir(self) -> Path:
        """Files written for the desktop shell to hand to the learner (a course saved
        as a file, ADR-063): each is here for a moment, under a generated name, and
        none is kept."""
        return self.data_dir / "handover"

    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.sources_dir, self.assets_dir, self.backups_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_environment(cls, data_dir: str | os.PathLike[str] | None = None) -> Settings:
        raw = data_dir if data_dir is not None else os.environ.get(DATA_DIR_ENV)
        if not raw:
            raise SettingsError(
                f"No data directory configured. Pass --data-dir or set {DATA_DIR_ENV}."
            )
        try:
            providers = ProviderCatalogue.from_environment(os.environ)
        except ProviderConfigError as error:
            raise SettingsError(str(error)) from error
        return cls(data_dir=Path(raw).expanduser().resolve(), providers=providers)
