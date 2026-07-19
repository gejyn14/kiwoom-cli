"""Tests for CLI commands using Click CliRunner."""

import json
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from kiwoom_cli import __version__
from kiwoom_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "키움증권" in result.output
    assert "stock" in result.output
    assert "account" in result.output
    assert "order" in result.output
    assert "market" in result.output
    assert "stream" in result.output
    assert "dashboard" in result.output


def test_stock_help(runner):
    result = runner.invoke(cli, ["stock", "--help"])
    assert result.exit_code == 0
    assert "info" in result.output
    assert "orderbook" in result.output
    assert "chart" in result.output
    assert "compare" in result.output


def test_config_show(runner):
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0


def test_config_show_with_profile(runner):
    result = runner.invoke(cli, ["-p", "test", "config", "show"])
    assert result.exit_code == 0
    assert "test" in result.output


def test_config_profiles(runner):
    result = runner.invoke(cli, ["config", "profiles"])
    assert result.exit_code == 0


def test_auth_status(runner):
    result = runner.invoke(cli, ["auth", "status"])
    assert result.exit_code == 0


def _mock_request(api_id, body=None, **kwargs):
    """Return canned API responses."""
    responses = {
        "ka10001": {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "-70000",
            "pred_pre": "-1000",
            "flu_rt": "-1.41",
            "trde_qty": "10000000",
            "return_code": 0,
        },
    }
    data = responses.get(api_id, {"return_code": 0})
    return data, {"cont-yn": "", "next-key": ""}


@patch("kiwoom_cli.commands.stock.KiwoomClient")
def test_stock_info_json(mock_cls, runner):
    mock_client = MagicMock()
    mock_client.request = _mock_request
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_cls.return_value = mock_client

    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["ok"] is True
    assert parsed["data"]["name"] == "삼성전자"          # 정규화된 필드
    assert parsed["data"]["raw"]["stk_nm"] == "삼성전자"  # 원본 보존


@patch("kiwoom_cli.commands.stock.KiwoomClient")
def test_stock_info_csv(mock_cls, runner):
    mock_client = MagicMock()
    mock_client.request = _mock_request
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_cls.return_value = mock_client

    result = runner.invoke(cli, ["-f", "csv", "stock", "info", "005930"])
    assert result.exit_code == 0
    assert "stk_cd" in result.output
    assert "005930" in result.output


@patch("kiwoom_cli.commands.stock.KiwoomClient")
def test_stock_price(mock_cls, runner):
    mock_client = MagicMock()
    mock_client.request = _mock_request
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_cls.return_value = mock_client

    result = runner.invoke(cli, ["stock", "price", "005930"])
    assert result.exit_code == 0
    assert "삼성전자" in result.output


def test_stream_types(runner):
    result = runner.invoke(cli, ["stream", "types"])
    assert result.exit_code == 0
    assert "주식체결" in result.output
    assert "0B" in result.output


def test_api_error_handling(runner):
    """Test that API errors produce exit code 2."""
    from kiwoom_cli.client import KiwoomAPIError

    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.request.side_effect = KiwoomAPIError(-1, "테스트 오류")
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = mock_client

        result = runner.invoke(cli, ["stock", "info", "005930"])
        assert result.exit_code == 2
        assert "오류" in result.output


def test_api_error_csv_mode_stdout_is_clean(runner):
    """-f csv에서 API 오류가 나면 stdout은 비어 있고 오류는 stderr로 가야 한다.

    KiwoomGroup.invoke의 오류 핸들러는 이전에 json 모드만 확인하고 그 외에는
    (csv 포함) console.print로 stdout에 Rich 서식 오류 문구를 찍었다 —
    `kiwoom -f csv ... > out.csv` 가 오류 시 CSV 파일을 한국어 산문으로 오염시켰다.
    """
    from kiwoom_cli.client import KiwoomAPIError

    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.request.side_effect = KiwoomAPIError(-1, "테스트 오류")
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = mock_client

        result = runner.invoke(cli, ["-f", "csv", "stock", "info", "005930"])
        assert result.exit_code == 2
        assert result.stdout == ""
        assert "오류" in result.stderr


# Note: Order command tests moved to tests/test_order.py for strict coverage.


def test_config_profiles_command(runner):
    result = runner.invoke(cli, ["config", "profiles"])
    assert result.exit_code == 0


def test_profile_flag_with_show(runner):
    result = runner.invoke(cli, ["-p", "test", "config", "show"])
    assert result.exit_code == 0
    assert "test" in result.output


# ── Exit-code contract ───────────────────────────────
# 0=성공, 1=입력오류, 2=API오류, 3=인증필요. Click's UsageError defaults to
# exit code 2, which would collide with EXIT_API — main.py overrides it to 1.


def test_invalid_option_value_exits_1(runner):
    result = runner.invoke(cli, ["order", "buy", "005930", "10", "--type", "bogus", "--confirm"])
    assert result.exit_code == 1


def test_missing_argument_exits_1(runner):
    result = runner.invoke(cli, ["stock", "info"])
    assert result.exit_code == 1


def test_unknown_command_exits_1(runner):
    result = runner.invoke(cli, ["nonexistent-command"])
    assert result.exit_code == 1


def test_invalid_json_body_exits_1(runner):
    result = runner.invoke(cli, ["api", "ka10001", "not-json"])
    assert result.exit_code == 1


# ── Unhandled exceptions → envelope errors (Task 19 / 감사 발견 N9-N11) ──
# 아래 3건은 수정 전에는 KiwoomGroup.invoke의 핸들러 목록에 없는 예외가
# escape해 traceback + 빈 stdout + exit 1로 종료됐다 — 에이전트가 "인자 오류"로
# 오인하게 된다.


def test_unknown_api_id_returns_invalid_api_envelope(runner, monkeypatch):
    """잘못된 api_id는 client.py의 get_url()이 ValueError를 던져 escape했다.

    (토큰이 있어야 KiwoomAuthError보다 먼저 get_url()에 도달한다.)
    """
    monkeypatch.setenv("KIWOOM_TOKEN", "test-token")

    result = runner.invoke(cli, ["-f", "json", "api", "bogus999", "{}"])

    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_API"


def test_corrupted_config_toml_returns_not_configured_envelope(runner, monkeypatch, tmp_path):
    """손상된 config.toml은 루트 콜백(resolve_profile -> load_config)에서
    TOMLDecodeError로 죽어 kiwoom config show조차 불가능했다."""
    from kiwoom_cli import config

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("this is not [ valid toml", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)

    result = runner.invoke(cli, ["-f", "json", "config", "show"])

    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "NOT_CONFIGURED"
    assert str(cfg_file) in doc["error"]["message"]


def test_non_json_response_returns_upstream_error_envelope(runner, monkeypatch, httpx_mock):
    """HTTP 200 유지보수 페이지처럼 응답 바디가 JSON이 아니면 resp.json()이
    json.JSONDecodeError를 던져 escape했다."""
    from kiwoom_cli import client as client_mod

    monkeypatch.setattr(client_mod.config, "get_domain", lambda profile=None: "https://mock.test")
    monkeypatch.setattr(client_mod.auth, "load_token", lambda profile=None: "test-token")
    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        text="<html>점검 중입니다</html>",
        status_code=200,
    )

    result = runner.invoke(cli, ["-f", "json", "api", "ka10001", "{}"])

    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert result.exit_code == 2
    doc = json.loads(result.output)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "UPSTREAM_ERROR"
