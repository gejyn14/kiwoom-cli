"""Configuration management for Kiwoom CLI.

Stores settings in ~/.kiwoom/config.toml:
  [auth]
  appkey = "..."
  secretkey = "..."

  [general]
  domain = "prod"   # "prod" or "mock"
  account = ""      # default account number
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

CONFIG_DIR = Path.home() / ".kiwoom"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DOMAINS = {
    "prod": "https://api.kiwoom.com",
    "mock": "https://mockapi.kiwoom.com",
}

DEFAULT_CONFIG = {
    "auth": {"appkey": "", "secretkey": ""},
    "general": {"domain": "mock", "account": ""},
}


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def save_config(cfg: dict) -> None:
    ensure_config_dir()
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(cfg, f)


def get_domain() -> str:
    cfg = load_config()
    key = cfg.get("general", {}).get("domain", "mock")
    return DOMAINS.get(key, DOMAINS["mock"])


def get_appkey() -> str:
    return load_config().get("auth", {}).get("appkey", "")


def get_secretkey() -> str:
    return load_config().get("auth", {}).get("secretkey", "")


def get_account() -> str:
    return load_config().get("general", {}).get("account", "")
