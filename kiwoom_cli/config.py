"""Configuration management for Kiwoom CLI.

Priority: environment variables > secure store (encrypted keychain) > config.toml

Sensitive credentials (appkey, secretkey, token) are encrypted with a
password-derived key and stored in the OS keychain via SecureStore.
Even direct keychain access (keyring.get_password) returns encrypted data.

Non-sensitive settings (domain, account) remain in config.toml.

Environment variables:
  KIWOOM_APPKEY       앱키
  KIWOOM_SECRETKEY    시크릿키
  KIWOOM_DOMAIN       도메인 (prod / mock)
  KIWOOM_ACCOUNT      계좌번호

Config file: ~/.kiwoom/config.toml
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import keyring
import tomli_w

from .secure_store import SecureStore

CONFIG_DIR = Path.home() / ".kiwoom"
CONFIG_FILE = CONFIG_DIR / "config.toml"
CACHE_DIR = CONFIG_DIR / "cache"

KEYRING_SERVICE = "kiwoom-cli"

DOMAINS = {
    "prod": "https://api.kiwoom.com",
    "mock": "https://mockapi.kiwoom.com",
}

DEFAULT_CONFIG = {
    "general": {"domain": "mock", "account": ""},
}

# Shared SecureStore instance
store = SecureStore(KEYRING_SERVICE)


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


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
    env = os.environ.get("KIWOOM_DOMAIN")
    if env:
        return DOMAINS.get(env, DOMAINS["mock"])
    cfg = load_config()
    key = cfg.get("general", {}).get("domain", "mock")
    return DOMAINS.get(key, DOMAINS["mock"])


def get_appkey() -> str:
    return os.environ.get("KIWOOM_APPKEY") or store.get("appkey") or ""


def get_secretkey() -> str:
    return os.environ.get("KIWOOM_SECRETKEY") or store.get("secretkey") or ""


def set_appkey(value: str) -> None:
    store.set("appkey", value)


def set_secretkey(value: str) -> None:
    store.set("secretkey", value)


def get_account() -> str:
    return os.environ.get("KIWOOM_ACCOUNT") or load_config().get("general", {}).get("account", "")


def migrate_from_plaintext() -> bool:
    """Migrate plaintext credentials to encrypted secure store."""
    migrated = False
    # Migrate from config.toml
    cfg = load_config()
    auth_section = cfg.get("auth", {})
    ak = auth_section.get("appkey", "")
    sk = auth_section.get("secretkey", "")
    if ak or sk:
        if ak:
            store.set("appkey", ak)
        if sk:
            store.set("secretkey", sk)
        cfg.pop("auth", None)
        save_config(cfg)
        migrated = True
    # Migrate from plain keyring (v0.4.0 format)
    plain_ak = keyring.get_password(KEYRING_SERVICE, "appkey")
    if plain_ak and not plain_ak.startswith("ey"):  # not already encrypted (base64 JSON)
        store.set("appkey", plain_ak)
        migrated = True
    plain_sk = keyring.get_password(KEYRING_SERVICE, "secretkey")
    if plain_sk and not plain_sk.startswith("ey"):
        store.set("secretkey", plain_sk)
        migrated = True
    # Migrate token file to plain keyring
    token_file = CONFIG_DIR / "token"
    if token_file.exists():
        token = token_file.read_text().strip()
        if token:
            keyring.set_password(KEYRING_SERVICE, "token", token)
        token_file.unlink()
        migrated = True
    return migrated
