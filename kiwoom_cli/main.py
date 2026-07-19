"""Kiwoom CLI entry point."""

from __future__ import annotations

import copy
import json
import os

import click
import httpx
import keyring

from . import __version__, auth, config, envelope
from .client import KiwoomClient, KiwoomAPIError, KiwoomAuthError
from .commands.account import account
from .commands.dashboard import dashboard
from .commands.history import history
from .commands.market import market
from .commands.order import order
from .commands.stock import stock
from .commands.stream import stream
from .commands.watch import watch
from .formatters import _get_format, fail_input, human, print_generic_table
from .output import console, err_console

# Exit codes
EXIT_OK = 0
EXIT_INPUT = 1   # Bad args (invalid option value, missing argument, malformed input)
EXIT_API = 2     # API or network error
EXIT_AUTH = 3    # Token missing or expired

# Click's UsageError defaults to exit code 2, which collides with EXIT_API and
# breaks the documented contract (1=입력오류, 2=API오류). Automation must be able
# to tell "fix my arguments" from "the API failed".
click.exceptions.UsageError.exit_code = EXIT_INPUT


class KiwoomGroup(click.Group):
    """Custom group that catches API/network errors globally."""

    @staticmethod
    def _json_mode(ctx) -> bool:
        # 알 수 없는 하위 명령 등 ctx.obj가 채워지기 전의 오류에서도 -f json을 인식해야
        # envelope 계약이 지켜진다 (루트 파라미터는 이미 파싱되어 있음).
        if ctx.obj and ctx.obj.get("format"):
            return ctx.obj["format"] == "json"
        return ctx.params.get("output_format") == "json"

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except KiwoomAPIError as e:
            stable_code, _ = envelope.classify(upstream_code=e.code)
            auth_related = stable_code in ("TOKEN_EXPIRED", "AUTH_REQUIRED")
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(e.msg, upstream_code=e.code))
            elif auth_related:
                err_console.print(f"[red]인증 오류:[/] {e} [dim]kiwoom auth login[/]")
            else:
                err_console.print(f"[red]API 오류:[/] {e}")
            ctx.exit(EXIT_AUTH if auth_related else EXIT_API)
        except KiwoomAuthError:
            keychain_ok = auth.keychain_readable()
            if self._json_mode(ctx):
                msg = (
                    "토큰이 없습니다. 'kiwoom auth login'으로 발급하세요."
                    if keychain_ok else
                    "토큰이 없습니다. 키체인 접근 불가 환경 — 본인 터미널에서 발급한 토큰을 KIWOOM_TOKEN 환경변수로 전달하세요."
                )
                envelope.emit(error=envelope.error_body(
                    msg, code="AUTH_REQUIRED", retryable=False,
                ))
            elif keychain_ok:
                err_console.print("[red]인증 필요:[/] 토큰이 없습니다. [dim]kiwoom auth login[/]")
            else:
                err_console.print("[red]인증 필요:[/] 토큰이 없습니다 (키체인 접근 불가 환경).")
                err_console.print(
                    "[dim]본인 터미널에서 'kiwoom auth login'으로 발급한 토큰을 "
                    "KIWOOM_TOKEN 환경변수로 전달하세요. (README '샌드박스 환경' 참고)[/]"
                )
            ctx.exit(EXIT_AUTH)
        except keyring.errors.KeyringError:
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(
                    "OS 키체인에 접근할 수 없습니다. KIWOOM_TOKEN 환경변수를 사용하세요.",
                    code="KEYCHAIN_UNAVAILABLE", retryable=False,
                ))
            else:
                err_console.print("[red]키체인 오류:[/] OS 키체인에 접근할 수 없습니다 (잠김 또는 비대화형 세션).")
                err_console.print(
                    "[dim]키체인 없는 환경에서는 본인 터미널에서 토큰을 발급한 뒤 "
                    "KIWOOM_TOKEN 환경변수로 전달하세요. (README '샌드박스 환경' 참고)[/]"
                )
            ctx.exit(EXIT_INPUT)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(f"HTTP {status}", http_status=status))
            elif status == 401:
                err_console.print("[red]인증 오류:[/] 토큰이 만료되었습니다. [dim]kiwoom auth login[/]")
            else:
                err_console.print(f"[red]HTTP 오류:[/] {status}")
            ctx.exit(EXIT_AUTH if status == 401 else EXIT_API)
        except httpx.ConnectError:
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(
                    "API 서버에 연결할 수 없습니다. 도메인을 확인하세요.",
                    code="NETWORK_ERROR", retryable=True,
                ))
            else:
                err_console.print("[red]연결 오류:[/] API 서버에 연결할 수 없습니다. 도메인을 확인하세요.")
            ctx.exit(EXIT_API)
        except httpx.RequestError as e:
            # 타임아웃 등 나머지 전송 오류 — traceback 대신 계약대로 종료
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(
                    f"네트워크 오류: {type(e).__name__}. 잠시 후 재시도하세요.",
                    code="NETWORK_ERROR", retryable=True,
                ))
            else:
                err_console.print(f"[red]네트워크 오류:[/] {type(e).__name__} — 잠시 후 재시도하세요.")
            ctx.exit(EXIT_API)
        except click.ClickException as e:
            # 인자/옵션 오류(UsageError 포함)도 json 모드에서는 envelope로.
            # table 모드는 Click 기본 출력 그대로 (re-raise).
            # 일부 호출부(예: config.load_config의 TOMLDecodeError 재발생)는
            # 더 구체적인 코드를 e.code에 실어 보낸다 — 없으면 INVALID_INPUT.
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(
                    e.format_message(), code=getattr(e, "code", "INVALID_INPUT"),
                    retryable=False,
                ))
                ctx.exit(e.exit_code)
            raise


@click.group(cls=KiwoomGroup)
@click.version_option(__version__, prog_name="kiwoom")
@click.option("-f", "--format", "output_format",
              type=click.Choice(["table", "json", "csv"]),
              default="table", help="출력 형식")
@click.option("-p", "--profile", default=None, help="사용할 프로필")
@click.option("--fields", "fields", default=None,
              help="json 출력의 data에서 유지할 필드 (쉼표구분). raw는 항상 제거 — 토큰 절약용")
@click.option("--next-key", "next_key", default=None,
              help="연속조회 커서 — 이전 응답 meta.cont.next_key를 전달하면 첫 API 요청이 해당 페이지부터 조회")
@click.option("--all-pages", "all_pages", is_flag=True,
              help="연속조회를 끝까지 자동 반복해 리스트를 병합 (최대 50페이지)")
@click.option("--no-color", is_flag=True, help="색상 없이 출력")
@click.pass_context
def cli(ctx, output_format, profile, fields, no_color, next_key, all_pages):
    """키움증권 REST API CLI.

    사용법:

    \b
      kiwoom config setup          # 초기 설정 (appkey, secretkey)
      kiwoom auth login             # 접근토큰 발급
      kiwoom stock info 005930      # 삼성전자 기본정보
      kiwoom stock orderbook 005930 # 호가창
      kiwoom account balance        # 계좌 잔고
      kiwoom order buy 005930 10 --type market --confirm  # 시장가 매수
      kiwoom market rank volume     # 거래량 상위
      kiwoom stream quote 005930   # 실시간 체결 스트리밍
      kiwoom api ka10001 '{"stk_cd":"005930"}' -f json  # JSON 출력
    """
    ctx.ensure_object(dict)
    ctx.obj["format"] = output_format
    ctx.obj["profile"] = profile
    ctx.obj["fields"] = [s.strip() for s in fields.split(",") if s.strip()] if fields else None

    try:
        resolved_profile = config.resolve_profile(profile)
    except click.ClickException:
        # config.toml이 손상된 경우 루트 콜백에서 여기서 죽으면 그 어떤
        # 서브커맨드도(복구용인 'config setup'조차) 실행될 기회가 없다 — 실제
        # 진단/복구는 각 서브커맨드가 필요할 때 load_config()를 다시 호출해
        # 스스로 판단하게 둔다: config_setup은 자신의 폴백으로 복구하고,
        # 나머지는 자기 몸체에서 동일하게 NOT_CONFIGURED로 정상 실패한다.
        resolved_profile = profile or "default"
    if not config.is_valid_profile_name(resolved_profile):
        fail_input(
            f"잘못된 프로필 이름 '{resolved_profile}' — "
            "영문자/숫자/하이픈/언더스코어 1~64자만 허용됩니다."
        )

    if next_key and all_pages:
        raise click.UsageError("--next-key와 --all-pages는 함께 사용할 수 없습니다.")
    ctx.obj["next_key"] = next_key
    ctx.obj["all_pages"] = all_pages

    # v2.7 이하가 만든 느슨한 권한(0755/0644)을 매 실행 시 조인다 — 생성은 하지 않음
    config.harden_permissions()

    try:
        # Auto-migrate plaintext credentials into the keychain
        if config.migrate_from_plaintext():
            from .output import err_console
            err_console.print("[yellow]인증정보를 키체인으로 이전했습니다.[/]")

        # Auto-migrate pre-profile config to profile-aware format
        if config.migrate_to_profiles():
            from .output import err_console
            err_console.print("[yellow]프로필 형식으로 마이그레이션 완료.[/]")
    except click.ClickException:
        # 위와 같은 이유로 건너뛴다 — 마이그레이션은 유효한 config.toml을
        # 전제로 하므로, 손상된 파일 위에서는 서브커맨드가 판단하게 둔다.
        pass

    # Legacy password-encrypted format: credentials must be re-entered
    if config.is_legacy_encrypted():
        from .output import err_console
        err_console.print(
            "[yellow]암호화 저장소 형식이 변경되었습니다. 'kiwoom config setup'으로 다시 설정하세요.[/]"
        )

    if no_color:
        # 각 모듈이 import 시점에 잡아둔 인스턴스 참조가 유효해야 하므로
        # 재바인딩이 아니라 기존 Console 객체를 변이시킨다.
        from . import output
        output.console.no_color = True
        output.err_console.no_color = True


# ── Config ────────────────────────────────────────────

@cli.group("config")
def config_cmd():
    """설정 관리."""
    pass


@config_cmd.command("setup")
@click.option("--profile", default=None, help="프로필 이름 (기본: 루트 -p/--profile, 없으면 default)")
@click.option("--appkey", default=None, help="키움 API App Key")
@click.option("--secretkey", default=None, help="키움 API Secret Key")
@click.option("--domain", default=None, type=click.Choice(["prod", "mock"]), help="도메인")
@click.option("--account", default="", help="계좌번호")
@click.option("--token-storage", "token_storage", default=None,
              type=click.Choice(list(config.TOKEN_STORAGES)),
              help="접근토큰 저장 방식")
@click.pass_context
def config_setup(ctx, profile: str | None, appkey: str | None, secretkey: str | None,
                 domain: str | None, account: str, token_storage: str | None):
    """초기 설정 (App Key, Secret Key, 도메인)."""
    if profile is None:
        profile = (ctx.obj.get("profile") if ctx.obj else None) or "default"
    if not config.is_valid_profile_name(profile):
        fail_input(
            f"잘못된 프로필 이름 '{profile}' — "
            "영문자/숫자/하이픈/언더스코어 1~64자만 허용됩니다."
        )
    interactive = _get_format() == "table"
    if not interactive:
        missing = [n for n, v in (("--appkey", appkey), ("--secretkey", secretkey)) if not v]
        if missing:
            fail_input("config setup 필수 옵션 누락: " + ", ".join(missing))
        domain = domain or "mock"
        token_storage = token_storage or "keychain"
    else:
        if appkey is None:
            appkey = click.prompt("App Key", err=True)
        if secretkey is None:
            secretkey = click.prompt("Secret Key", hide_input=True, err=True)
        if domain is None:
            domain = click.prompt("도메인 (prod=실거래, mock=모의투자)",
                                  type=click.Choice(["prod", "mock"]), default="mock", err=True)
        if not account:
            account = click.prompt("계좌번호 (없으면 Enter)", default="", err=True)
        if token_storage is None:
            token_storage = click.prompt(
                "토큰 저장 방식 (keychain=OS 키체인, env=KIWOOM_TOKEN 직접 관리)",
                type=click.Choice(list(config.TOKEN_STORAGES)), default="keychain", err=True)
    if config.is_legacy_encrypted():
        # Old password-encrypted entries are unusable — purge before writing new keys
        config.purge_legacy_credentials()
        config.clear_legacy_sentinels()
    try:
        cfg = config.load_config()
    except click.ClickException:
        # config.toml이 손상된 경우에도 setup은 이걸 복구하는 명령이어야 한다 —
        # 어차피 아래에서 덮어쓸 것이므로 기본값에서 새로 시작한다. 이 명령이
        # 실패하면 (load_config()가 재발생시키는 NOT_CONFIGURED로) 안내하는
        # 'kiwoom config setup을 다시 실행하세요'가 그 자체로 다시 실패하는
        # 무한루프가 됐었다.
        err_console.print(
            f"[yellow]config.toml이 손상되어 있어 기본값으로 새로 씁니다 ({config.CONFIG_FILE}).[/]"
        )
        cfg = copy.deepcopy(config.DEFAULT_CONFIG)
    # load_config()가 성공한 뒤에만 키체인에 쓴다 — 실패 케이스가 위에서
    # 처리되므로 여기 도달했다는 것은 cfg 구성이 확정됐다는 뜻이고, appkey/
    # secretkey를 먼저 써버린 뒤 이후 단계가 죽어 키체인만 반쯤 갱신된 채
    # 남는 상황을 막는다.
    config.set_appkey(appkey, profile=profile)
    config.set_secretkey(secretkey, profile=profile)
    cfg.setdefault("profiles", {}).setdefault(profile, {})["domain"] = domain
    if account:
        cfg["profiles"][profile]["account"] = account
    cfg["profiles"][profile]["token_storage"] = token_storage
    if "default_profile" not in cfg.get("general", {}):
        cfg.setdefault("general", {})["default_profile"] = profile
    cfg.pop("auth", None)
    config.save_config(cfg)
    if _get_format() == "json":
        envelope.emit(data={
            "profile": profile, "domain": domain,
            "account": account or "", "token_storage": token_storage,
        })
        return
    console.print(f"[green]설정 완료![/] (프로필: {profile})")
    console.print("  App Key/Secret Key: [bold]OS 키체인에 저장됨[/]")
    console.print(f"  도메인: [bold]{config.DOMAINS[domain]}[/]")
    if token_storage == "env":
        console.print("  토큰 저장: [bold]환경변수 (KIWOOM_TOKEN)[/] — auth login 후 안내되는 export를 실행하세요")
    else:
        console.print("  토큰 저장: [bold]OS 키체인[/]")


@config_cmd.command("show")
@click.pass_context
def config_show(ctx):
    """현재 설정 확인."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    cfg = config.load_config()
    configured = config.is_configured(profile)
    profile_cfg = cfg.get("profiles", {}).get(profile, {})
    token_storage = config.get_token_storage(profile)
    if _get_format() == "json":
        envelope.emit(data={
            "profile": profile,
            "config_file": str(config.CONFIG_FILE),
            "domain": profile_cfg.get("domain", "mock"),
            "configured": configured,
            "account": profile_cfg.get("account", ""),
            "token_storage": token_storage,
        })
        return
    human(f"  프로필: [bold]{profile}[/]")
    human(f"  설정 파일: {config.CONFIG_FILE}")
    human(f"  도메인: {profile_cfg.get('domain', 'mock')}")
    human(f"  App Key: {'[dim]설정됨 (키체인)[/]' if configured else '(미설정)'}")
    human(f"  계좌번호: {profile_cfg.get('account', '(미설정)')}")
    human(f"  토큰 저장: {'환경변수 (KIWOOM_TOKEN)' if token_storage == 'env' else 'OS 키체인'}")
    human(f"  보안: [bold]{'OS 키체인 저장' if configured else '미설정'}[/]")


@config_cmd.command("set")
@click.argument("key", type=click.Choice(["domain", "account", "token_storage"]))
@click.argument("value")
@click.pass_context
def config_set(ctx, key: str, value: str):
    """프로필 설정 변경. (예: kiwoom config set domain prod)"""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    if key == "domain" and value not in ("prod", "mock"):
        fail_input("domain은 prod 또는 mock만 가능합니다.")
    if key == "token_storage" and value not in config.TOKEN_STORAGES:
        fail_input("token_storage는 keychain 또는 env만 가능합니다.")
    cfg = config.load_config()
    cfg.setdefault("profiles", {}).setdefault(profile, {})[key] = value
    config.save_config(cfg)
    if _get_format() == "json":
        envelope.emit(data={"key": key, "value": value, "profile": profile})
        return
    display = config.DOMAINS[value] if key == "domain" else value
    console.print(f"[green]{key} 변경:[/] {display} (프로필: {profile})")


# Backward compatibility: keep 'domain' as alias
@config_cmd.command("domain", hidden=True)
@click.argument("domain", type=click.Choice(["prod", "mock"]))
@click.pass_context
def config_domain(ctx, domain: str):
    """도메인 변경 (config set domain의 별칭)."""
    ctx.invoke(config_set, key="domain", value=domain)


@config_cmd.command("use")
@click.argument("profile_name")
def config_use(profile_name: str):
    """기본 프로필 변경."""
    if not config.is_valid_profile_name(profile_name):
        fail_input(
            f"잘못된 프로필 이름 '{profile_name}' — "
            "영문자/숫자/하이픈/언더스코어 1~64자만 허용됩니다."
        )
    profiles = config.get_profiles()
    if profile_name not in profiles:
        fail_input(f"프로필 '{profile_name}'을(를) 찾을 수 없습니다.")
    config.set_default_profile(profile_name)
    if _get_format() == "json":
        envelope.emit(data={"default_profile": profile_name})
        return
    console.print(f"[green]기본 프로필 변경:[/] {profile_name}")


@config_cmd.command("profiles")
def config_profiles():
    """등록된 프로필 목록."""
    cfg = config.load_config()
    profiles = cfg.get("profiles", {})
    default = config.get_default_profile()
    if _get_format() == "json":
        envelope.emit(data=[
            {
                "name": name,
                "domain": settings.get("domain", "mock"),
                "account": settings.get("account", ""),
                "default": name == default,
            }
            for name, settings in profiles.items()
        ])
        return
    if not profiles:
        human("[yellow]등록된 프로필이 없습니다.[/]")
        return
    human(f"  현재 프로필: [bold green]{default}[/]")
    human("")
    for name, settings in profiles.items():
        marker = " [green]*[/]" if name == default else "  "
        domain = settings.get("domain", "mock")
        account = settings.get("account", "") or "(미설정)"
        human(f"  {marker} {name:15s} 도메인={domain}  계좌={account}")


# ── Auth ──────────────────────────────────────────────

@cli.group("auth")
def auth_cmd():
    """인증 (토큰 발급/폐기)."""
    pass


def _fail_not_configured():
    msg = "설정이 필요합니다. 먼저 실행: kiwoom config setup"
    if _get_format() == "json":
        envelope.emit(error=envelope.error_body(msg, code="NOT_CONFIGURED", retryable=False))
    else:
        human(f"[red]{msg}[/]")
    raise SystemExit(EXIT_INPUT)


@auth_cmd.command("login")
@click.pass_context
def auth_login(ctx):
    """접근토큰 발급."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    if not config.is_configured(profile):
        _fail_not_configured()
    # 발급 실패(KiwoomAPIError)는 전역 핸들러가 envelope/exit 2로 처리
    with KiwoomClient() as c:
        token = c.issue_token()
    storage = config.get_token_storage(profile)
    if _get_format() == "json":
        # env 모드에서는 사용자가 직접 관리해야 하므로 토큰 원문을 포함
        envelope.emit(data={
            "profile": profile,
            "token_storage": storage,
            "saved": storage != "env",
            "token": token if storage == "env" else None,
        })
        return
    human("[green]토큰 발급 완료![/]")
    if storage == "env":
        human("  저장 위치: [bold]없음 (env 모드)[/] — 아래를 셸에서 실행하세요:")
        human(f"  export KIWOOM_TOKEN='{token}'")
    else:
        masked = token[:10] + "..." + token[-4:] if len(token) > 14 else token
        human(f"  토큰: {masked}")
        human("  저장 위치: [bold]키체인[/]")


@auth_cmd.command("logout")
@click.pass_context
def auth_logout(ctx):
    """접근토큰 폐기."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    if not config.is_configured(profile):
        _fail_not_configured()
    # 폐기 실패(KiwoomAPIError)는 전역 핸들러가 envelope/exit 2로 처리
    with KiwoomClient() as c:
        c.revoke_token()
    if _get_format() == "json":
        envelope.emit(data={"profile": profile, "revoked": True})
    else:
        human("[green]토큰 폐기 완료.[/]")
    if os.environ.get("KIWOOM_TOKEN"):
        human("[yellow]KIWOOM_TOKEN 환경변수가 설정되어 있어 이 셸에서는 해당 토큰이 계속 사용됩니다. unset KIWOOM_TOKEN 으로 제거하세요.[/]")


@auth_cmd.command("status")
@click.pass_context
def auth_status(ctx):
    """토큰 상태 확인."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    configured = config.is_configured(profile)
    token_storage = config.get_token_storage(profile)
    token = auth.load_token(profile=profile)
    token_source = None
    if token is not None:
        token_source = "env" if os.environ.get("KIWOOM_TOKEN") else "keyring"
    if _get_format() == "json":
        cfg = config.load_config()
        envelope.emit(data={
            "profile": profile,
            "domain": cfg.get("profiles", {}).get(profile, {}).get("domain", "mock"),
            "configured": configured,
            "has_token": token is not None,
            "token_source": token_source,
            "token_storage": token_storage,
        })
        return
    if not configured and token is None:
        if not auth.keychain_readable():
            human("[yellow]키체인 접근 불가 환경.[/] 본인 터미널에서 발급한 토큰을 KIWOOM_TOKEN 환경변수로 전달하세요.")
        else:
            human("[yellow]설정 필요.[/] 'kiwoom config setup' 으로 설정하세요.")
        return
    human(f"  프로필: [bold]{profile}[/]")
    if token is not None:
        source_label = "환경변수 KIWOOM_TOKEN" if token_source == "env" else "키체인 저장됨"
        human(f"[green]토큰 있음[/] [dim]({source_label})[/]")
    elif token_storage == "env":
        human("[yellow]토큰 없음.[/] 'kiwoom auth login' 으로 발급 후 안내되는 export KIWOOM_TOKEN을 실행하세요.")
    elif not auth.keychain_readable():
        human("[yellow]토큰 없음.[/] 키체인 접근 불가 환경 — 본인 터미널에서 발급한 토큰을 KIWOOM_TOKEN 환경변수로 전달하세요.")
    else:
        human("[yellow]토큰 없음.[/] 'kiwoom auth login' 으로 발급하세요.")


# ── Raw API ───────────────────────────────────────────

@cli.command("api")
@click.argument("api_id")
@click.argument("body", default="{}")
@click.option("--raw", is_flag=True, help="JSON 원본 출력")
@click.option("--next-key", "next_key", default="", help="연속조회 커서 (이전 응답의 meta.cont.next_key)")
@click.option("--confirm", "--yes", "confirm", is_flag=True,
              help="주문성 API(매수/매도/정정/취소/환전) 확인 생략 (자동화용)")
def raw_api(api_id: str, body: str, raw: bool, next_key: str, confirm: bool):
    """Raw API 호출. (예: kiwoom api ka10001 '{"stk_cd":"005930"}')

    \b
    api_id 자리에 list를 주면 전체 API 목록(217개 REST)을 출력합니다.
    두 번째 인자는 검색 키워드: kiwoom api list 미체결
    """
    from .api_spec import API_REGISTRY

    if api_id == "list":
        keyword = "" if body == "{}" else body.lower()
        rows = [
            {"api_id": aid, "url_path": url, "description": desc}
            for aid, (url, desc) in sorted(API_REGISTRY.items())
            if not keyword or keyword in aid.lower() or keyword in desc.lower()
        ]
        if _get_format() == "json":
            envelope.emit(data=rows)
            return
        from rich.markup import escape
        for r in rows:
            console.print(f"  {r['api_id']}  [dim]{escape(r['description'])}[/]", highlight=False)
        console.print(f"[dim]{len(rows)}개 API — kiwoom api <id> '<body-json>' 로 호출[/]")
        return

    if api_id not in API_REGISTRY:
        fail_input(f"알 수 없는 API ID: {api_id}", code="INVALID_API")

    try:
        body_dict = json.loads(body)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON body: {e}")

    from .api_spec import MUTATION_APIS, get_description
    from .commands._mutation import confirm_gate, suppress_pagination
    if api_id in MUTATION_APIS:
        if _get_format() == "table" and not confirm:
            # 미리보기 먼저, 확인은 그 다음 (Tier-1 불변식)
            err_console.print(
                f"[yellow]주문성 API {api_id} ({get_description(api_id)}) — 전송될 body:[/]"
            )
            err_console.print(json.dumps(body_dict, ensure_ascii=False, indent=2))
        confirm_gate(confirm)
        suppress_pagination()

    with KiwoomClient() as c:
        data, headers = c.request(
            api_id, body_dict,
            cont_yn="Y" if next_key else "",
            next_key=next_key,
        )
        if raw:
            if _get_format() == "json":
                # --raw는 필드 제거만 생략: stdout은 여전히 단일 envelope 문서
                envelope.emit(data=data)
            else:
                console.print_json(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            title = get_description(api_id)
            print_generic_table(data, title=title)

        if headers.get("cont-yn") == "Y" and api_id not in MUTATION_APIS:
            err_console.print(f"\n[dim]연속조회 가능 (next-key: {headers.get('next-key', '')})[/]")


# ── Describe (CLI 자기서술) ───────────────────────────

def _param_spec(p: click.Parameter) -> dict:
    default = p.default
    if callable(default):
        default = None
    elif isinstance(default, tuple):
        default = list(default)
    if not isinstance(default, (str, int, float, bool, list, type(None))):
        default = None  # click 내부 Sentinel 등 JSON 비직렬화 값
    spec: dict = {
        "name": p.name,
        "opts": list(p.opts) + list(p.secondary_opts),
        "type": p.type.name,
        "required": p.required,
        "default": default,
    }
    if isinstance(p.type, click.Choice):
        spec["choices"] = list(p.type.choices)
    if isinstance(p, click.Option):
        spec["is_flag"] = p.is_flag
        spec["help"] = p.help
    return spec


def _describe_command(cmd: click.Command, path: str, depth: int | None = None) -> dict:
    spec: dict = {
        "path": path,
        "help": (cmd.help or cmd.short_help or "").strip(),
        "arguments": [_param_spec(p) for p in cmd.params if isinstance(p, click.Argument)],
        "options": [_param_spec(p) for p in cmd.params if isinstance(p, click.Option)],
    }
    if isinstance(cmd, click.Group):
        if depth is not None and depth <= 0:
            spec["subcommands"] = []
        else:
            next_depth = None if depth is None else depth - 1
            spec["subcommands"] = [
                _describe_command(sub, f"{path} {name}", next_depth)
                for name, sub in sorted(cmd.commands.items())
                if not sub.hidden
            ]
    return spec


def _collect_paths(cmd: click.Command, path: str) -> list[dict]:
    head = ((cmd.help or cmd.short_help or "").strip().splitlines() or [""])[0]
    rows = [{"path": path, "help": head}]
    if isinstance(cmd, click.Group):
        for name, sub in sorted(cmd.commands.items()):
            if not sub.hidden:
                rows.extend(_collect_paths(sub, f"{path} {name}"))
    return rows


def _render_describe(spec: dict, depth: int = 0) -> None:
    from rich.markup import escape

    pad = "  " * depth
    head = (spec["help"] or "").splitlines()[0] if spec["help"] else ""
    console.print(f"{pad}[bold]{escape(spec['path'])}[/]  [dim]{escape(head)}[/]", highlight=False)
    for a in spec["arguments"]:
        req = " (필수)" if a["required"] else ""
        choices = f" {'|'.join(a['choices'])}" if a.get("choices") else ""
        console.print(f"{pad}  [cyan]{escape(a['name'].upper())}[/] <{a['type']}>{escape(choices)}{req}", highlight=False)
    for o in spec["options"]:
        parts = "/".join(o["opts"])
        choices = f" [{'|'.join(o['choices'])}]" if o.get("choices") else ""
        default = f" (기본: {o['default']})" if o.get("default") not in (None, "", False, 0) else ""
        console.print(
            f"{pad}  [green]{escape(parts)}[/]{escape(choices)}{escape(default)}  [dim]{escape(o.get('help') or '')}[/]",
            highlight=False,
        )
    for sub in spec.get("subcommands", []):
        _render_describe(sub, depth + 1)


@cli.command("describe")
@click.argument("command_path", nargs=-1)
@click.option("--paths", "paths_only", is_flag=True,
              help="경로+한줄설명 평면 목록만 출력 (전체 트리 대비 토큰 절약 — 발견용)")
@click.option("--depth", type=int, default=None,
              help="하위 명령 재귀 깊이 제한 (예: --depth 1 = 한 단계만)")
def describe(command_path: tuple[str, ...], paths_only: bool, depth: int | None):
    """CLI 명령 구조 자기서술 — 경로/도움말/인자/옵션(타입·기본값·choices).

    에이전트가 도구 스키마를 파악할 때 사용합니다.

    \b
    예: kiwoom describe --paths -f json   # 전체 경로 목록 (저비용 발견)
        kiwoom describe order buy -f json # 단일 명령 상세 스키마
        kiwoom describe order --depth 1
    """
    cmd: click.Command = cli
    path = "kiwoom"
    for name in command_path:
        if not isinstance(cmd, click.Group) or name not in cmd.commands:
            raise click.ClickException(f"명령을 찾을 수 없습니다: {' '.join(command_path)}")
        cmd = cmd.commands[name]
        path += f" {name}"
    if paths_only:
        rows = _collect_paths(cmd, path)
        if _get_format() == "json":
            envelope.emit(data=rows)
            return
        for r in rows:
            console.print(f"[bold]{r['path']}[/]  [dim]{r['help']}[/]", highlight=False)
        return
    spec = _describe_command(cmd, path, depth)
    if _get_format() == "json":
        envelope.emit(data=spec)
        return
    _render_describe(spec)


@cli.command("find")
@click.argument("keyword")
def find_cmd(keyword: str):
    """명령어/API 통합 검색 — 명령 경로·도움말·API ID·API 설명에서 키워드 검색.

    \b
    예: kiwoom find 미체결            # 관련 명령어 + API ID
        kiwoom find balance -f json  # 에이전트용 구조화 출력
    """
    kw = keyword.lower()
    cmd_rows = [
        r for r in _collect_paths(cli, "kiwoom")
        if kw in r["path"].lower() or kw in r["help"].lower()
    ]
    from .api_spec import API_REGISTRY
    api_rows = [
        {"api_id": aid, "description": desc}
        for aid, (_, desc) in sorted(API_REGISTRY.items())
        if kw in aid.lower() or kw in desc.lower()
    ]
    if _get_format() == "json":
        envelope.emit(data={"commands": cmd_rows, "apis": api_rows})
        return
    from rich.markup import escape

    if not cmd_rows and not api_rows:
        console.print(f"[yellow]'{escape(keyword)}'에 대한 결과가 없습니다.[/]")
        return
    if cmd_rows:
        console.print(f"[bold]명령어 ({len(cmd_rows)})[/]")
        for r in cmd_rows:
            console.print(f"  {escape(r['path'])}  [dim]{escape(r['help'])}[/]", highlight=False)
    if api_rows:
        console.print(f"[bold]API ({len(api_rows)}) — kiwoom api <id>로 호출[/]")
        for r in api_rows:
            console.print(f"  {escape(r['api_id'])}  [dim]{escape(r['description'])}[/]", highlight=False)


# ── Register subcommands ─────────────────────────────

cli.add_command(stock)
cli.add_command(account)
cli.add_command(order)
cli.add_command(market)
cli.add_command(stream)
cli.add_command(history)
cli.add_command(dashboard)
cli.add_command(watch)


if __name__ == "__main__":
    cli()
