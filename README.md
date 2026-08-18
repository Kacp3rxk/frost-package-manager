# ❄️ frost

A simple, human-friendly package manager that downloads real binaries from GitHub releases.

## Install

```sh
git clone https://github.com/yourusername/frost.git
cd frost
chmod +x frost
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
| `frost update` | Check for updates |

## Usage

```sh
frost search rip          # Find packages
frost freeze ripgrep      # Install ripgrep
frost freeze bat          # Install bat
frost list                # See installed
frost melt fd             # Remove fd
```

## Available Packages

- **firefox** - Mozilla Firefox web browser
- **ripgrep** - Fast line-oriented search tool
- **fd** - Fast and user-friendly find alternative
- **bat** - A cat(1) clone with wings
- **exa** - A modern replacement for ls
- **delta** - Syntax-highlighting pager for git
- **zoxide** - A smarter cd command
- **starship** - Blazing-fast shell prompt
- **hyperfine** - Command-line benchmarking tool
- **duf** - Better df
- **dust** - Better du
- **grex** - Regex generator
- **tokei** - Code counter

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