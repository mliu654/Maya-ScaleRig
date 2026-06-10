"""Persistent UI settings stored as a small JSON file."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


APP_DIR_NAME = 'MayaScaleRig'
CONFIG_FILE_NAME = 'ui_settings.json'


def config_path() -> Path:
    appdata = os.environ.get('APPDATA')
    if appdata:
        return Path(appdata) / APP_DIR_NAME / CONFIG_FILE_NAME
    return Path.home() / '.config' / 'maya-scalerig' / CONFIG_FILE_NAME


def load_settings() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict[str, Any]) -> None:
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        return
