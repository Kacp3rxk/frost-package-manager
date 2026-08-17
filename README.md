# frost

A simple package manager that downloads real binaries from GitHub releases

## Install

```sh
git clone https://github.com/Kacp3rxk/frost-package-manager.git
cd frost
chmod +x frost.py
export PATH="$PWD:$HOME/.local/bin:$PATH"
```

## Commands

| Command | Description |
|---------|-------------|
| `frost freeze <package>` | Install a package |
| `frost melt <package>` | Remove a package |
| `frost list` | List installed packages |
| `frost search <query>` | Search packages |
| `frost info <package>` | Show package details |
| `frost upgrade [package]` | Upgrade packages (all or specific) |
| `frost outdated` | Show packages with updates available |
| `frost help` | Show help |

## Usage

```sh
frost search rip          # Find packages
frost freeze ripgrep -y   # Install without confirmation
frost freeze bat          # Install bat
frost list                # See installed
frost upgrade ripgrep     # Upgrade a package
frost upgrade             # Upgrade all packages
frost outdated            # Check for updates
frost melt fd             # Remove fd
```

## Available Packages (102 total)

### Browsers
- **firefox** - Mozilla Firefox web browser
- **floorp** - Firefox-based browser with vertical tabs
- **discourdev** - Discord for Linux (dev builds)

### Terminals & Shells
- **kitty** - GPU-based terminal emulator
- **starship** - Blazing-fast shell prompt
- **zoxide** - A smarter cd command
- **atuin** - Magical shell history with sync and search
- **fish** - Smart and user-friendly command line shell

### Development Tools
- **neovim** - Hyperextensible Vim-based text editor
- **helix** - A post-modern modal text editor
- **just** - Command runner
- **lazygit** - Simple terminal UI for git commands
- **lazydocker** - Simple terminal UI for docker and docker-compose
- **dive** - Explore each layer in a Docker image
- **docker** - Docker CLI client
- **docker-compose** - Define and run multi-container Docker apps
- **kubectl** - Kubernetes command-line tool
- **kubectx** - Switch between Kubernetes contexts
- **kubens** - Switch between Kubernetes namespaces
- **helm** - The package manager for Kubernetes
- **flux** - GitOps toolkit for Kubernetes
- **consul** - Service mesh and service discovery
- **terraform** - Infrastructure as Code tool
- **vault** - Secrets management
- **packer** - Build automated machine images

### CLI Utilities
- **ripgrep** - Fast line-oriented search tool
- **fd** - Fast and user-friendly find alternative
- **bat** - A cat(1) clone with wings
- **exa** - A modern replacement for ls
- **lsd** - ls with colors, icons, tree-view and more
- **fzf** - A command-line fuzzy finder
- **delta** - Syntax-highlighting pager for git
- **dust** - A more intuitive version of du
- **duf** - Disk Usage/Free Utility - better df
- **btop** - Resource monitor - best looking system monitor
- **bottom** - Cross-platform graphical process/system monitor
- **tokei** - Code counter
- **grex** - Regex generator
- **hyperfine** - Command-line benchmarking tool
- **jq** - Command-line JSON processor
- **yq** - Portable command-line YAML processor
- **glow** - Render markdown on the CLI
- **hexyl** - A command-line hex viewer
- **doggo** - Modern DNS client
- **hey** - HTTP load generator
- **curl** - Command line tool and library
- **wget** - Network retriever
- **tree** - Directory tree viewer
- **fselect** - Find files with SQL-like queries
- **gron** - Make JSON greppable

### System & Monitoring
- **fastfetch** - Fast system information tool
- **btop** - Resource monitor
- **duf** - Better df
- **dust** - Better du
- **hyperfine** - Benchmarking tool

### Applications
- **discord** - All-in-one voice, video and text chat
- **steam** - Valve's Steam gaming platform
- **anki** - Powerful spaced repetition flashcard program
- **figma-linux** - Figma desktop client for Linux
- **obs-studio** - Video recording and live streaming
- **vlc** - Media player
- **mpv** - Minimalist media player

### DevOps & Cloud
- **terraform** - Infrastructure as Code
- **packer** - Machine image builder
- **vault** - Secrets management
- **consul** - Service mesh
- **helm** - Kubernetes package manager
- **kubectl** - Kubernetes CLI
- **kubectx** - Kubernetes context switcher
- **kubens** - Kubernetes namespace switcher
- **flux** - GitOps toolkit

### Web Development
- **biome** - One toolchain for your web project
- **eslint** - Find and fix problems in JavaScript
- **prettier** - Code formatter
- **knip** - Cut the clutter from TypeScript projects
- **cspell** - Spell checker for code

### Data & Config
- **dasel** - Query and modify data structures
- **fx** - Command-line JSON viewer
- **gojq** - Pure Go implementation of jq
- **gron** - Make JSON greppable
- **chezmoi** - Manage dotfiles across machines

### Games
- **crawl** - Roguelike dungeon exploration game

### Other
- **just** - Command runner
- **mkcert** - Local trusted development certificates
- **age** - Simple, modern encryption tool
- **lazyssh** - Interactive SSH session manager

## Flags

| Flag | Description |
|------|-------------|
| `-y`, `--yes` | Skip confirmation prompts |
| `-q`, `--quiet` | Minimal output |
| `--force` | Force re-install |

## How It Works

1. `frost freeze` downloads the package archive from GitHub releases
2. Extracts it to `~/.config/frost/cache/`
3. Installs binaries to `~/.local/bin/`
4. For full applications (like Firefox), installs to `~/.local/lib/`
5. Tracks everything in `~/.config/frost/installed.json`

## Adding Packages

Edit `registry.json` to add new packages:

```json
{
  "package-name": {
    "name": "package-name",
    "version": "1.0.0",
    "description": "What it does",
    "author": "Author Name",
    "license": "MIT",
    "homepage": "https://github.com/author/package",
    "dependencies": [],
    "binary": "binary-name",
    "platform": "linux-x86_64",
    "url": "https://github.com/author/package/releases/download/v1.0.0/package-linux.tar.gz",
    "archive_type": "tar.gz",
    "extract_dir": "package-1.0.0",
    "install_files": ["binary-name"]
  }
}
```

## License

MIT
