#!/usr/bin/env python3
"""
Frost - A real package manager that downloads from GitHub releases.
"""

import json
import os
import sys
import shutil
import hashlib
import time
import tarfile
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# ─── Colors ───────────────────────────────────────────────────────────────────
class Colors:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    CYAN    = "\033[36m"

c = Colors

# ─── UI Helpers ───────────────────────────────────────────────────────────────
def banner():
    print(f"""
{c.CYAN}{c.BOLD}  ❄️  frost - package manager
  ────────────────────────────{c.RESET}
""")

def success(msg: str):
    print(f"  {c.GREEN}✓{c.RESET} {msg}")

def error(msg: str):
    print(f"  {c.RED}✗{c.RESET} {msg}")

def warn(msg: str):
    print(f"  {c.YELLOW}!{c.RESET} {msg}")

def info(msg: str):
    print(f"  {c.BLUE}i{c.RESET} {msg}")

def step(msg: str):
    print(f"  {c.CYAN}>{c.RESET} {msg}")

def dim(msg: str) -> str:
    return f"{c.DIM}{msg}{c.RESET}"

def bold(msg: str) -> str:
    return f"{c.BOLD}{msg}{c.RESET}"

def highlight(msg: str) -> str:
    return f"{c.CYAN}{c.BOLD}{msg}{c.RESET}"

def progress_bar(current: int, total: int, prefix: str = "", suffix: str = "", width: int = 30):
    """Display a progress bar."""
    filled = int(width * current / total)
    bar = f"{c.GREEN}{'█' * filled}{c.DIM}{'░' * (width - filled)}{c.RESET}"
    percent = int(100 * current / total)
    print(f"\r  {prefix} [{bar}] {percent}% {suffix}", end="", flush=True)
    if current == total:
        print()

def confirm(prompt: str, default: bool = True) -> bool:
    """Ask for user confirmation."""
    indicator = f"{c.GREEN}Y{c.RESET}/n" if default else f"y/{c.GREEN}N{c.RESET}"
    try:
        response = input(f"  {c.YELLOW}?{c.RESET} {bold(prompt)} [{indicator}]: ").strip().lower()
    except EOFError:
        return default
    if not response:
        return default
    return response in ("y", "yes")

def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def divider(char: str = "─", length: int = 60):
    """Print a divider line."""
    print(f"  {c.DIM}{char * length}{c.RESET}")

def table_row(*cols, widths: List[int] = None) -> str:
    """Format a table row."""
    if widths is None:
        widths = [16, 12, 32]
    parts = []
    for i, (col, w) in enumerate(zip(cols, widths)):
        if i == 0:
            parts.append(f"{c.BOLD}{col:<{w}}{c.RESET}")
        else:
            parts.append(f"{col:<{w}}")
    return "  ".join(parts)

# ─── Configuration ────────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".config" / "frost"
REGISTRY_FILE = Path(__file__).parent / "registry.json"
INSTALLED_DB = CONFIG_DIR / "installed.json"
INSTALL_DIR = Path.home() / ".local"
BIN_DIR = INSTALL_DIR / "bin"
CACHE_DIR = CONFIG_DIR / "cache"
LOG_FILE = CONFIG_DIR / "frost.log"

@dataclass
class Package:
    name: str
    version: str
    description: str
    author: str
    license: str
    homepage: str
    dependencies: List[str]
    binary: str
    platform: str
    url: str
    archive_type: str
    extract_dir: str
    install_files: List[str]
    install_full_dir: bool = False

@dataclass
class InstalledPackage:
    package: Package
    installed_date: str
    installed_files: List[str]

class Frost:
    def __init__(self):
        self._ensure_dirs()
        self.registry = self._load_registry()
        self.installed = self._load_installed()

    def _ensure_dirs(self):
        """Create necessary directories."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        BIN_DIR.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> Dict[str, Package]:
        """Load package registry."""
        if REGISTRY_FILE.exists():
            with open(REGISTRY_FILE, 'r') as f:
                data = json.load(f)
                return {name: Package(**pkg) for name, pkg in data.items()}
        return {}

    def _load_installed(self) -> Dict[str, InstalledPackage]:
        """Load installed packages database."""
        if INSTALLED_DB.exists():
            with open(INSTALLED_DB, 'r') as f:
                data = json.load(f)
                return {name: InstalledPackage(
                    package=Package(**pkg['package']),
                    installed_date=pkg['installed_date'],
                    installed_files=pkg['installed_files']
                ) for name, pkg in data.items()}
        return {}

    def _save_installed(self):
        """Save installed packages database."""
        data = {name: asdict(inst) for name, inst in self.installed.items()}
        INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
        with open(INSTALLED_DB, 'w') as f:
            json.dump(data, f, indent=2)

    def _log(self, message: str, level: str = "INFO"):
        """Log a message."""
        timestamp = datetime.now().isoformat()
        with open(LOG_FILE, 'a') as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")

    def search(self, query: str) -> List[Package]:
        """Search for packages."""
        query_lower = query.lower()
        return [
            pkg for name, pkg in self.registry.items()
            if query_lower in name.lower() or query_lower in pkg.description.lower()
        ]

    def info(self, package_name: str) -> Optional[Package]:
        """Get package info."""
        return self.registry.get(package_name)

    def list_installed(self) -> List[InstalledPackage]:
        """List installed packages."""
        return list(self.installed.values())

    def _download(self, url: str, dest: Path) -> bool:
        """Download a file with progress."""
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'frost/1.0'})
            response = urllib.request.urlopen(req)
            total_size = int(response.headers.get('content-length', 0))
            
            downloaded = 0
            block_size = 8192
            
            with open(dest, 'wb') as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress_bar(downloaded, total_size, prefix="  Downloading")
                    else:
                        # Indeterminate progress
                        dots = (downloaded // 1024) % 40
                        print(f"\r  Downloading {'.' * dots}{' ' * (40 - dots)}", end="", flush=True)
            
            print()
            return True
            
        except urllib.error.URLError as e:
            print()
            error(f"Download failed: {e}")
            return False
        except Exception as e:
            print()
            error(f"Download failed: {e}")
            return False

    def _extract(self, archive_path: Path, extract_dir: Path, archive_type: str, inner_dir: str) -> bool:
        """Extract an archive."""
        try:
            step(f"Extracting {archive_path.name}...")
            
            if archive_type == "tar.gz":
                with tarfile.open(archive_path, 'r:gz') as tar:
                    tar.extractall(extract_dir)
            elif archive_type == "tar.xz":
                with tarfile.open(archive_path, 'r:xz') as tar:
                    tar.extractall(extract_dir)
            elif archive_type == "zip":
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            else:
                error(f"Unsupported archive type: {archive_type}")
                return False
            
            return True
            
        except Exception as e:
            error(f"Extraction failed: {e}")
            return False

    def freeze(self, package_name: str, force: bool = False) -> bool:
        """Install a package (freeze it)."""
        if package_name in self.installed and not force:
            warn(f"{highlight(package_name)} is already frozen")
            return False

        package = self.registry.get(package_name)
        if not package:
            error(f"Package {highlight(package_name)} not found")
            return False

        # Check dependencies
        for dep in package.dependencies:
            if dep not in self.installed:
                warn(f"Missing dependency: {dep}")
                info(f"Run: frost freeze {dep}")

        # Download
        archive_path = CACHE_DIR / f"{package_name}.{package.archive_type}"
        step(f"Downloading {package.name} v{package.version}...")
        
        if not self._download(package.url, archive_path):
            return False

        # Extract
        extract_dir = CACHE_DIR / "extract"
        extract_dir.mkdir(exist_ok=True)
        
        if not self._extract(archive_path, extract_dir, package.archive_type, package.extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
            return False

        # Find and copy files
        step("Installing files...")
        installed_files = []
        
        # Check if we need to install the full directory
        if getattr(package, 'install_full_dir', False):
            # Copy the entire extracted directory
            src_dir = extract_dir / package.extract_dir if package.extract_dir else extract_dir
            if not src_dir.exists():
                src_dir = extract_dir
            
            dest_dir = INSTALL_DIR / "lib" / package.name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
            installed_files.append(str(dest_dir))
            info(f"Installed {package.name}/ -> {dest_dir}")
            
            # Create symlink for binary in bin
            binary_src = dest_dir / package.binary
            if binary_src.exists():
                symlink_path = BIN_DIR / package.binary
                if symlink_path.exists() or symlink_path.is_symlink():
                    symlink_path.unlink()
                symlink_path.symlink_to(binary_src)
                os.chmod(binary_src, 0o755)
                installed_files.append(str(symlink_path))
                info(f"Linked {package.binary} -> {symlink_path}")
        else:
            # Copy individual files
            for install_file in package.install_files:
                src = extract_dir / package.extract_dir / install_file
                if not src.exists():
                    src = extract_dir / install_file
                
                if src.exists():
                    dest = BIN_DIR / install_file
                    shutil.copy2(src, dest)
                    os.chmod(dest, 0o755)
                    installed_files.append(str(dest))
                    info(f"Installed {install_file} -> {dest}")
                else:
                    warn(f"Could not find {install_file} in archive")

        # Cleanup
        shutil.rmtree(extract_dir, ignore_errors=True)
        archive_path.unlink(missing_ok=True)

        # Save to database
        self.installed[package_name] = InstalledPackage(
            package=package,
            installed_date=datetime.now().isoformat(),
            installed_files=installed_files
        )
        self._save_installed()

        self._log(f"Froze {package_name} v{package.version}")
        success(f"{highlight(package_name)} v{package.version} frozen!")
        info(f"Binary available at: {BIN_DIR / package.binary}")
        
        # Check if in PATH
        if str(BIN_DIR) not in os.environ.get('PATH', ''):
            warn(f"{BIN_DIR} is not in your PATH")
            info(f"Add to ~/.profile: export PATH=\"$HOME/.local/bin:$PATH\"")

        return True

    def melt(self, package_name: str) -> bool:
        """Remove a package (melt it)."""
        if package_name not in self.installed:
            warn(f"{highlight(package_name)} is not frozen")
            return False

        inst = self.installed[package_name]
        
        # Remove files
        for file_path in inst.installed_files:
            path = Path(file_path)
            if path.is_symlink():
                path.unlink()
                info(f"Removed {path.name}")
            elif path.is_dir():
                shutil.rmtree(path)
                info(f"Removed {path.name}/")
            elif path.exists():
                path.unlink()
                info(f"Removed {path.name}")

        # Remove from database
        del self.installed[package_name]
        self._save_installed()

        self._log(f"Melted {package_name}")
        success(f"{highlight(package_name)} melted!")
        return True

def print_usage():
    print(f"""
{c.CYAN}{c.BOLD}  ❄️  frost - package manager
  ────────────────────────────{c.RESET}

{c.BOLD}  USAGE:{c.RESET}
    frost <command> [package]

{c.BOLD}  COMMANDS:{c.RESET}
    {c.CYAN}freeze{c.RESET}  <package>     Install a package
    {c.CYAN}melt{c.RESET}    <package>     Remove a package
    {c.CYAN}list{c.RESET}                  List frozen packages
    {c.CYAN}search{c.RESET}  <query>       Search packages
    {c.CYAN}info{c.RESET}    <package>     Show package details
    {c.CYAN}update{c.RESET}                Update all packages
    {c.CYAN}help{c.RESET}                  Show this help

{c.BOLD}  EXAMPLES:{c.RESET}
    {dim("frost search ripgrep")}
    {dim("frost freeze ripgrep")}
    {dim("frost list")}
    {dim("frost info bat")}

{c.DIM}  Config: ~/.config/frost/{c.RESET}
""")

def main():
    if len(sys.argv) < 2:
        banner()
        print_usage()
        sys.exit(0)

    frost = Frost()
    command = sys.argv[1]

    if command in ("help", "--help", "-h"):
        banner()
        print_usage()

    elif command == "search":
        if len(sys.argv) < 3:
            error("Provide a search query")
            sys.exit(1)
        query = sys.argv[2]
        results = frost.search(query)
        if results:
            print(f"\n  {bold(f'Found {len(results)} packages')}\n")
            divider()
            print(f"  {table_row('NAME', 'VERSION', 'DESCRIPTION')}")
            divider()
            for pkg in sorted(results, key=lambda p: p.name):
                print(f"  {table_row(pkg.name, pkg.version, pkg.description[:32])}")
            divider()
            print()
        else:
            warn("No packages found")

    elif command == "info":
        if len(sys.argv) < 3:
            error("Provide a package name")
            sys.exit(1)
        package_name = sys.argv[2]
        package = frost.info(package_name)
        if package:
            is_installed = package_name in frost.installed
            status = f"{c.GREEN}frozen{c.RESET}" if is_installed else f"{c.DIM}not frozen{c.RESET}"
            print(f"""
  {c.CYAN}{bold(package.name)} {dim(f'v{package.version}')}  {status}{c.RESET}

  {bold('Description:')}  {package.description}
  {bold('Author:')}       {package.author}
  {bold('License:')}      {package.license}
  {bold('Homepage:')}     {package.homepage}
  {bold('Binary:')}       {package.binary}
  {bold('Platform:')}     {package.platform}
  {bold('Archive:')}      {package.archive_type}

  {bold('Download URL:')}
    {dim(package.url)}
""")
        else:
            error(f"Package '{package_name}' not found")

    elif command == "freeze":
        if len(sys.argv) < 3:
            error("Provide a package name")
            sys.exit(1)
        package_name = sys.argv[2]
        force = "--force" in sys.argv

        package = frost.info(package_name)
        if not package:
            error(f"Package '{package_name}' not found")
            sys.exit(1)

        print(f"\n  {bold('Ready to freeze:')} {highlight(package.name)} v{package.version}")
        print(f"  {dim(package.description)}")
        print()
        
        if not confirm("Proceed?"):
            info("Cancelled")
            sys.exit(0)

        print()
        frost.freeze(package_name, force)

    elif command == "melt":
        if len(sys.argv) < 3:
            error("Provide a package name")
            sys.exit(1)
        package_name = sys.argv[2]

        if package_name not in frost.installed:
            error(f"'{package_name}' is not frozen")
            sys.exit(1)

        inst = frost.installed[package_name]
        print(f"\n  {bold('Ready to melt:')} {c.RED}{package_name} v{inst.package.version}{c.RESET}")
        print()
        
        if not confirm("Proceed?", default=False):
            info("Cancelled")
            sys.exit(0)

        print()
        frost.melt(package_name)

    elif command == "list":
        installed = frost.list_installed()
        if installed:
            print(f"\n  {bold('Frozen packages')} {dim(f'({len(installed)} total)')}\n")
            divider()
            print(f"  {table_row('NAME', 'VERSION', 'BINARY')}")
            divider()
            for inst in sorted(installed, key=lambda i: i.package.name):
                print(f"  {table_row(inst.package.name, inst.package.version, inst.package.binary)}")
            divider()
            print()
        else:
            print(f"\n  {dim('No packages frozen yet')}")
            info("Use 'frost freeze <package>' to install")
            print()

    elif command == "update":
        banner()
        installed = frost.list_installed()
        if not installed:
            info("No packages to update")
            return
        
        step("Checking for updates...")
        print()
        for inst in installed:
            print(f"  {inst.package.name} v{inst.package.version}")
        print()
        info("To update, re-freeze: frost freeze <package> --force")

    else:
        error(f"Unknown command '{command}'")
        info("Run 'frost help' for usage")
        sys.exit(1)

if __name__ == "__main__":
    main()
