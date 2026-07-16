"""Stdout purity tests.

"stdout carries data; stderr carries everything human-facing."
In json mode, stdout must be exactly one parseable JSON document —
previews, confirm prompts, hints, and banners must not leak into it.

Note: Click 8.2+ removed CliRunner(mix_stderr=False); streams are
separated by default and exposed as result.stdout / result.stderr.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from kiwoom_cli.client import KiwoomAPIError
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient

# Every module that instantiates KiwoomClient for the commands under test.
CLIENT_PATCH_TARGETS = [
    "kiwoom_cli.main.KiwoomClient",
    "kiwoom_cli.commands.stock.KiwoomClient",
    "kiwoom_cli.commands.account.KiwoomClient",
    "kiwoom_cli.commands.order.KiwoomClient",
    "kiwoom_cli.commands.us.order_ops.KiwoomClient",
]


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_client(monkeypatch):
    """Inject one FakeKiwoomClient into all command modules."""
    fake = FakeKiwoomClient()
    for target in CLIENT_PATCH_TARGETS:
        monkeypatch.setattr(target, lambda *args, **kwargs: fake)
    return fake


PURE_COMMANDS = [
    ["stock", "info", "005930"],
    ["account", "balance"],
    ["order", "buy", "005930", "1", "--price", "70000", "--type", "limit", "--confirm"],
    ["order", "cancel", "001", "005930", "--confirm"],
    ["api", "ka10001", '{"stk_cd":"005930"}'],
    ["auth", "status"],
    ["config", "show"],
]


@pytest.mark.parametrize("argv", PURE_COMMANDS, ids=lambda a: " ".join(a))
def test_json_stdout_is_single_document(runner, fake_client, argv):
    """-f json: stdout parses as exactly one JSON document."""
    result = runner.invoke(cli, ["-f", "json", *argv])
    assert result.exit_code == 0, result.output
    json.loads(result.stdout)


def test_json_error_path_emits_json_error(runner, monkeypatch):
    """-f json + KiwoomAPIError: stdout is a JSON error document, exit code 2."""
    fake = FakeKiwoomClient()

    def _raise(*args, **kwargs):
        raise KiwoomAPIError(-1, "테스트 오류")

    fake.request = _raise
    monkeypatch.setattr(
        "kiwoom_cli.commands.stock.KiwoomClient",
        lambda *args, **kwargs: fake,
    )

    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 2
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["error"]["upstream_code"] == -1
    assert doc["error"]["message"] == "테스트 오류"
    assert isinstance(doc["error"]["code"], str)
