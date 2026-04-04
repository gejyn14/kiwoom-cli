"""Configuration management for Kiwoom CLI.

Priority: environment variables > secure store (encrypted keychain) > config.toml

Sensitive credentials (appkey, secretkey, token) are encrypted with a
password-derived key and stored in the OS keychain via SecureStore.
Even direct keychain access (keyring.get_password) returns encrypted data.

Non-sensitive settings (domain, account) remain in config.toml.

Environment variables (non-sensitive only):
  KIWOOM_DOMAIN       도메인 (prod / mock)
  KIWOOM_ACCOUNT      계좌번호
  KIWOOM_PROFILE      활성 프로필 이름

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
    "general": {"default_profile": "default"},
    "profiles": {"default": {"domain": "mock", "account": ""}},
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


def resolve_profile(profile: str | None = None) -> str:
    """Resolve the active profile name.

    Priority: explicit arg > KIWOOM_PROFILE env > general.default_profile > "default"
    """
    if profile:
        return profile
    env = os.environ.get("KIWOOM_PROFILE")
    if env:
        return env
    cfg = load_config()
    return cfg.get("general", {}).get("default_profile", "default")


def get_domain(profile: str | None = None) -> str:
    env = os.environ.get("KIWOOM_DOMAIN")
    if env:
        return DOMAINS.get(env, DOMAINS["mock"])
    p = resolve_profile(profile)
    cfg = load_config()
    key = cfg.get("profiles", {}).get(p, {}).get("domain", "mock")
    return DOMAINS.get(key, DOMAINS["mock"])


def get_appkey(profile: str | None = None) -> str:
    p = resolve_profile(profile)
    return store.get(f"{p}:appkey") or ""


def get_secretkey(profile: str | None = None) -> str:
    p = resolve_profile(profile)
    return store.get(f"{p}:secretkey") or ""


def set_appkey(value: str, profile: str | None = None) -> None:
    p = resolve_profile(profile)
    store.set(f"{p}:appkey", value)


def set_secretkey(value: str, profile: str | None = None) -> None:
    p = resolve_profile(profile)
    store.set(f"{p}:secretkey", value)


def get_account(profile: str | None = None) -> str:
    env = os.environ.get("KIWOOM_ACCOUNT")
    if env:
        return env
    p = resolve_profile(profile)
    cfg = load_config()
    return cfg.get("profiles", {}).get(p, {}).get("account", "")


def get_profiles() -> list[str]:
    """Return list of configured profile names."""
    cfg = load_config()
    return list(cfg.get("profiles", {}).keys())


def get_default_profile() -> str:
    """Return the default profile name."""
    cfg = load_config()
    return cfg.get("general", {}).get("default_profile", "default")


def set_default_profile(name: str) -> None:
    """Set the default profile."""
    cfg = load_config()
    cfg.setdefault("general", {})["default_profile"] = name
    save_config(cfg)


def is_dangerous_mode() -> bool:
    """Check if dangerous mode is enabled (skip system auth for orders)."""
    cfg = load_config()
    return cfg.get("general", {}).get("dangerous_mode", "off") == "on"


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
            store.set("default:appkey", ak)
        if sk:
            store.set("default:secretkey", sk)
        cfg.pop("auth", None)
        save_config(cfg)
        migrated = True
    # Migrate from plain keyring (v0.4.0 format)
    plain_ak = keyring.get_password(KEYRING_SERVICE, "appkey")
    if plain_ak and not plain_ak.startswith("ey"):  # not already encrypted (base64 JSON)
        store.set("default:appkey", plain_ak)
        migrated = True
    plain_sk = keyring.get_password(KEYRING_SERVICE, "secretkey")
    if plain_sk and not plain_sk.startswith("ey"):
        store.set("default:secretkey", plain_sk)
        migrated = True
    # Migrate token file to plain keyring
    token_file = CONFIG_DIR / "token"
    if token_file.exists():
        token = token_file.read_text().strip()
        if token:
            keyring.set_password(KEYRING_SERVICE, "default:token", token)
        token_file.unlink()
        migrated = True
    return migrated


def migrate_to_profiles() -> bool:
    """Migrate pre-profile config and keyring keys to profile-aware format."""
    cfg = load_config()
    if "profiles" in cfg:
        return False
    migrated = False
    general = cfg.get("general", {})
    # config.toml: general.domain/account -> profiles.default
    profile_data: dict[str, str] = {}
    if "domain" in general:
        profile_data["domain"] = general.pop("domain")
    if "account" in general:
        profile_data["account"] = general.pop("account")
    if profile_data:
        cfg.setdefault("profiles", {})["default"] = profile_data
        general["default_profile"] = "default"
        cfg["general"] = general
        save_config(cfg)
        migrated = True
    # keyring: bare keys -> default:-prefixed
    for key in ("appkey", "secretkey"):
        raw = keyring.get_password(KEYRING_SERVICE, key)
        if raw is not None:
            keyring.set_password(KEYRING_SERVICE, f"default:{key}", raw)
            keyring.delete_password(KEYRING_SERVICE, key)
            migrated = True
    raw_token = keyring.get_password(KEYRING_SERVICE, "token")
    if raw_token is not None:
        keyring.set_password(KEYRING_SERVICE, "default:token", raw_token)
        keyring.delete_password(KEYRING_SERVICE, "token")
        migrated = True
    return migrated
