"""Configuration management for Kiwoom CLI.

Priority: environment variables > OS keychain > config.toml

Credentials (appkey, secretkey, token) are stored directly in the OS
keychain via keyring (macOS Keychain / Windows Credential Manager /
Linux Secret Service). The keychain encrypts secrets at rest; no
app-level password is required — commands never prompt.

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


def _keyring_get(key: str) -> str | None:
    """keyring.get_password, treating keyring errors as "not stored".

    Locked/absent keychains (headless, CI, sandboxed shells) must degrade to
    "미설정" instead of crashing read-only commands like config show.
    """
    try:
        return keyring.get_password(KEYRING_SERVICE, key)
    except Exception:
        return None


def is_legacy_encrypted() -> bool:
    """True if the pre-v2.1 password-encrypted format is present in the keychain.

    Keyring errors (locked/absent keychain in headless or CI environments) are
    treated as "not legacy" so commands like --help never crash.
    """
    return _keyring_get("_salt") is not None


def clear_legacy_sentinels() -> None:
    """Remove the legacy SecureStore sentinels (_salt, _verify)."""
    for key in ("_salt", "_verify"):
        try:
            keyring.delete_password(KEYRING_SERVICE, key)
        except keyring.errors.PasswordDeleteError:
            pass


def purge_legacy_credentials() -> None:
    """Delete legacy Fernet-encrypted appkey/secretkey entries for all profiles.

    Tokens are untouched (they were always stored plaintext and remain valid).
    """
    for p in get_profiles():
        for key in (f"{p}:appkey", f"{p}:secretkey"):
            try:
                keyring.delete_password(KEYRING_SERVICE, key)
            except keyring.errors.PasswordDeleteError:
                pass


def is_configured(profile: str | None = None) -> bool:
    """True if an appkey is stored for the profile (and not in legacy format)."""
    if is_legacy_encrypted():
        return False
    p = resolve_profile(profile)
    return _keyring_get(f"{p}:appkey") is not None


def get_appkey(profile: str | None = None) -> str:
    if is_legacy_encrypted():
        return ""
    p = resolve_profile(profile)
    return _keyring_get(f"{p}:appkey") or ""


def get_secretkey(profile: str | None = None) -> str:
    if is_legacy_encrypted():
        return ""
    p = resolve_profile(profile)
    return _keyring_get(f"{p}:secretkey") or ""


def set_appkey(value: str, profile: str | None = None) -> None:
    p = resolve_profile(profile)
    keyring.set_password(KEYRING_SERVICE, f"{p}:appkey", value)


def set_secretkey(value: str, profile: str | None = None) -> None:
    p = resolve_profile(profile)
    keyring.set_password(KEYRING_SERVICE, f"{p}:secretkey", value)


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


def migrate_from_plaintext() -> bool:
    """Migrate legacy plaintext credential locations into the keychain."""
    migrated = False
    # Migrate from config.toml [auth] section
    cfg = load_config()
    auth_section = cfg.get("auth", {})
    ak = auth_section.get("appkey", "")
    sk = auth_section.get("secretkey", "")
    if ak or sk:
        if ak:
            keyring.set_password(KEYRING_SERVICE, "default:appkey", ak)
        if sk:
            keyring.set_password(KEYRING_SERVICE, "default:secretkey", sk)
        cfg.pop("auth", None)
        save_config(cfg)
        migrated = True
    # Migrate token file to keyring
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
