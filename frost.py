#!/usr/bin/env python3
"""
Frost - A fast, minimal package manager that downloads from GitHub releases.
"""

import json
import os
import sys
import shutil
import time
import tarfile
import zipfile
import gzip
import bz2
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


# -- Colors --
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

# -- Globals --
QUIET = False
AUTO_YES = False

# -- UI Helpers --
def banner():
    if QUIET:
        return
    print(f"""
{c.CYAN}{c.BOLD}  frost - package manager
  -----------------------{c.RESET}
""")

def success(msg: str):
    if not QUIET:
        print(f"  {c.GREEN}+{c.RESET} {msg}")

def error(msg: str):
    print(f"  {c.RED}x{c.RESET} {msg}")

def warn(msg: str):
    if not QUIET:
        print(f"  {c.YELLOW}!{c.RESET} {msg}")

def info(msg: str):
    if not QUIET:
        print(f"  {c.BLUE}i{c.RESET} {msg}")

def step(msg: str):
    if not QUIET:
        print(f"  {c.CYAN}>{c.RESET} {msg}")

def dim(msg: str) -> str:
    return f"{c.DIM}{msg}{c.RESET}"

def bold(msg: str) -> str:
    return f"{c.BOLD}{msg}{c.RESET}"

def highlight(msg: str) -> str:
    return f"{c.CYAN}{c.BOLD}{msg}{c.RESET}"

def progress_bar(current: int, total: int, prefix: str = "", start_time: float = 0, width: int = 30):
    filled = int(width * current / total) if total > 0 else 0
    bar = f"{c.GREEN}{'#' * filled}{c.DIM}{'-' * (width - filled)}{c.RESET}"
    percent = int(100 * current / total) if total > 0 else 0

    speed = ""
    eta = ""
    if start_time > 0 and current > 0:
        elapsed = time.time() - start_time
        if elapsed > 0:
            bps = current / elapsed
            speed = f"  {format_size(int(bps))}/s"
            if total > 0 and bps > 0:
                remaining = (total - current) / bps
                if remaining < 60:
                    eta = f"  {remaining:.0f}s"
                elif remaining < 3600:
                    eta = f"  {remaining/60:.0f}m {remaining%60:.0f}s"
                else:
                    eta = f"  {remaining/3600:.0f}h {(remaining%3600)/60:.0f}m"

    print(f"\r  {prefix} [{bar}] {percent}% {speed}{eta}   ", end="", flush=True)
    if current == total:
        print()

def confirm(prompt: str, default: bool = True) -> bool:
    if AUTO_YES:
        return True
    indicator = f"{c.GREEN}Y{c.RESET}/n" if default else f"y/{c.GREEN}N{c.RESET}"
    try:
        response = input(f"  {c.YELLOW}?{c.RESET} {bold(prompt)} [{indicator}]: ").strip().lower()
    except EOFError:
        return default
    if not response:
        return default
    return response in ("y", "yes")

def format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def divider(char: str = "-", length: int = 60):
    if not QUIET:
        print(f"  {c.DIM}{char * length}{c.RESET}")

def table_row(*cols, widths: List[int] = None) -> str:
    if widths is None:
        widths = [16, 12, 32]
    parts = []
    for i, (col, w) in enumerate(zip(cols, widths)):
        if i == 0:
            parts.append(f"{c.BOLD}{col:<{w}}{c.RESET}")
        else:
            parts.append(f"{col:<{w}}")
    return "  ".join(parts)

# -- Configuration --
CONFIG_DIR = Path.home() / ".config" / "frost"
REGISTRY_FILE = Path(__file__).parent / "registry.json"
INSTALLED_DB = CONFIG_DIR / "installed.json"
INSTALL_DIR = Path.home() / ".local"
BIN_DIR = INSTALL_DIR / "bin"
CACHE_DIR = CONFIG_DIR / "cache"
LOG_FILE = CONFIG_DIR / "frost.log"

VERSION = "0.2.0"

ARCHIVE_EXTENSIONS = {
    "tar.gz": ".tar.gz",
    "tar.xz": ".tar.xz",
    "tar.bz2": ".tar.bz2",
    "bzip2": ".bz2",
    "gzip": ".gz",
    "zip": ".zip",
    "deb": ".deb",
    "bare-binary": "",
    "appimage": ".AppImage",
}

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
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        BIN_DIR.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> Dict[str, Package]:
        if REGISTRY_FILE.exists():
            with open(REGISTRY_FILE, 'r') as f:
                data = json.load(f)
                return {name: Package(**pkg) for name, pkg in data.items()}
        return {}

    def _load_installed(self) -> Dict[str, InstalledPackage]:
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
        data = {name: asdict(inst) for name, inst in self.installed.items()}
        INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
        with open(INSTALLED_DB, 'w') as f:
            json.dump(data, f, indent=2)

    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().isoformat()
        with open(LOG_FILE, 'a') as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")

    def search(self, query: str) -> List[Package]:
        query_lower = query.lower()
        return [
            pkg for name, pkg in self.registry.items()
            if query_lower in name.lower() or query_lower in pkg.description.lower()
        ]

    def info(self, package_name: str) -> Optional[Package]:
        return self.registry.get(package_name)

    def list_installed(self) -> List[InstalledPackage]:
        return list(self.installed.values())

    def _download(self, url: str, dest: Path) -> bool:
        if dest.exists() and dest.stat().st_size > 0:
            step(f"Using cached {dest.name}")
            return True

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'frost/1.0'})
            response = urllib.request.urlopen(req)
            total_size = int(response.headers.get('content-length', 0))

            downloaded = 0
            block_size = 65536
            start_time = time.time()

            with open(dest, 'wb') as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress_bar(downloaded, total_size, prefix="  Downloading", start_time=start_time)
                    else:
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            speed = format_size(int(downloaded / elapsed))
                            print(f"\r  Downloading {format_size(downloaded)} at {speed}/s   ", end="", flush=True)

            print()
            return True

        except urllib.error.URLError as e:
            print()
            error(f"Download failed: {e}")
            if dest.exists():
                dest.unlink()
            return False
        except Exception as e:
            print()
            error(f"Download failed: {e}")
            if dest.exists():
                dest.unlink()
            return False

    def _safe_extract_tar(self, tar: tarfile.TarFile, dest: Path):
        for member in tar.getmembers():
            member_path = (dest / member.name).resolve()
            if not str(member_path).startswith(str(dest.resolve())):
                error(f"Refusing to extract {member.name}: path traversal detected")
                continue
            tar.extract(member, dest)

    def _extract(self, archive_path: Path, extract_dir: Path, archive_type: str, inner_dir: str) -> bool:
        try:
            step(f"Extracting {archive_path.name}...")

            if archive_type == "tar.gz":
                with tarfile.open(archive_path, 'r:gz') as tar:
                    self._safe_extract_tar(tar, extract_dir)
            elif archive_type == "tar.xz":
                with tarfile.open(archive_path, 'r:xz') as tar:
                    self._safe_extract_tar(tar, extract_dir)
            elif archive_type == "tar.bz2":
                with tarfile.open(archive_path, 'r:bz2') as tar:
                    self._safe_extract_tar(tar, extract_dir)
            elif archive_type == "bzip2":
                out_path = extract_dir / archive_path.stem
                with bz2.open(archive_path, 'rb') as f_in:
                    with open(out_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.chmod(out_path, 0o755)
            elif archive_type == "gzip":
                out_path = extract_dir / archive_path.stem
                with gzip.open(archive_path, 'rb') as f_in:
                    with open(out_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.chmod(out_path, 0o755)
            elif archive_type == "zip":
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif archive_type == "deb":
                result = subprocess.run(
                    ['ar', 'x', str(archive_path)],
                    cwd=str(extract_dir),
                    capture_output=True
                )
                if result.returncode != 0:
                    error(f"Failed to extract deb: {result.stderr.decode()}")
                    return False
                data_tar = extract_dir / "data.tar.xz"
                if not data_tar.exists():
                    data_tar = extract_dir / "data.tar.gz"
                if data_tar.exists():
                    with tarfile.open(data_tar, 'r:xz' if data_tar.suffix == '.xz' else 'r:gz') as tar:
                        self._safe_extract_tar(tar, extract_dir)
                    data_tar.unlink(missing_ok=True)
                    for f in ['control.tar.xz', 'control.tar.gz', 'debian-binary']:
                        (extract_dir / f).unlink(missing_ok=True)
            elif archive_type == "bare-binary":
                dest = extract_dir / archive_path.name
                shutil.copy2(archive_path, dest)
                os.chmod(dest, 0o755)
            else:
                error(f"Unsupported archive type: {archive_type}")
                return False

            return True

        except Exception as e:
            error(f"Extraction failed: {e}")
            return False

    def _install_deps(self, package_name: str, visited: set = None) -> bool:
        if visited is None:
            visited = set()
        if package_name in visited:
            return True
        visited.add(package_name)

        package = self.registry.get(package_name)
        if not package:
            return False

        for dep in package.dependencies:
            if dep not in self.installed:
                if dep not in self.registry:
                    warn(f"Dependency '{dep}' not found in registry")
                    continue
                info(f"Installing dependency: {dep}")
                if not self.freeze(dep, force=False, skip_confirm=True):
                    warn(f"Failed to install dependency: {dep}")
                    return False
                self._install_deps(dep, visited)

        return True

    def freeze(self, package_name: str, force: bool = False, skip_confirm: bool = False) -> bool:
        if package_name in self.installed and not force:
            warn(f"{highlight(package_name)} is already frozen")
            return False

        package = self.registry.get(package_name)
        if not package:
            error(f"Package {highlight(package_name)} not found")
            return False

        if not self._install_deps(package_name):
            return False

        # Download
        ext = ARCHIVE_EXTENSIONS.get(package.archive_type, f".{package.archive_type}")
        archive_path = CACHE_DIR / f"{package_name}{ext}"
        step(f"Downloading {package.name} v{package.version}...")

        if not self._download(package.url, archive_path):
            return False

        # Handle bare-binary
        if package.archive_type == "bare-binary":
            step("Installing binary...")
            dest = BIN_DIR / package.binary
            shutil.copy2(archive_path, dest)
            os.chmod(dest, 0o755)
            archive_path.unlink(missing_ok=True)

            self.installed[package_name] = InstalledPackage(
                package=package,
                installed_date=datetime.now().isoformat(),
                installed_files=[str(dest)]
            )
            self._save_installed()
            success(f"{highlight(package_name)} v{package.version} frozen!")
            info(f"Binary available at: {dest}")
            return True

        # Extract
        extract_dir = CACHE_DIR / "extract"
        extract_dir.mkdir(exist_ok=True)

        if not self._extract(archive_path, extract_dir, package.archive_type, package.extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
            return False

        # Install files
        step("Installing files...")
        installed_files = []

        if getattr(package, 'install_full_dir', False):
            src_dir = extract_dir / package.extract_dir if package.extract_dir else extract_dir
            if not src_dir.exists():
                src_dir = extract_dir

            dest_dir = INSTALL_DIR / "lib" / package.name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
            installed_files.append(str(dest_dir))
            info(f"Installed {package.name}/ -> {dest_dir}")

            for bin_name in (package.binary.split(",") if package.binary else []):
                bin_name = bin_name.strip()
                if not bin_name:
                    continue
                binary_src = dest_dir / bin_name
                if binary_src.exists():
                    symlink_path = BIN_DIR / Path(bin_name).name
                    if symlink_path.exists() or symlink_path.is_symlink():
                        symlink_path.unlink()
                    symlink_path.symlink_to(binary_src)
                    os.chmod(binary_src, 0o755)
                    installed_files.append(str(symlink_path))
                    info(f"Linked {Path(bin_name).name} -> {symlink_path}")
        else:
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
        last_bin = [f for f in installed_files if str(BIN_DIR) in f]
        if last_bin:
            info(f"Binary available at: {last_bin[-1]}")

        if str(BIN_DIR) not in os.environ.get('PATH', ''):
            warn(f"{BIN_DIR} is not in your PATH")
            info(f"Add to ~/.profile: export PATH=\"$HOME/.local/bin:$PATH\"")

        return True

    def melt(self, package_name: str) -> bool:
        if package_name not in self.installed:
            warn(f"{highlight(package_name)} is not frozen")
            return False

        inst = self.installed[package_name]

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

        del self.installed[package_name]
        self._save_installed()

        self._log(f"Melted {package_name}")
        success(f"{highlight(package_name)} melted!")
        return True

    def upgrade(self, package_name: str = None) -> bool:
        if package_name:
            if package_name not in self.installed:
                error(f"'{package_name}' is not frozen")
                return False
            step(f"Upgrading {package_name}...")
            old = self.installed[package_name]
            self.melt(package_name)
            if not self.freeze(package_name, force=True, skip_confirm=True):
                error(f"Upgrade failed, attempting to restore {package_name}...")
                self.freeze(package_name, force=True, skip_confirm=True)
                return False
            return True
        else:
            installed = self.list_installed()
            if not installed:
                info("No packages to upgrade")
                return True

            step(f"Upgrading {len(installed)} packages...")
            upgraded = 0
            failed = 0
            for inst in installed:
                name = inst.package.name
                print()
                old = self.installed.get(name)
                self.melt(name)
                if self.freeze(name, force=True, skip_confirm=True):
                    upgraded += 1
                else:
                    error(f"Upgrade failed for {name}, attempting to restore...")
                    if old:
                        self.installed[name] = old
                        self._save_installed()
                        self.freeze(name, force=True, skip_confirm=True)
                    failed += 1

            print()
            info(f"Upgraded: {upgraded}, Failed: {failed}")
            return True

    def outdated(self) -> List[tuple]:
        outdated = []
        for name, inst in self.installed.items():
            pkg = self.registry.get(name)
            if pkg and pkg.version != inst.package.version:
                outdated.append((name, inst.package.version, pkg.version))
        return outdated

def print_usage():
    print(f"""
{c.CYAN}{c.BOLD}  frost - package manager
  -----------------------{c.RESET}

{c.BOLD}  USAGE:{c.RESET}
    frost <command> [package]

{c.BOLD}  COMMANDS:{c.RESET}
    {c.CYAN}freeze{c.RESET}  <package>     Install a package
    {c.CYAN}melt{c.RESET}    <package>     Remove a package
    {c.CYAN}list{c.RESET}                  List frozen packages
    {c.CYAN}search{c.RESET}  <query>       Search packages
    {c.CYAN}info{c.RESET}    <package>     Show package details
    {c.CYAN}upgrade{c.RESET} [package]     Upgrade packages (all or specific)
    {c.CYAN}outdated{c.RESET}              Show packages with updates available
    {c.CYAN}help{c.RESET}                  Show this help

{c.BOLD}  OPTIONS:{c.RESET}
    {c.CYAN}-y{c.RESET}, {c.CYAN}--yes{c.RESET}       Skip confirmation prompts
    {c.CYAN}-q{c.RESET}, {c.CYAN}--quiet{c.RESET}      Minimal output
    {c.CYAN}--force{c.RESET}             Force re-install

{c.BOLD}  EXAMPLES:{c.RESET}
    {dim("frost search ripgrep")}
    {dim("frost freeze ripgrep -y")}
    {dim("frost upgrade ripgrep")}
    {dim("frost upgrade")}
    {dim("frost outdated")}

{c.DIM}  Config: ~/.config/frost/{c.RESET}
""")

def main():
    global QUIET, AUTO_YES

    if '--version' in sys.argv or '-v' in sys.argv:
        print(f"frost {VERSION}")
        sys.exit(0)

    # Parse global flags
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    flags = [a for a in sys.argv[1:] if a.startswith('-')]

    if '-q' in flags or '--quiet' in flags:
        QUIET = True
    if '-y' in flags or '--yes' in flags:
        AUTO_YES = True

    if not args:
        banner()
        print_usage()
        sys.exit(0)

    frost = Frost()
    command = args[0]

    if command in ("help", "--help", "-h"):
        banner()
        print_usage()

    elif command == "search":
        if len(args) < 2:
            error("Provide a search query")
            sys.exit(1)
        query = args[1]
        results = frost.search(query)
        if results:
            print(f"\n  {bold(f'Found {len(results)} packages')}\n")
            divider()
            print(f"  {table_row('NAME', 'VERSION', 'DESCRIPTION')}")
            divider()
            for pkg in sorted(results, key=lambda p: p.name):
                status = f"{c.GREEN}[frozen]{c.RESET}" if pkg.name in frost.installed else ""
                print(f"  {table_row(pkg.name, pkg.version, pkg.description[:32])} {status}")
            divider()
            print()
        else:
            warn("No packages found")

    elif command == "info":
        if len(args) < 2:
            error("Provide a package name")
            sys.exit(1)
        package_name = args[1]
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
  {bold('Dependencies:')} {', '.join(package.dependencies) if package.dependencies else 'none'}

  {bold('Download URL:')}
    {dim(package.url)}
""")
        else:
            error(f"Package '{package_name}' not found")

    elif command == "freeze":
        if len(args) < 2:
            error("Provide a package name")
            sys.exit(1)
        package_name = args[1]
        force = "--force" in flags

        package = frost.info(package_name)
        if not package:
            error(f"Package '{package_name}' not found")
            sys.exit(1)

        if not AUTO_YES:
            print(f"\n  {bold('Ready to freeze:')} {highlight(package.name)} v{package.version}")
            print(f"  {dim(package.description)}")
            print()

            if not confirm("Proceed?"):
                info("Cancelled")
                sys.exit(0)
            print()

        frost.freeze(package_name, force)

    elif command == "melt":
        if len(args) < 2:
            error("Provide a package name")
            sys.exit(1)
        package_name = args[1]

        if package_name not in frost.installed:
            import shutil as _shutil
            if _shutil.which(package_name):
                warn(f"'{package_name}' is installed but not by frost")
                warn(f"Use 'sudo pacman -R {package_name}' to remove it")
            else:
                error(f"'{package_name}' is not frozen")
            sys.exit(1)

        if not AUTO_YES:
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

    elif command == "upgrade":
        if not AUTO_YES and not QUIET:
            banner()
        if len(args) >= 2:
            frost.upgrade(args[1])
        else:
            frost.upgrade()

    elif command == "outdated":
        outdated = frost.outdated()
        if outdated:
            print(f"\n  {bold('Outdated packages')} {dim(f'({len(outdated)} total)')}\n")
            divider()
            print(f"  {table_row('NAME', 'CURRENT', 'LATEST')}")
            divider()
            for name, current, latest in outdated:
                print(f"  {table_row(name, current, latest)}")
            divider()
            print()
            info("Run 'frost upgrade' to update all")
        else:
            info("All packages are up to date")

    else:
        error(f"Unknown command '{command}'")
        info("Run 'frost help' for usage")
        sys.exit(1)

if __name__ == "__main__":
    main()
