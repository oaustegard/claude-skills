"""Data classes for the Claude Code plugin marketplace."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PluginEntry:
    """A single plugin entry for a category-based plugin containing multiple skills."""
    name: str
    description: str
    source: str = "./"
    version: Optional[str] = None
    author: Optional[dict] = None
    category: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "description": self.description,
            "source": self.source,
        }
        if self.version:
            d["version"] = self.version
        if self.author:
            d["author"] = self.author
        if self.category:
            d["category"] = self.category
        return d


@dataclass
class Marketplace:
    """Top-level marketplace manifest."""
    schema: str = "https://anthropic.com/claude-code/marketplace.schema.json"
    name: str = "oaustegard-claude-skills"
    version: str = "1.0.0"
    description: str = "Community skills for Claude Code and Claude.ai"
    owner: dict = field(default_factory=lambda: {
        "name": "Oskar Austegard",
    })
    plugins: list[PluginEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "$schema": self.schema,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "owner": self.owner,
            "plugins": [p.to_dict() for p in self.plugins],
        }
