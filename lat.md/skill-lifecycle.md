# Skill Lifecycle

Skills that manage other skills: creation, inspection, installation, and the registry that indexes them.

## Skill Inspection

[[inspecting-skills/scripts/discover.py#discover_skill]] scans a skill directory for layout information: SKILL.md location, scripts directory, README, changelog. [[inspecting-skills/scripts/discover.py#discover_all_skills]] iterates over a skills root to enumerate all skills. [[inspecting-skills/scripts/discover.py#skill_name_to_module]] and [[inspecting-skills/scripts/discover.py#module_to_skill_name]] handle the name mapping between directory names and Python importable names.

[[inspecting-skills/scripts/index.py#index_skill]] performs deeper analysis — it parses Python AST to extract function signatures via [[inspecting-skills/scripts/index.py#get_signature]], docstrings via [[inspecting-skills/scripts/index.py#get_docstring_first_line]], and exported symbols via [[inspecting-skills/scripts/index.py#extract_symbols]]. [[inspecting-skills/scripts/index.py#generate_registry]] produces a JSON index of all importable symbols across skills.

## Cross-Skill Imports

[[inspecting-skills/scripts/skill_imports.py#skill_import]] enables importing between skills.

It handles path resolution and module registration. [[inspecting-skills/scripts/skill_imports.py#SkillImportFinder]] is a custom PEP 302 import hook that resolves `skill_name.module` paths against the skills root. [[inspecting-skills/scripts/skill_imports.py#setup_skill_path]] registers the finder on `sys.meta_path`.

## Registry

[[registry/generate.py#generate]] walks all skill directories, extracts metadata via [[registry/generate.py#build_entry]], and produces a structured JSON registry. Each entry includes name, version, description, dependencies, tags, and available scripts — parsed from SKILL.md frontmatter using [[scripts/frontmatter_utils.py#parse_skill_md]].

## Frontmatter Utilities

[[scripts/frontmatter_utils.py#parse_skill_md]] separates YAML frontmatter from markdown body in SKILL.md files. [[scripts/frontmatter_utils.py#write_skill_md]] reassembles them. [[scripts/frontmatter_utils.py#extract_version]] finds the version from frontmatter or legacy version files. These utilities serve both the registry and the migration script [[scripts/migrate-version-to-frontmatter.py#migrate_skill]].

## On-Demand Discovery

[[finding-skills/scripts/skills.py#cmd_list]], [[finding-skills/scripts/skills.py#cmd_search]], and [[finding-skills/scripts/skills.py#cmd_show]] expose the skill catalog as a CLI so contexts that can't afford to preload every SKILL.md frontmatter can still find and load skills. [[finding-skills/scripts/skills.py#_parse_meta]] extracts name + description from the YAML frontmatter; [[finding-skills/scripts/skills.py#_iter_skills]] walks `/mnt/skills/user/`.

The search ranker scores exact name matches highest (100), substring name matches next (10), and description substring hits last (1 per occurrence). Analogous to Anthropic's ToolSearch for MCP tools, one layer up. Enables CCotw boot to emit names-only instead of full descriptions and still preserve skill awareness.

## Knowledge Skills

Seventeen of ~60 skills contain only a SKILL.md with no scripts — the markdown IS the implementation.

They work because Claude already has the capabilities (ImageMagick, ffmpeg, git, web search); the skill provides decision frameworks and workflow patterns. Examples include processing-images, processing-video, creating-bookmarklets, making-waffles, and updating-knowledge. The tradeoff: no enforcement. A knowledge skill can be ignored; a code skill with validation cannot.
