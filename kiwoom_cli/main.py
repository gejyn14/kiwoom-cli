"""Kiwoom CLI entry point."""

from __future__ import annotations

import json

import click
import httpx

from . import __version__, config
from .client import KiwoomClient, KiwoomAPIError
from .commands.account import account
from .commands.dashboard import dashboard
from .commands.market import market
from .commands.order import order
from .commands.stock import stock
from .commands.stream import stream
from .commands.watch import watch
from .formatters import print_generic_table
from .output import console

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

    # Auto-migrate plaintext credentials to encrypted store
    if config.store.is_initialized and config.migrate_from_plaintext():
        from .output import err_console
        err_console.print("[yellow]인증정보를 암호화된 키체인으로 이전했습니다.[/]")

    # Auto-migrate pre-profile config to profile-aware format
    if config.store.is_initialized and config.migrate_to_profiles():
        from .output import err_console
        err_console.print("[yellow]프로필 형식으로 마이그레이션 완료.[/]")

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
    password = click.prompt("시스템 비밀번호 (인증정보 암호화에 사용)", hide_input=True)
    if config.store.is_initialized:
        if not config.store.unlock(password):
            # Unlock failed — possibly old encryption format. Offer re-init.
            if click.confirm("비밀번호 검증 실패. 암호화 저장소를 재설정하시겠습니까?"):
                config.store.setup(password)
            else:
                raise SystemExit(1)
    else:
        config.store.setup(password)
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
    console.print("  App Key/Secret Key: [bold]암호화되어 키체인에 저장됨[/]")
    console.print(f"  도메인: [bold]{config.DOMAINS[domain]}[/]")


@config_cmd.command("show")
@click.pass_context
def config_show(ctx):
    """현재 설정 확인."""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    cfg = config.load_config()
    initialized = config.store.is_initialized
    profile_cfg = cfg.get("profiles", {}).get(profile, {})
    console.print(f"  프로필: [bold]{profile}[/]")
    console.print(f"  설정 파일: {config.CONFIG_FILE}")
    console.print(f"  도메인: {profile_cfg.get('domain', 'mock')}")
    console.print(f"  App Key: {'[dim]설정됨 (암호화)[/]' if initialized else '(미설정)'}")
    console.print(f"  계좌번호: {profile_cfg.get('account', '(미설정)')}")
    console.print(f"  보안: [bold]{'SecureStore 활성' if initialized else '미초기화'}[/]")


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
        console.print("[yellow]등록된 프로필이 없습니다.[/]")
        return
    console.print(f"  현재 프로필: [bold green]{default}[/]")
    console.print()
    for name, settings in profiles.items():
        marker = " [green]*[/]" if name == default else "  "
        domain = settings.get("domain", "mock")
        account = settings.get("account", "") or "(미설정)"
        console.print(f"  {marker} {name:15s} 도메인={domain}  계좌={account}")


# ── Auth ──────────────────────────────────────────────

@cli.group("auth")
def auth_cmd():
    """인증 (토큰 발급/폐기)."""
    pass


def _unlock_store() -> bool:
    """Prompt for password and unlock the secure store."""
    if not config.store.is_initialized:
        console.print("[red]설정이 필요합니다. 먼저 실행: kiwoom config setup[/]")
        return False
    password = click.prompt("비밀번호", hide_input=True)
    if not config.store.unlock(password):
        console.print("[red]비밀번호가 일치하지 않습니다.[/]")
        return False
    return True


@auth_cmd.command("login")
def auth_login():
    """접근토큰 발급 (비밀번호 확인 후 암호화된 인증정보 사용)."""
    if not _unlock_store():
        raise SystemExit(1)
    with KiwoomClient() as c:
        try:
            token = c.issue_token()
            masked = token[:10] + "..." + token[-4:] if len(token) > 14 else token
            console.print("[green]토큰 발급 완료![/]")
            console.print(f"  토큰: {masked}")
            console.print("  저장 위치: [bold]키체인[/]")
        except KiwoomAPIError as e:
            console.print(f"[red]토큰 발급 실패:[/] {e}")


@auth_cmd.command("logout")
def auth_logout():
    """접근토큰 폐기 (비밀번호 확인 필요)."""
    if not _unlock_store():
        raise SystemExit(1)
    with KiwoomClient() as c:
        try:
            c.revoke_token()
            console.print("[green]토큰 폐기 완료.[/]")
        except KiwoomAPIError as e:
            console.print(f"[red]토큰 폐기 실패:[/] {e}")


@auth_cmd.command("status")
@click.pass_context
def auth_status(ctx):
    """토큰 상태 확인."""
    if not config.store.is_initialized:
        console.print("[yellow]설정 필요.[/] 'kiwoom config setup' 으로 설정하세요.")
        return
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    import keyring as _kr
    has_token = _kr.get_password(config.KEYRING_SERVICE, f"{profile}:token") is not None
    console.print(f"  프로필: [bold]{profile}[/]")
    if has_token:
        console.print("[green]토큰 있음[/] [dim](키체인 저장됨)[/]")
    else:
        console.print("[yellow]토큰 없음.[/] 'kiwoom auth login' 으로 발급하세요.")


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
        try:
            data, headers = c.request(api_id, body_dict)
            if raw:
                console.print_json(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                from .api_spec import get_description
                title = get_description(api_id)
                print_generic_table(data, title=title)

            if headers.get("cont-yn") == "Y":
                console.print(f"\n[dim]연속조회 가능 (next-key: {headers.get('next-key', '')})[/]")
        except KiwoomAPIError as e:
            console.print(f"[red]API 오류:[/] {e}")


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
