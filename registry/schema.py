"""Data classes for the Claude Code plugin marketplace."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class PluginEntry:
    """A single plugin entry for a category-based plugin containing multiple skills."""
    name: str
    description: str
    source: str = "./"
    version: Optional[str] = None
    author: Optional[dict] = None
    repository: Optional[str] = None
    homepage: Optional[str] = None
    license: Optional[str] = None
    category: Optional[str] = None
    keywords: list[str] = field(default_factory=list)

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
        if self.repository:
            d["repository"] = self.repository
        if self.homepage:
            d["homepage"] = self.homepage
        if self.license:
            d["license"] = self.license
        if self.category:
            d["category"] = self.category
        if self.keywords:
            d["keywords"] = self.keywords
        return d


@dataclass
class Marketplace:
    """Top-level marketplace manifest."""
    schema: str = "https://anthropic.com/claude-code/marketplace.schema.json"
    name: str = "oaustegard-claude-skills"
    description: str = "Community skills for Claude Code and Claude.ai"
    owner: dict = field(default_factory=lambda: {
        "name": "Oskar Austegard",
    })
    plugins: list[PluginEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        version = datetime.now(timezone.utc).strftime("%Y.%m%d.%H%M")
        return {
            "$schema": self.schema,
            "name": self.name,
            "description": self.description,
            "metadata": {"version": version},
            "owner": self.owner,
            "plugins": [p.to_dict() for p in self.plugins],
        }
