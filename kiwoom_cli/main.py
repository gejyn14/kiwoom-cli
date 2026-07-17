"""Kiwoom CLI entry point."""

from __future__ import annotations

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
from .formatters import _get_format, human, print_generic_table
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
                console.print(f"[red]인증 오류:[/] {e} [dim]kiwoom auth login[/]")
            else:
                console.print(f"[red]API 오류:[/] {e}")
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
                console.print("[red]인증 필요:[/] 토큰이 없습니다. [dim]kiwoom auth login[/]")
            else:
                console.print("[red]인증 필요:[/] 토큰이 없습니다 (키체인 접근 불가 환경).")
                console.print(
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
                console.print("[red]키체인 오류:[/] OS 키체인에 접근할 수 없습니다 (잠김 또는 비대화형 세션).")
                console.print(
                    "[dim]키체인 없는 환경에서는 본인 터미널에서 토큰을 발급한 뒤 "
                    "KIWOOM_TOKEN 환경변수로 전달하세요. (README '샌드박스 환경' 참고)[/]"
                )
            ctx.exit(EXIT_INPUT)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(f"HTTP {status}", http_status=status))
            elif status == 401:
                console.print("[red]인증 오류:[/] 토큰이 만료되었습니다. [dim]kiwoom auth login[/]")
            else:
                console.print(f"[red]HTTP 오류:[/] {status}")
            ctx.exit(EXIT_AUTH if status == 401 else EXIT_API)
        except httpx.ConnectError:
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(
                    "API 서버에 연결할 수 없습니다. 도메인을 확인하세요.",
                    code="NETWORK_ERROR", retryable=True,
                ))
            else:
                console.print("[red]연결 오류:[/] API 서버에 연결할 수 없습니다. 도메인을 확인하세요.")
            ctx.exit(EXIT_API)
        except httpx.RequestError as e:
            # 타임아웃 등 나머지 전송 오류 — traceback 대신 계약대로 종료
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(
                    f"네트워크 오류: {type(e).__name__}. 잠시 후 재시도하세요.",
                    code="NETWORK_ERROR", retryable=True,
                ))
            else:
                console.print(f"[red]네트워크 오류:[/] {type(e).__name__} — 잠시 후 재시도하세요.")
            ctx.exit(EXIT_API)
        except click.ClickException as e:
            # 인자/옵션 오류(UsageError 포함)도 json 모드에서는 envelope로.
            # table 모드는 Click 기본 출력 그대로 (re-raise).
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(
                    e.format_message(), code="INVALID_INPUT", retryable=False,
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
@click.option("--no-color", is_flag=True, help="색상 없이 출력")
@click.pass_context
def cli(ctx, output_format, profile, fields, no_color):
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

    # Auto-migrate plaintext credentials into the keychain
    if config.migrate_from_plaintext():
        from .output import err_console
        err_console.print("[yellow]인증정보를 키체인으로 이전했습니다.[/]")

    # Auto-migrate pre-profile config to profile-aware format
    if config.migrate_to_profiles():
        from .output import err_console
        err_console.print("[yellow]프로필 형식으로 마이그레이션 완료.[/]")

    # Legacy password-encrypted format: credentials must be re-entered
    if config.is_legacy_encrypted():
        from .output import err_console
        err_console.print(
            "[yellow]암호화 저장소 형식이 변경되었습니다. 'kiwoom config setup'으로 다시 설정하세요.[/]"
        )

    if no_color:
        from rich.console import Console as RichConsole
        from . import output
        output.console = RichConsole(no_color=True)
        output.err_console = RichConsole(stderr=True, no_color=True)


# ── Config ────────────────────────────────────────────

@cli.group("config")
def config_cmd():
    """설정 관리."""
    pass


@config_cmd.command("setup")
@click.option("--profile", default="default", help="프로필 이름")
@click.option("--appkey", prompt="App Key", help="키움 API App Key")
@click.option("--secretkey", prompt="Secret Key", hide_input=True, help="키움 API Secret Key")
@click.option("--domain", prompt="도메인 (prod=실거래, mock=모의투자)", type=click.Choice(["prod", "mock"]), default="mock", help="도메인")
@click.option("--account", prompt="계좌번호 (없으면 Enter)", default="", help="계좌번호")
@click.option("--token-storage", "token_storage",
              prompt="토큰 저장 방식 (keychain=OS 키체인, env=KIWOOM_TOKEN 직접 관리)",
              type=click.Choice(list(config.TOKEN_STORAGES)), default="keychain",
              help="접근토큰 저장 방식")
def config_setup(profile: str, appkey: str, secretkey: str, domain: str, account: str, token_storage: str):
    """초기 설정 (App Key, Secret Key, 도메인)."""
    if config.is_legacy_encrypted():
        # Old password-encrypted entries are unusable — purge before writing new keys
        config.purge_legacy_credentials()
        config.clear_legacy_sentinels()
    config.set_appkey(appkey, profile=profile)
    config.set_secretkey(secretkey, profile=profile)
    cfg = config.load_config()
    cfg.setdefault("profiles", {}).setdefault(profile, {})["domain"] = domain
    if account:
        cfg["profiles"][profile]["account"] = account
    cfg["profiles"][profile]["token_storage"] = token_storage
    if "default_profile" not in cfg.get("general", {}):
        cfg.setdefault("general", {})["default_profile"] = profile
    cfg.pop("auth", None)
    config.save_config(cfg)
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
        console.print("[red]domain은 prod 또는 mock만 가능합니다.[/]")
        raise SystemExit(1)
    if key == "token_storage" and value not in config.TOKEN_STORAGES:
        console.print("[red]token_storage는 keychain 또는 env만 가능합니다.[/]")
        raise SystemExit(1)
    cfg = config.load_config()
    cfg.setdefault("profiles", {}).setdefault(profile, {})[key] = value
    config.save_config(cfg)
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
    profiles = config.get_profiles()
    if profile_name not in profiles:
        console.print(f"[red]프로필 '{profile_name}'을(를) 찾을 수 없습니다.[/]")
        raise SystemExit(1)
    config.set_default_profile(profile_name)
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
def raw_api(api_id: str, body: str, raw: bool, next_key: str):
    """Raw API 호출. (예: kiwoom api ka10001 '{"stk_cd":"005930"}')"""
    try:
        body_dict = json.loads(body)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON body: {e}")

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
            from .api_spec import get_description
            title = get_description(api_id)
            print_generic_table(data, title=title)

        if headers.get("cont-yn") == "Y":
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


def _describe_command(cmd: click.Command, path: str) -> dict:
    spec: dict = {
        "path": path,
        "help": (cmd.help or cmd.short_help or "").strip(),
        "arguments": [_param_spec(p) for p in cmd.params if isinstance(p, click.Argument)],
        "options": [_param_spec(p) for p in cmd.params if isinstance(p, click.Option)],
    }
    if isinstance(cmd, click.Group):
        spec["subcommands"] = [
            _describe_command(sub, f"{path} {name}")
            for name, sub in sorted(cmd.commands.items())
            if not sub.hidden
        ]
    return spec


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
def describe(command_path: tuple[str, ...]):
    """CLI 명령 구조 자기서술 — 경로/도움말/인자/옵션(타입·기본값·choices).

    에이전트가 도구 스키마를 파악할 때 사용합니다.

    \b
    예: kiwoom describe                  # 전체 트리
        kiwoom describe order buy -f json
    """
    cmd: click.Command = cli
    path = "kiwoom"
    for name in command_path:
        if not isinstance(cmd, click.Group) or name not in cmd.commands:
            raise click.ClickException(f"명령을 찾을 수 없습니다: {' '.join(command_path)}")
        cmd = cmd.commands[name]
        path += f" {name}"
    spec = _describe_command(cmd, path)
    if _get_format() == "json":
        envelope.emit(data=spec)
        return
    _render_describe(spec)


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
