"""
Configuration manager for the Exam Evaluator backend.
Loads and saves config.json from the application data directory.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG = {
    "root_exam_folder": "",
    "export_output_folder": "",
    "openai_api_key": "",
    "mongodb_uri": "mongodb://localhost:27017",
    "redis_url": "redis://localhost:6379",
    "distributed_mode": False,
    "head_node_port": 8765,
    "re_evaluate": False,
    "max_concurrent_api_calls": 5,
    "grading_scale": {
        "O": 90,
        "A+": 80,
        "A": 70,
        "B+": 60,
        "B": 50,
        "C": 40,
        "F": 0,
    },
    "selected_courses": "ALL",
}


def _get_config_path() -> Path:
    """Get the config file path. Uses EXAM_EVAL_CONFIG_DIR env var if set,
    otherwise falls back to the directory where the backend is located."""
    config_dir = os.environ.get("EXAM_EVAL_CONFIG_DIR")
    if config_dir:
        return Path(config_dir) / "config.json"
    # In production, Electron sets this env var to app.getPath('userData')
    # In dev, store alongside the backend
    backend_dir = Path(__file__).resolve().parent.parent
    return backend_dir / "config.json"


def load_config() -> dict:
    """Load configuration from config.json. Returns defaults if file doesn't exist."""
    config_path = _get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge with defaults to ensure all keys exist
            merged = {**DEFAULT_CONFIG, **saved}
            # Ensure grading_scale has all keys
            if "grading_scale" in saved:
                merged["grading_scale"] = {**DEFAULT_CONFIG["grading_scale"], **saved["grading_scale"]}
            return merged
        except (json.JSONDecodeError, IOError):
            return dict(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> dict:
    """Save configuration to config.json. Returns the saved config."""
    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config


def validate_config(config: dict) -> dict:
    """Validate that required fields are present and non-empty.
    Returns a dict of {field: bool} indicating validity."""
    results = {}
    results["root_exam_folder"] = bool(config.get("root_exam_folder")) and os.path.isdir(config.get("root_exam_folder", ""))
    results["openai_api_key"] = bool(config.get("openai_api_key"))
    results["mongodb_uri"] = bool(config.get("mongodb_uri"))
    return results
