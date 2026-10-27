"""Version reporting for reproducible runs."""

from __future__ import annotations

import platform
import sys
from importlib import metadata


def _version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "not installed"


def show_versions() -> dict[str, str]:
    """Print and return package versions relevant to MasonQ runs."""
    from . import __version__

    versions = {
        "masonq": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "qiskit": _version("qiskit"),
        "qiskit-ibm-runtime": _version("qiskit-ibm-runtime"),
        "graphix": _version("graphix"),
        "quimb": _version("quimb"),
        "numpy": _version("numpy"),
        "networkx": _version("networkx"),
    }
    width = max(len(key) for key in versions)
    for key, value in versions.items():
        print(f"{key:<{width}} : {value}")
    return versions
