"""Kiwoom CLI entry point."""

from __future__ import annotations

import json

import click
import httpx

from . import __version__, auth, config
from .client import KiwoomClient, KiwoomAPIError
from .commands.account import account
from .commands.dashboard import dashboard
from .commands.market import market
from .commands.order import order
from .commands.stock import stock
from .commands.stream import stream
from .commands.watch import watch
from .formatters import _get_format, _output_json, human, print_generic_table
from .output import console, err_console

# Exit codes
EXIT_OK = 0
EXIT_INPUT = 1   # Click default for bad args
EXIT_API = 2     # API or network error
EXIT_AUTH = 3    # Token missing or expired


class KiwoomGroup(click.Group):
    """Custom group that catches API/network errors globally."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except KiwoomAPIError as e:
            fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
            if fmt == "json":
                click.echo(json.dumps({"error": e.msg, "code": e.code}, ensure_ascii=False))
            else:
                console.print(f"[red]API 오류:[/] {e}")
            ctx.exit(EXIT_API)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                console.print("[red]인증 오류:[/] 토큰이 만료되었습니다. [dim]kiwoom auth login[/]")
                ctx.exit(EXIT_AUTH)
            else:
                console.print(f"[red]HTTP 오류:[/] {e.response.status_code}")
                ctx.exit(EXIT_API)
        except httpx.ConnectError:
            console.print("[red]연결 오류:[/] API 서버에 연결할 수 없습니다. 도메인을 확인하세요.")
            ctx.exit(EXIT_API)


@click.group(cls=KiwoomGroup)
@click.version_option(__version__, prog_name="kiwoom")
@click.option("-f", "--format", "output_format",
              type=click.Choice(["table", "json", "csv"]),
              default="table", help="출력 형식")
@click.option("-p", "--profile", default=None, help="사용할 프로필")
@click.option("--no-color", is_flag=True, help="색상 없이 출력")
@click.pass_context
def cli(ctx, output_format, profile, no_color):
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
def config_setup(profile: str, appkey: str, secretkey: str, domain: str, account: str):
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
    if "default_profile" not in cfg.get("general", {}):
        cfg.setdefault("general", {})["default_profile"] = profile
    cfg.pop("auth", None)
    config.save_config(cfg)
    console.print(f"[green]설정 완료![/] (프로필: {profile})")
    console.print("  App Key/Secret Key: [bold]OS 키체인에 저장됨[/]")
    console.print(f"  도메인: [bold]{config.DOMAINS[domain]}[/]")


@config_cmd.command("show")
@click.pass_context
def config_show(ctx):
    """현재 설정 확인."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    cfg = config.load_config()
    configured = config.is_configured(profile)
    profile_cfg = cfg.get("profiles", {}).get(profile, {})
    if _get_format() == "json":
        _output_json({
            "profile": profile,
            "config_file": str(config.CONFIG_FILE),
            "domain": profile_cfg.get("domain", "mock"),
            "configured": configured,
            "account": profile_cfg.get("account", ""),
        })
        return
    human(f"  프로필: [bold]{profile}[/]")
    human(f"  설정 파일: {config.CONFIG_FILE}")
    human(f"  도메인: {profile_cfg.get('domain', 'mock')}")
    human(f"  App Key: {'[dim]설정됨 (키체인)[/]' if configured else '(미설정)'}")
    human(f"  계좌번호: {profile_cfg.get('account', '(미설정)')}")
    human(f"  보안: [bold]{'OS 키체인 저장' if configured else '미설정'}[/]")


@config_cmd.command("set")
@click.argument("key", type=click.Choice(["domain", "account"]))
@click.argument("value")
@click.pass_context
def config_set(ctx, key: str, value: str):
    """프로필 설정 변경. (예: kiwoom config set domain prod)"""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    if key == "domain" and value not in ("prod", "mock"):
        console.print("[red]domain은 prod 또는 mock만 가능합니다.[/]")
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


@auth_cmd.command("login")
@click.pass_context
def auth_login(ctx):
    """접근토큰 발급."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    if not config.is_configured(profile):
        human("[red]설정이 필요합니다. 먼저 실행: kiwoom config setup[/]")
        raise SystemExit(1)
    with KiwoomClient() as c:
        try:
            token = c.issue_token()
            masked = token[:10] + "..." + token[-4:] if len(token) > 14 else token
            human("[green]토큰 발급 완료![/]")
            human(f"  토큰: {masked}")
            human("  저장 위치: [bold]키체인[/]")
        except KiwoomAPIError as e:
            human(f"[red]토큰 발급 실패:[/] {e}")


@auth_cmd.command("logout")
@click.pass_context
def auth_logout(ctx):
    """접근토큰 폐기."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    if not config.is_configured(profile):
        human("[red]설정이 필요합니다. 먼저 실행: kiwoom config setup[/]")
        raise SystemExit(1)
    with KiwoomClient() as c:
        try:
            c.revoke_token()
            human("[green]토큰 폐기 완료.[/]")
        except KiwoomAPIError as e:
            human(f"[red]토큰 폐기 실패:[/] {e}")


@auth_cmd.command("status")
@click.pass_context
def auth_status(ctx):
    """토큰 상태 확인."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    configured = config.is_configured(profile)
    has_token = configured and auth.load_token(profile=profile) is not None
    if _get_format() == "json":
        cfg = config.load_config()
        _output_json({
            "profile": profile,
            "domain": cfg.get("profiles", {}).get(profile, {}).get("domain", "mock"),
            "configured": configured,
            "has_token": has_token,
        })
        return
    if not configured:
        human("[yellow]설정 필요.[/] 'kiwoom config setup' 으로 설정하세요.")
        return
    human(f"  프로필: [bold]{profile}[/]")
    if has_token:
        human("[green]토큰 있음[/] [dim](키체인 저장됨)[/]")
    else:
        human("[yellow]토큰 없음.[/] 'kiwoom auth login' 으로 발급하세요.")


# ── Raw API ───────────────────────────────────────────

@cli.command("api")
@click.argument("api_id")
@click.argument("body", default="{}")
@click.option("--raw", is_flag=True, help="JSON 원본 출력")
def raw_api(api_id: str, body: str, raw: bool):
    """Raw API 호출. (예: kiwoom api ka10001 '{"stk_cd":"005930"}')"""
    try:
        body_dict = json.loads(body)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON body: {e}")

    with KiwoomClient() as c:
        data, headers = c.request(api_id, body_dict)
        if raw:
            console.print_json(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            from .api_spec import get_description
            title = get_description(api_id)
            print_generic_table(data, title=title)

        if headers.get("cont-yn") == "Y":
            err_console.print(f"\n[dim]연속조회 가능 (next-key: {headers.get('next-key', '')})[/]")


# ── Register subcommands ─────────────────────────────

cli.add_command(stock)
cli.add_command(account)
cli.add_command(order)
cli.add_command(market)
cli.add_command(stream)
cli.add_command(dashboard)
cli.add_command(watch)


if __name__ == "__main__":
    cli()
