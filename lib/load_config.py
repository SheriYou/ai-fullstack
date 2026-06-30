# -*- coding: utf-8 -*-
"""Load key=value from projects/<name>/config.env (gitignored)."""
from pathlib import Path


def load_config(project_root: Path | None = None) -> dict[str, str]:
    root = project_root or Path.cwd()
    path = root / "config.env"
    if not path.is_file():
        return {}
    cfg: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip()
    return cfg
