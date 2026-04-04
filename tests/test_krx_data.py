"""Tests for KRX stock list fetching and caching."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from kiwoom_cli.krx_data import get_stock_list, _load_cache, _save_cache, CACHE_TTL
from kiwoom_cli.main import cli


FAKE_STOCKS = [
    {"stk_cd": "005930", "stk_nm": "삼성전자", "market": "KOSPI"},
    {"stk_cd": "000660", "stk_nm": "SK하이닉스", "market": "KOSPI"},
    {"stk_cd": "035420", "stk_nm": "NAVER", "market": "KOSPI"},
]


@pytest.fixture
def runner():
    return CliRunner()


# ── Cache tests ──────────────────────────────────────────────


def test_save_and_load_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.krx_data.CACHE_DIR", tmp_path)
    monkeypatch.setattr("kiwoom_cli.config.CACHE_DIR", tmp_path)

    _save_cache("KOSPI", FAKE_STOCKS)

    loaded = _load_cache("KOSPI")
    assert loaded == FAKE_STOCKS


def test_cache_expired(tmp_path, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.krx_data.CACHE_DIR", tmp_path)
    monkeypatch.setattr("kiwoom_cli.config.CACHE_DIR", tmp_path)

    expired = datetime.now() - timedelta(hours=25)
    payload = {"fetched_at": expired.isoformat(), "data": FAKE_STOCKS}
    cache_file = tmp_path / "stocks_KOSPI.json"
    cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert _load_cache("KOSPI") is None


def test_cache_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.krx_data.CACHE_DIR", tmp_path)

    cache_file = tmp_path / "stocks_KOSPI.json"
    cache_file.write_text("not json", encoding="utf-8")

    assert _load_cache("KOSPI") is None


def test_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.krx_data.CACHE_DIR", tmp_path)
    assert _load_cache("KOSPI") is None


# ── get_stock_list tests ─────────────────────────────────────


@patch("kiwoom_cli.krx_data._fetch_stocks", return_value=FAKE_STOCKS)
def test_get_stock_list_fetches_on_miss(mock_fetch, tmp_path, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.krx_data.CACHE_DIR", tmp_path)
    monkeypatch.setattr("kiwoom_cli.config.CACHE_DIR", tmp_path)

    result = get_stock_list("KOSPI")
    assert result == FAKE_STOCKS
    mock_fetch.assert_called_once_with("KOSPI")


@patch("kiwoom_cli.krx_data._fetch_stocks", return_value=FAKE_STOCKS)
def test_get_stock_list_uses_cache(mock_fetch, tmp_path, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.krx_data.CACHE_DIR", tmp_path)
    monkeypatch.setattr("kiwoom_cli.config.CACHE_DIR", tmp_path)

    _save_cache("KOSPI", FAKE_STOCKS)

    result = get_stock_list("KOSPI")
    assert result == FAKE_STOCKS
    mock_fetch.assert_not_called()


@patch("kiwoom_cli.krx_data._fetch_stocks", return_value=FAKE_STOCKS)
def test_get_stock_list_refresh_ignores_cache(mock_fetch, tmp_path, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.krx_data.CACHE_DIR", tmp_path)
    monkeypatch.setattr("kiwoom_cli.config.CACHE_DIR", tmp_path)

    _save_cache("KOSPI", FAKE_STOCKS)

    result = get_stock_list("KOSPI", refresh=True)
    assert result == FAKE_STOCKS
    mock_fetch.assert_called_once_with("KOSPI")


# ── CLI command tests ────────────────────────────────────────


@patch("kiwoom_cli.krx_data.get_stock_list", return_value=FAKE_STOCKS)
def test_stock_list_table(mock_get, runner):
    result = runner.invoke(cli, ["stock", "list"])
    assert result.exit_code == 0
    assert "3개" in result.output
    assert "삼성전자" in result.output
    assert "SK하이닉스" in result.output


@patch("kiwoom_cli.krx_data.get_stock_list", return_value=FAKE_STOCKS)
def test_stock_list_json(mock_get, runner):
    result = runner.invoke(cli, ["-f", "json", "stock", "list"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["total"] == 3
    assert len(parsed["stocks"]) == 3


@patch("kiwoom_cli.krx_data.get_stock_list", return_value=FAKE_STOCKS)
def test_stock_list_search(mock_get, runner):
    result = runner.invoke(cli, ["stock", "list", "--search", "삼성"])
    assert result.exit_code == 0
    assert "삼성전자" in result.output
    assert "SK하이닉스" not in result.output
    assert "1개" in result.output


@patch("kiwoom_cli.krx_data.get_stock_list", return_value=FAKE_STOCKS)
def test_stock_list_search_by_code(mock_get, runner):
    result = runner.invoke(cli, ["stock", "list", "--search", "005930"])
    assert result.exit_code == 0
    assert "삼성전자" in result.output
    assert "1개" in result.output


@patch("kiwoom_cli.krx_data.get_stock_list", return_value=FAKE_STOCKS)
def test_stock_list_csv(mock_get, runner):
    result = runner.invoke(cli, ["-f", "csv", "stock", "list"])
    assert result.exit_code == 0
    assert "005930" in result.output


@patch("kiwoom_cli.krx_data.get_stock_list", return_value=FAKE_STOCKS)
def test_stock_list_market_option(mock_get, runner):
    result = runner.invoke(cli, ["stock", "list", "--market", "kospi"])
    assert result.exit_code == 0
    mock_get.assert_called_once_with("KOSPI", refresh=False)


@patch("kiwoom_cli.krx_data.get_stock_list", return_value=FAKE_STOCKS)
def test_stock_list_refresh(mock_get, runner):
    result = runner.invoke(cli, ["stock", "list", "--refresh"])
    assert result.exit_code == 0
    mock_get.assert_called_once_with("ALL", refresh=True)
