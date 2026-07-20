"""Configuration management for Kiwoom CLI.

Priority: environment variables > OS keychain > config.toml

Credentials (appkey, secretkey, token) are stored directly in the OS
keychain via keyring (macOS Keychain / Windows Credential Manager /
Linux Secret Service). The keychain encrypts secrets at rest; no
app-level password is required — commands never prompt.

Non-sensitive settings (domain, account, token_storage) remain in config.toml.
token_storage: "keychain" (기본, auth login이 토큰을 키체인에 저장) 또는
"env" (키체인에 저장하지 않음 — 사용자가 KIWOOM_TOKEN 환경변수로 직접 관리).

Environment variables (non-sensitive only):
  KIWOOM_DOMAIN       도메인 (prod / mock)
  KIWOOM_ACCOUNT      계좌번호
  KIWOOM_PROFILE      활성 프로필 이름

Config file: ~/.kiwoom/config.toml
"""

from __future__ import annotations

import copy
import os
import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import click
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

TOKEN_STORAGES = ("keychain", "env")

# 프로필 이름 allowlist — 원장 파일명(idempotency/<profile>-<env>.jsonl)과
# keyring 키(<profile>:appkey)에 그대로 들어가므로 경로 조작 문자를 차단한다
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_valid_profile_name(name: str) -> bool:
    return bool(PROFILE_NAME_RE.fullmatch(name))


DEFAULT_CONFIG = {
    "general": {"default_profile": "default"},
    "profiles": {"default": {"domain": "mock", "account": ""}},
}


def secure_dir(path: Path) -> None:
    """디렉토리를 생성하고 소유자 전용(0700)으로 강제한다. 이미 있어도 매번 조인다."""
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        path.chmod(0o700)


def secure_file(path: Path) -> None:
    """존재하는 파일을 소유자 전용(0600)으로 조인다. 없으면 아무것도 하지 않는다."""
    if os.name == "posix" and path.exists():
        path.chmod(0o600)


def ensure_config_dir() -> None:
    secure_dir(CONFIG_DIR)


def ensure_cache_dir() -> None:
    ensure_config_dir()
    secure_dir(CACHE_DIR)


def harden_permissions() -> None:
    """기존 설치본의 ~/.kiwoom 트리 권한을 일괄로 조인다 (디렉토리 0700, 파일 0600).

    계좌번호(config.toml)·주문 원장(idempotency/)·레코딩(data/)이 v2.7 이하에서
    0755/0644로 생성되어 다른 로컬 사용자가 읽을 수 있었다. 아무것도 생성하지 않는다.

    best-effort: root 소유 잔재 파일 등 chmod가 실패(OSError)해도 무시하고 계속
    조인다 — 파일 하나가 다른 사용자 소유라고 해서 매 명령이 죽으면 안 된다.
    """
    if os.name != "posix" or not CONFIG_DIR.exists():
        return

    failed = False

    def _try_chmod(path: Path, mode: int) -> None:
        nonlocal failed
        try:
            path.chmod(mode)
        except OSError:
            failed = True

    _try_chmod(CONFIG_DIR, 0o700)
    if CONFIG_FILE.exists():
        _try_chmod(CONFIG_FILE, 0o600)
    for sub in ("idempotency", "data", "cache"):
        d = CONFIG_DIR / sub
        if not d.is_dir():
            continue
        _try_chmod(d, 0o700)
        try:
            entries = list(d.iterdir())
        except OSError:
            failed = True
            continue
        for f in entries:
            if f.is_file():
                _try_chmod(f, 0o600)

    if failed:
        from .output import err_console
        err_console.print(
            "[dim]일부 파일/디렉토리 권한을 조이지 못했습니다 (다른 사용자 소유 등) — 무시하고 계속합니다.[/]"
        )


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        # deepcopy: 호출자가 중첩 dict를 수정해도 DEFAULT_CONFIG가 오염되지 않도록
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        # resolve_profile() 등 루트 콜백에서 호출되므로 여기서 escape하면
        # kiwoom config show조차 불가능해진다 — KiwoomGroup.invoke의 기존
        # ClickException 핸들러가 envelope으로 감싸도록 재발생시킨다.
        err = click.ClickException(
            f"config.toml이 손상되었습니다 ({CONFIG_FILE}): {e}. "
            "파일을 복구하거나 'kiwoom config setup'을 다시 실행하세요."
        )
        err.code = "NOT_CONFIGURED"
        raise err from e


def save_config(cfg: dict) -> None:
    ensure_config_dir()
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(cfg, f)
    secure_file(CONFIG_FILE)


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


def get_domain_key(profile: str | None = None) -> str:
    """도메인 키('prod'|'mock'). KIWOOM_DOMAIN env > 프로필 설정 > 'mock'.

    잘못된 KIWOOM_DOMAIN 값은 기존 get_domain과 동일하게 mock으로 강제한다
    (실서버로 잘못 붙는 것보다 안전한 방향).
    """
    env = os.environ.get("KIWOOM_DOMAIN")
    if env:
        return env if env in DOMAINS else "mock"
    p = resolve_profile(profile)
    cfg = load_config()
    key = cfg.get("profiles", {}).get(p, {}).get("domain", "mock")
    return key if key in DOMAINS else "mock"


def get_domain(profile: str | None = None) -> str:
    return DOMAINS[get_domain_key(profile)]


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


def get_token_storage(profile: str | None = None) -> str:
    """토큰 저장 방식: "keychain" (OS 키체인) 또는 "env" (KIWOOM_TOKEN 직접 관리)."""
    p = resolve_profile(profile)
    cfg = load_config()
    value = cfg.get("profiles", {}).get(p, {}).get("token_storage", "keychain")
    return value if value in TOKEN_STORAGES else "keychain"


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
    # keyring: bare keys -> default:-prefixed
    #
    # config 저장보다 **먼저** 옮긴다. cfg["profiles"]의 존재가 곧 위쪽
    # `if "profiles" in cfg: return False` 가드의 마이그레이션 완료 표식이므로,
    # 자격증명이 실제로 옮겨가기 전에 저장하면 keyring 도중 예외가 났을 때
    # 다음 실행이 가드에 걸려 bare 키가 영영 고아로 남는다.
    #
    # 각 키는 set -> delete 순서라 루프 자체가 멱등하다: set 직후에 죽으면
    # bare 키가 남아 다음 실행이 같은 값으로 다시 set하고 delete한다.
    # 따라서 keyring 이전과 config 저장 사이에서 죽어도 재실행이 완주한다.
    for key in ("appkey", "secretkey", "token"):
        raw = keyring.get_password(KEYRING_SERVICE, key)
        if raw is not None:
            keyring.set_password(KEYRING_SERVICE, f"default:{key}", raw)
            keyring.delete_password(KEYRING_SERVICE, key)
            migrated = True
    if profile_data:
        save_config(cfg)
        migrated = True
    return migrated
