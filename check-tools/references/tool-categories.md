# Development Tool Categories Reference

Complete reference of development tools organized by ecosystem, with installation methods and validation patterns.

## Python Ecosystem

### Interpreters

#### python3 / python
**Purpose**: Python interpreter for running Python code
**Check**: `python3 --version` or `python --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install python3

# macOS
brew install python3

# From source
wget https://www.python.org/ftp/python/3.11.4/Python-3.11.4.tgz
```

### Package Managers

#### pip
**Purpose**: Python package installer
**Check**: `pip --version`
**Installation**:
```bash
# Usually comes with Python
python3 -m ensurepip --upgrade

# Or via get-pip.py
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
```

#### poetry
**Purpose**: Dependency management and packaging made easy
**Check**: `poetry --version`
**Installation**:
```bash
# Official installer
curl -sSL https://install.python-poetry.org | python3 -

# Via pip
pip install poetry
```

#### uv
**Purpose**: Ultra-fast Python package installer
**Check**: `uv --version`
**Installation**:
```bash
# From PyPI
pip install uv

# Using cargo
cargo install uv
```

### Development Tools

#### black
**Purpose**: Uncompromising Python code formatter
**Check**: `black --version`
**Installation**:
```bash
pip install black
```

#### mypy
**Purpose**: Static type checker for Python
**Check**: `mypy --version`
**Installation**:
```bash
pip install mypy
```

#### pytest
**Purpose**: Python testing framework
**Check**: `pytest --version`
**Installation**:
```bash
pip install pytest
```

#### ruff
**Purpose**: Extremely fast Python linter
**Check**: `ruff --version`
**Installation**:
```bash
# Via pip
pip install ruff

# Via cargo
cargo install ruff
```

## Node.js Ecosystem

### Runtime & Package Managers

#### node
**Purpose**: JavaScript runtime built on Chrome's V8
**Check**: `node --version`
**Installation**:
```bash
# Using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install node

# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# macOS
brew install node
```

#### nvm
**Purpose**: Node Version Manager
**Check**: `nvm --version` (after sourcing)
**Installation**:
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
```

#### npm
**Purpose**: Node Package Manager (comes with Node.js)
**Check**: `npm --version`
**Installation**: Installed automatically with Node.js

#### yarn
**Purpose**: Fast, reliable, and secure dependency management
**Check**: `yarn --version`
**Installation**:
```bash
# Via npm
npm install -g yarn

# Via corepack (Node 16.10+)
corepack enable
corepack prepare yarn@stable --activate
```

#### pnpm
**Purpose**: Fast, disk space efficient package manager
**Check**: `pnpm --version`
**Installation**:
```bash
# Via npm
npm install -g pnpm

# Via curl
curl -fsSL https://get.pnpm.io/install.sh | sh -
```

### Development Tools

#### eslint
**Purpose**: JavaScript and TypeScript linter
**Check**: `eslint --version`
**Installation**:
```bash
npm install -g eslint
```

#### prettier
**Purpose**: Opinionated code formatter
**Check**: `prettier --version`
**Installation**:
```bash
npm install -g prettier
```

#### chromedriver
**Purpose**: WebDriver for Chrome browser automation
**Check**: `chromedriver --version`
**Installation**:
```bash
# Via npm
npm install -g chromedriver

# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# macOS
brew install chromedriver
```

## Java Ecosystem

### Runtime & Compiler

#### java
**Purpose**: Java Runtime Environment and compiler
**Check**: `java -version`
**Installation**:
```bash
# Ubuntu/Debian - OpenJDK 17
sudo apt-get install openjdk-17-jdk

# macOS
brew install openjdk@17

# Set JAVA_HOME
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
```

### Build Tools

#### mvn (Maven)
**Purpose**: Build automation and project management
**Check**: `mvn --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install maven

# macOS
brew install maven

# Manual installation
wget https://dlcdn.apache.org/maven/maven-3/3.9.4/binaries/apache-maven-3.9.4-bin.tar.gz
tar xzvf apache-maven-3.9.4-bin.tar.gz
export PATH=$PATH:/path/to/apache-maven-3.9.4/bin
```

#### gradle
**Purpose**: Build automation tool
**Check**: `gradle --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install gradle

# macOS
brew install gradle

# Using SDKMAN!
sdk install gradle
```

## Go Ecosystem

#### go
**Purpose**: Go programming language compiler and tools
**Check**: `go version`
**Installation**:
```bash
# Ubuntu/Debian
wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin

# macOS
brew install go

# Add to PATH
export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin
```

## Rust Ecosystem

### Toolchain

#### rustc
**Purpose**: Rust compiler
**Check**: `rustc --version`
**Installation**:
```bash
# Using rustup (recommended)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
```

#### cargo
**Purpose**: Rust package manager and build tool
**Check**: `cargo --version`
**Installation**: Installed automatically with rustup

## C/C++ Ecosystem

### Compilers

#### gcc
**Purpose**: GNU Compiler Collection
**Check**: `gcc --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# macOS (installs clang, gcc symlinks to it)
xcode-select --install
```

#### clang
**Purpose**: C, C++, and Objective-C compiler
**Check**: `clang --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install clang

# macOS
xcode-select --install
```

### Build Tools

#### cmake
**Purpose**: Cross-platform build system generator
**Check**: `cmake --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install cmake

# macOS
brew install cmake

# From source
wget https://github.com/Kitware/CMake/releases/download/v3.27.0/cmake-3.27.0.tar.gz
```

#### ninja
**Purpose**: Small build system with a focus on speed
**Check**: `ninja --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install ninja-build

# macOS
brew install ninja

# Via pip
pip install ninja
```

#### conan
**Purpose**: C/C++ package manager
**Check**: `conan --version`
**Installation**:
```bash
# Via pip
pip install conan

# Via homebrew
brew install conan
```

## System Utilities

### Version Control

#### git
**Purpose**: Distributed version control system
**Check**: `git --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install git

# macOS
brew install git

# Or use Xcode command line tools
xcode-select --install
```

### Data Transfer & Processing

#### curl
**Purpose**: Command line tool for transferring data
**Check**: `curl --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install curl

# macOS
brew install curl
```

#### jq
**Purpose**: Lightweight command-line JSON processor
**Check**: `jq --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install jq

# macOS
brew install jq

# From source
wget https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64
chmod +x jq-linux64
sudo mv jq-linux64 /usr/local/bin/jq
```

#### yq
**Purpose**: YAML processor (like jq but for YAML)
**Check**: `yq --version`
**Installation**:
```bash
# Via pip
pip install yq

# Via snap
sudo snap install yq

# Via homebrew
brew install yq
```

### Text Processing

#### awk
**Purpose**: Pattern scanning and processing language
**Check**: `awk --version`
**Installation**: Usually pre-installed on Unix-like systems

#### sed
**Purpose**: Stream editor for filtering and transforming text
**Check**: `sed --version`
**Installation**: Usually pre-installed on Unix-like systems

#### grep
**Purpose**: Print lines matching a pattern
**Check**: `grep --version`
**Installation**: Usually pre-installed on Unix-like systems

#### rg (ripgrep)
**Purpose**: Recursively search directories for a regex pattern
**Check**: `rg --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install ripgrep

# macOS
brew install ripgrep

# Via cargo
cargo install ripgrep
```

### Compression & Archiving

#### gzip
**Purpose**: File compression utility
**Check**: `gzip --version`
**Installation**: Usually pre-installed on Unix-like systems

#### tar
**Purpose**: Archive utility
**Check**: `tar --version`
**Installation**: Usually pre-installed on Unix-like systems

### Build Tools

#### make
**Purpose**: Build automation tool
**Check**: `make --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install make

# macOS
xcode-select --install
```

### Terminal Multiplexers

#### tmux
**Purpose**: Terminal multiplexer
**Check**: `tmux -V`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install tmux

# macOS
brew install tmux

# From source
git clone https://github.com/tmux/tmux.git
cd tmux
sh autogen.sh
./configure && make
sudo make install
```

### Text Editors

#### vim
**Purpose**: Highly configurable text editor
**Check**: `vim --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install vim

# macOS
brew install vim
```

#### nano
**Purpose**: Simple command-line text editor
**Check**: `nano --version`
**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install nano

# macOS
brew install nano
```

## Validation Patterns by Tool Type

### Standard Version Flag
Most tools support `--version`:
```bash
tool_name --version
```

### Version to Stderr
Some tools (especially Java ecosystem) output to stderr:
```bash
java -version 2>&1
```

### Version Command Without Dash
```bash
cargo version
go version
```

### Short Version Flag
```bash
tmux -V
```

### Subcommand Version
```bash
git --version
pip --version
```

### First Line Only
When tools output multiple lines:
```bash
tool_name --version | head -1
```

### Regex Version Extraction
For tools with verbose output:
```bash
eslint --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
```

## Tool Dependency Chains

### Python Project (Full Stack)
1. python3 (required)
2. pip (required)
3. poetry or uv (choose one for dependency management)
4. pytest (testing)
5. black (formatting)
6. mypy (type checking)
7. ruff (linting)

### Node.js Project (Full Stack)
1. node (required)
2. npm (required, comes with node)
3. nvm (recommended for version management)
4. yarn or pnpm (optional, alternative to npm)
5. eslint (linting)
6. prettier (formatting)

### Rust Project
1. rustc (required)
2. cargo (required, comes with rustc)

### C/C++ Project
1. gcc or clang (required)
2. cmake (build system)
3. ninja (optional, faster builds)
4. conan (optional, package management)

### Polyglot Project
All of the above, plus:
- git (version control)
- curl (API testing)
- jq (JSON processing)
- rg (code search)
- tmux (workflow)

## Exit Code Conventions

- **0**: All validations passed
- **1**: One or more required tools missing
- **2**: Configuration error
- **126**: Tool found but not executable
- **127**: Tool not found

## Environment Variable Patterns

### Tool Location Discovery
```bash
# Check if tool exists in PATH
command -v tool_name

# Get full path
which tool_name

# Check specific location
if [[ -x "/usr/local/bin/tool_name" ]]; then
    echo "Found at specific location"
fi
```

### Version Manager Environment Loading
```bash
# NVM
if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
    source "$HOME/.nvm/nvm.sh"
fi

# Cargo
if [[ -f "$HOME/.cargo/env" ]]; then
    source "$HOME/.cargo/env"
fi

# SDKMAN
if [[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]]; then
    source "$HOME/.sdkman/bin/sdkman-init.sh"
fi
```

This reference provides comprehensive coverage of all major development tools, their purposes, installation methods, and validation patterns.
