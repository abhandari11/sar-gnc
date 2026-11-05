"""Project-tree locations for data, caches and outputs."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Project root: $SARGNC_ROOT if set, else the repository containing this file."""
    env = os.environ.get("SARGNC_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return project_root() / "data"


def outputs_dir() -> Path:
    return project_root() / "outputs"
