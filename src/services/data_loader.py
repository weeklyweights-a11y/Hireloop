"""Lazy singleton for taxonomy / skills / locations JSON — safe across Celery forks."""
from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class DataLoader:
    _instance: DataLoader | None = None

    def __init__(self) -> None:
        self.taxonomy: list[dict] = self._load("title_taxonomy.json")
        self.skills: list[dict] = self._load("skills.json")
        self.locations: dict = self._load("locations.json")
        # Flat alias → canonical for quick lookup (search / title helpers)
        self.title_alias_index: dict[str, str] = {}
        for entry in self.taxonomy:
            canonical = entry["canonical"]
            self.title_alias_index[canonical.lower()] = canonical
            for alias in entry.get("aliases", []):
                self.title_alias_index[alias.lower()] = canonical

    @staticmethod
    def _load(name: str):
        return json.loads((_DATA_DIR / name).read_text(encoding="utf-8"))

    @classmethod
    def get(cls) -> DataLoader:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — force reload on next get()."""
        cls._instance = None
