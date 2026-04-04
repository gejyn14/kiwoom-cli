"""Tests for CLI commands using Click CliRunner."""

import json
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.5.0" in result.output


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
    assert parsed["stk_nm"] == "삼성전자"


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
