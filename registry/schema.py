"""Data classes for the skill registry."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SkillEntry:
    """A single skill's metadata."""
    name: str
    description: str
    version: Optional[str] = None
    deprecated: bool = False
    superseded_by: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    credentials: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    directory: str = ""
    last_updated: Optional[str] = None
    download_url: Optional[str] = None
    files: list[str] = field(default_factory=list)


@dataclass
class Registry:
    """Top-level registry containing all skills."""
    schema_version: str = "1.0.0"
    generated_at: str = ""
    repository: str = "oaustegard/claude-skills"
    skill_count: int = 0
    skills: dict[str, SkillEntry] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "repository": self.repository,
            "skill_count": self.skill_count,
            "skills": {k: asdict(v) for k, v in self.skills.items()},
        }
        return d
