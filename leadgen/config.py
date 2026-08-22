"""Minimal .env reader (stdlib only) -- the project only ever needs one secret
(SHEET_WEBAPP_URL), so this skips adding python-dotenv as a dependency for it.
Real OS environment variables always win over .env, matching normal .env-loader convention.
"""
import os
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env(env_path: Path = PROJECT_ROOT / ".env") -> Dict[str, str]:
    values: Dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    for key in list(values):
        values[key] = os.environ.get(key, values[key])
    return values


def get_webapp_url() -> str:
    return load_env().get("SHEET_WEBAPP_URL", "")
