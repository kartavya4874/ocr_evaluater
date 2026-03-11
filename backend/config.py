"""
Configuration manager for the Exam Evaluator backend.
Loads and saves config.json from the application data directory.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    # Load .env file from two levels up (root directory)
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed yet, or we're running somewhere else


DEFAULT_CONFIG = {
    "root_exam_folder": "",
    "export_output_folder": "",
    "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
    "google_cloud_credentials_path": os.environ.get("GOOGLE_CLOUD_CREDENTIALS_PATH", ""),
    "mongodb_uri": os.environ.get("MONGODB_URI", "mongodb://localhost:27017"),
    "redis_url": os.environ.get("REDIS_URL", "redis://localhost:6379"),
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
            
            # Override with ENV variables if available (takes precedence over config.json)
            if os.environ.get("OPENAI_API_KEY"):
                merged["openai_api_key"] = os.environ.get("OPENAI_API_KEY")
            if os.environ.get("GOOGLE_CLOUD_CREDENTIALS_PATH"):
                merged["google_cloud_credentials_path"] = os.environ.get("GOOGLE_CLOUD_CREDENTIALS_PATH")
            if os.environ.get("MONGODB_URI"):
                merged["mongodb_uri"] = os.environ.get("MONGODB_URI")
            if os.environ.get("REDIS_URL"):
                merged["redis_url"] = os.environ.get("REDIS_URL")
                
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
    results["google_cloud_credentials_path"] = (
        bool(config.get("google_cloud_credentials_path"))
        and os.path.isfile(config.get("google_cloud_credentials_path", ""))
    )
    results["mongodb_uri"] = bool(config.get("mongodb_uri"))
    return results
