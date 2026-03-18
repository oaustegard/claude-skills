"""Data classes for the Claude Code plugin marketplace."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PluginEntry:
    """A single plugin entry wrapping one skill."""
    name: str
    description: str
    source: str = "./"
    strict: bool = False
    skills: list[str] = field(default_factory=list)
    version: Optional[str] = None
    author: Optional[dict] = None
    repository: Optional[str] = None
    license: Optional[str] = None
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "strict": self.strict,
            "skills": self.skills,
        }
        if self.version:
            d["version"] = self.version
        if self.author:
            d["author"] = self.author
        if self.repository:
            d["repository"] = self.repository
        if self.license:
            d["license"] = self.license
        if self.keywords:
            d["keywords"] = self.keywords
        return d


@dataclass
class Marketplace:
    """Top-level marketplace manifest."""
    name: str = "oaustegard-claude-skills"
    owner: dict = field(default_factory=lambda: {
        "name": "Oskar Austegard",
    })
    metadata: dict = field(default_factory=lambda: {
        "description": "Community skills for Claude Code and Claude.ai",
        "version": "1.0.0",
    })
    plugins: list[PluginEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "owner": self.owner,
            "metadata": self.metadata,
            "plugins": [p.to_dict() for p in self.plugins],
        }
