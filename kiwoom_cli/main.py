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
@click.option("--no-color", is_flag=True, help="색상 없이 출력")
@click.pass_context
def cli(ctx, output_format, no_color):
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

    # Auto-migrate plaintext credentials to keychain
    if config.migrate_from_config_file():
        from .output import err_console
        err_console.print("[yellow]appkey/secretkey를 키체인으로 이전했습니다. config.toml에서 제거됨.[/]")

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
@click.option("--appkey", prompt="App Key", help="키움 API App Key")
@click.option("--secretkey", prompt="Secret Key", hide_input=True, help="키움 API Secret Key")
@click.option("--domain", type=click.Choice(["prod", "mock"]), default="mock", help="도메인 (prod: 실거래, mock: 모의투자)")
@click.option("--account", default="", help="기본 계좌번호")
def config_setup(appkey: str, secretkey: str, domain: str, account: str):
    """초기 설정 (App Key, Secret Key, 도메인)."""
    config.set_appkey(appkey)
    config.set_secretkey(secretkey)
    cfg = config.load_config()
    cfg.setdefault("general", {})["domain"] = domain
    if account:
        cfg["general"]["account"] = account
    cfg.pop("auth", None)  # Remove plaintext credentials if present
    config.save_config(cfg)
    console.print("[green]설정 완료![/]")
    console.print("  App Key/Secret Key: [bold]키체인에 저장됨[/]")
    console.print(f"  도메인: [bold]{config.DOMAINS[domain]}[/]")


@config_cmd.command("show")
def config_show():
    """현재 설정 확인."""
    cfg = config.load_config()
    ak = config.get_appkey()
    console.print(f"  설정 파일: {config.CONFIG_FILE}")
    console.print(f"  도메인: {cfg.get('general', {}).get('domain', 'mock')}")
    console.print(f"  App Key: {'***' + ak[-4:] if ak else '(미설정)'} [dim](키체인)[/]")
    console.print(f"  계좌번호: {cfg.get('general', {}).get('account', '(미설정)')}")
    console.print(f"  토큰: {'있음 [dim](키체인)[/]' if auth.load_token() else '없음'}")


@config_cmd.command("domain")
@click.argument("domain", type=click.Choice(["prod", "mock"]))
def config_domain(domain: str):
    """도메인 변경 (prod/mock)."""
    cfg = config.load_config()
    cfg.setdefault("general", {})["domain"] = domain
    config.save_config(cfg)
    console.print(f"[green]도메인 변경:[/] {config.DOMAINS[domain]}")


# ── Auth ──────────────────────────────────────────────

@cli.group("auth")
def auth_cmd():
    """인증 (토큰 발급/폐기)."""
    pass


def _verify_system_password() -> bool:
    """Verify OS login password before accessing credentials.

    macOS: dscl, Windows: LogonUser, Linux: PAM (su fallback).
    """
    import os
    import subprocess
    import sys as _sys
    password = click.prompt("시스템 비밀번호", hide_input=True)
    user = os.environ.get("USER") or os.getlogin()
    if _sys.platform == "darwin":
        result = subprocess.run(
            ["dscl", "/Local/Default", "-authonly", user, password],
            capture_output=True,
        )
        return result.returncode == 0
    if _sys.platform == "win32":
        import ctypes
        advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]
        handle = ctypes.c_void_p()
        ok = advapi32.LogonUserW(
            user, None, password,
            2,  # LOGON32_LOGON_INTERACTIVE
            0,  # LOGON32_PROVIDER_DEFAULT
            ctypes.byref(handle),
        )
        if ok:
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
        return bool(ok)
    # Linux: use PAM via su
    result = subprocess.run(
        ["su", user, "-c", "true"],
        input=password + "\n",
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


@auth_cmd.command("login")
def auth_login():
    """접근토큰 발급 (시스템 비밀번호 확인 후 키체인에서 인증정보 사용)."""
    if not _verify_system_password():
        console.print("[red]비밀번호가 일치하지 않습니다.[/]")
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
    """접근토큰 폐기."""
    with KiwoomClient() as c:
        try:
            c.revoke_token()
            console.print("[green]토큰 폐기 완료.[/]")
        except KiwoomAPIError as e:
            console.print(f"[red]토큰 폐기 실패:[/] {e}")


@auth_cmd.command("status")
def auth_status():
    """토큰 상태 확인."""
    token = auth.load_token()
    if token:
        masked = token[:10] + "..." + token[-4:] if len(token) > 14 else token
        console.print(f"[green]토큰 있음:[/] {masked}")
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
