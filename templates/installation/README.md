# Claude Skills Installation Templates

Automated installation templates for adding Claude Skills to your projects.

## Quick Start

### For Claude Code (Command Line)

Simply run the installation script from your project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/oaustegard/claude-skills/main/templates/installation/install-skills.sh | bash
```

Or download and customize:

```bash
# Download the script
curl -O https://raw.githubusercontent.com/oaustegard/claude-skills/main/templates/installation/install-skills.sh

# Edit SKILLS array to select which skills to install
nano install-skills.sh

# Run installation
chmod +x install-skills.sh
./install-skills.sh
```

### For GitHub Actions (CI/CD)

Copy `install-skills.yml` to `.github/workflows/` in your repository:

```bash
mkdir -p .github/workflows
curl -o .github/workflows/install-skills.yml \
  https://raw.githubusercontent.com/oaustegard/claude-skills/main/templates/installation/install-skills.yml
```

Then trigger via GitHub Actions UI: **Actions** → **Install Claude Skills** → **Run workflow**

## Features

- ✅ **Single-command installation** - One command installs all configured skills
- ✅ **Always up-to-date** - Pulls latest versions from main branch
- ✅ **Automatic cleanup** - Removes workflow metadata (VERSION, README files)
- ✅ **Customizable** - Edit SKILLS array to choose which skills to install
- ✅ **CI/CD ready** - GitHub Actions workflow for automated updates
- ✅ **Symlink handling** - Removes repository-specific symlinks

## How It Works

### Installation Script (`install-skills.sh`)

1. **Clones** the claude-skills repository to a temporary directory
2. **Copies** selected skills to `.claude/skills/` in your project
3. **Removes** workflow metadata files (VERSION, README.md)
4. **Deletes** any symlinks from the source repository
5. **Cleans up** temporary files

### GitHub Actions Workflow (`install-skills.yml`)

1. **Checks out** your repository
2. **Executes** the installation script
3. **Commits** changes with automated git config
4. **Pushes** updates to your branch

## Customization

### Selecting Skills

Edit the `SKILLS` array in `install-skills.sh`:

```bash
SKILLS=(
  "asking-questions"
  "crafting-instructions"
  "creating-mcp-servers"
  # Add or remove skills as needed
)
```

Browse available skills: https://github.com/oaustegard/claude-skills

### Target Directory

Change the installation location by editing:

```bash
SKILLS_TARGET=".claude/skills"  # Default location
```

### Repository Source

To install from a fork or different branch:

```bash
REPO_URL="https://github.com/your-username/claude-skills.git"
```

## Use Cases

### Development Workflow

Claude Code can invoke the installation script during sessions:

```bash
# Claude Code can execute:
bash templates/installation/install-skills.sh
```

### CI/CD Pipeline

Automatically update skills when dependencies change:

```yaml
# In your .github/workflows/install-skills.yml
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly updates
  workflow_dispatch:       # Manual trigger
```

### Project Onboarding

Include in setup scripts for new team members:

```bash
# setup.sh
npm install
./templates/installation/install-skills.sh
echo "✓ Project ready!"
```

## Troubleshooting

### Permission Denied

Make the script executable:

```bash
chmod +x install-skills.sh
```

### Skills Not Found

Verify skill names match the repository:

```bash
# List available skills
curl -s https://api.github.com/repos/oaustegard/claude-skills/contents | \
  grep '"name"' | grep -v '\.' | cut -d'"' -f4
```

### Git Errors in GitHub Actions

Ensure your workflow has write permissions:

1. Go to **Settings** → **Actions** → **General**
2. Under "Workflow permissions", select **Read and write permissions**

## What Gets Installed

Each skill directory contains:

- `SKILL.md` - Core instructions and metadata
- `scripts/` - Executable utilities (optional)
- `references/` - Detailed documentation (optional)
- `assets/` - Templates and resources (optional)

**Excluded from installation:**
- `VERSION` - Workflow metadata file
- `README.md` - Auto-generated descriptions (not needed in installed skills)
- Symlinks - Repository-specific links

## Integration with Claude

Once installed, skills are automatically available in Claude Code sessions. Claude discovers them via:

1. **Metadata** (name + description) from SKILL.md frontmatter
2. **Trigger patterns** in the description field
3. **Progressive loading** of content as needed

Example skill frontmatter:

```yaml
---
name: creating-mcp-servers
description: Creates production-ready MCP servers using FastMCP v2. Use when building MCP servers...
---
```

## Related Resources

- [Claude Skills Repository](https://github.com/oaustegard/claude-skills)
- [Skill Development Guide](../../AGENTS.md)
- [Claude Code Documentation](https://github.com/anthropics/claude-code)

## License

MIT License - See [LICENSE](../../LICENSE) file in the main repository.
