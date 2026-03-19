"""Resolve plist domains to layer files and read them."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

HOME = Path.home()

# Domain aliases
DOMAIN_ALIASES = {
    "NSGlobalDomain": ".GlobalPreferences",
    "-g": ".GlobalPreferences",
    "-globalDomain": ".GlobalPreferences",
}

# Layer definitions in precedence order (highest first)
LAYER_ORDER = ["managed", "user", "system", "byhost", "sandbox"]


def hw_uuid() -> str:
    """Get the hardware UUID for ByHost lookups."""
    result = subprocess.run(
        ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if "IOPlatformUUID" in line:
            return line.split('"')[-2]
    raise RuntimeError("Could not determine hardware UUID")


def resolve_domain(domain: str) -> str:
    """Resolve domain aliases (e.g., NSGlobalDomain -> .GlobalPreferences)."""
    return DOMAIN_ALIASES.get(domain, domain)


def domain_paths(domain: str) -> dict[str, Path]:
    """Map layer names to plist file paths for a domain."""
    domain = resolve_domain(domain)
    uid = hw_uuid()
    return {
        "managed": HOME / f"Library/Managed Preferences/{domain}.plist",
        "user": HOME / f"Library/Preferences/{domain}.plist",
        "system": Path(f"/Library/Preferences/{domain}.plist"),
        "byhost": HOME / f"Library/Preferences/ByHost/{domain}.{uid}.plist",
        "sandbox": HOME / f"Library/Containers/{domain}/Data/Library/Preferences/{domain}.plist",
    }


def is_file_path(arg: str) -> bool:
    """Check if the argument looks like a file path rather than a domain name."""
    return "/" in arg or arg.endswith(".plist")


def domain_from_path(path: str) -> str:
    """Extract domain name from a plist file path."""
    return Path(path).stem


def read_plist(path: Path) -> dict | None:
    """Read a plist file, return None if not found or unreadable."""
    try:
        with open(path, "rb") as f:
            return plistlib.load(f)
    except (FileNotFoundError, PermissionError, plistlib.InvalidFileException):
        return None


def existing_layers(domain: str) -> dict[str, Path]:
    """Return only the layers that exist on disk for a domain."""
    paths = domain_paths(domain)
    return {name: path for name, path in paths.items() if path.exists()}


def all_domains() -> list[str]:
    """List all known domains from ~/Library/Preferences/."""
    prefs_dir = HOME / "Library/Preferences"
    domains = []
    for p in sorted(prefs_dir.glob("*.plist")):
        domains.append(p.stem)
    return domains
