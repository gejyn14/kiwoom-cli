"""HTTP client for Kiwoom REST API.

Handles authentication headers, pagination, and error handling.
"""

from __future__ import annotations

from typing import Any

import click
import httpx
from rich.console import Console

from . import auth, config
from .api_spec import get_url

console = Console(stderr=True)

CONTENT_TYPE = "application/json;charset=UTF-8"


class KiwoomAPIError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


class KiwoomClient:
    """Synchronous client for the Kiwoom REST API."""

    def __init__(self, domain: str | None = None, token: str | None = None):
        self.domain = domain or config.get_domain()
        self.token = token or auth.load_token()
        self._http = httpx.Client(
            base_url=self.domain,
            timeout=30.0,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _headers(self, api_id: str, cont_yn: str = "", next_key: str = "") -> dict:
        h = {
            "content-type": CONTENT_TYPE,
            "api-id": api_id,
        }
        if self.token:
            h["authorization"] = f"Bearer {self.token}"
        if cont_yn:
            h["cont-yn"] = cont_yn
        if next_key:
            h["next-key"] = next_key
        return h

    def request(
        self,
        api_id: str,
        body: dict[str, Any] | None = None,
        *,
        cont_yn: str = "",
        next_key: str = "",
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Make a single API request. Returns (body_json, response_headers)."""
        url_path = get_url(api_id)
        headers = self._headers(api_id, cont_yn, next_key)
        resp = self._http.post(url_path, headers=headers, json=body or {})
        resp.raise_for_status()
        data = resp.json()

        rc = data.get("return_code")
        if rc is not None and rc != 0:
            raise KiwoomAPIError(rc, data.get("return_msg", "Unknown error"))

        resp_headers = {
            "cont-yn": resp.headers.get("cont-yn", ""),
            "next-key": resp.headers.get("next-key", ""),
        }
        return data, resp_headers

    def request_all(
        self,
        api_id: str,
        body: dict[str, Any] | None = None,
        *,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Auto-paginate through cont-yn/next-key. Returns list of all response bodies."""
        results = []
        cont_yn = ""
        next_key = ""

        for _ in range(max_pages):
            data, headers = self.request(
                api_id, body, cont_yn=cont_yn, next_key=next_key
            )
            results.append(data)

            if headers.get("cont-yn") == "Y" and headers.get("next-key"):
                cont_yn = headers["cont-yn"]
                next_key = headers["next-key"]
            else:
                break

        return results

    def issue_token(self, appkey: str | None = None, secretkey: str | None = None) -> str:
        """Issue an access token via au10001."""
        ak = appkey or config.get_appkey()
        sk = secretkey or config.get_secretkey()
        if not ak or not sk:
            raise click.ClickException(
                "appkey/secretkey not set. Run: kiwoom config setup"
            )

        resp = self._http.post(
            "/oauth2/token",
            headers={"content-type": CONTENT_TYPE, "api-id": "au10001"},
            json={
                "grant_type": "client_credentials",
                "appkey": ak,
                "secretkey": sk,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        rc = data.get("return_code")
        if rc is not None and rc != 0:
            raise KiwoomAPIError(rc, data.get("return_msg", "Token issue failed"))

        token = data.get("token", "")
        if not token:
            # Some responses put it differently
            for k in ("access_token", "token"):
                if data.get(k):
                    token = data[k]
                    break

        if token:
            auth.save_token(token)
            self.token = token
        return token

    def revoke_token(self) -> None:
        """Revoke the current access token via au10002."""
        ak = config.get_appkey()
        sk = config.get_secretkey()
        token = self.token or auth.load_token()
        if not token:
            raise click.ClickException("No token to revoke.")

        self._http.post(
            "/oauth2/revoke",
            headers={"content-type": CONTENT_TYPE, "api-id": "au10002"},
            json={"appkey": ak, "secretkey": sk, "token": token},
        )
        auth.delete_token()
        self.token = None
