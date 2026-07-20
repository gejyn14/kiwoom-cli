"""HTTP client for Kiwoom REST API.

Handles authentication headers, pagination, and error handling.
"""

from __future__ import annotations

import json
import os
from typing import Any

import click
import httpx

from . import auth, config
from .api_spec import get_url
from .output import err_console

CONTENT_TYPE = "application/json;charset=UTF-8"


class KiwoomAPIError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


class KiwoomAuthError(Exception):
    """No access token available — the caller must authenticate first."""


class KiwoomClient:
    """Synchronous client for the Kiwoom REST API."""

    def __init__(self, domain: str | None = None, token: str | None = None, profile: str | None = None):
        if profile is None:
            ctx = click.get_current_context(silent=True)
            if ctx and ctx.obj:
                # 루트가 해석해 둔 값을 우선 읽는다. 없으면(루트 콜백을 거치지
                # 않는 직접 사용) 원시 플래그로 폴백한다.
                profile = ctx.obj.get("resolved_profile") or ctx.obj.get("profile")
        self.profile = profile
        self.domain = domain or config.get_domain(profile=profile)
        self.token = token or auth.load_token(profile=profile)
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

    def _should_spin(self) -> bool:
        """Show spinner only for table format on a real terminal."""
        if not err_console.is_terminal:
            return False
        ctx = click.get_current_context(silent=True)
        if ctx and ctx.obj and ctx.obj.get("format") != "table":
            return False
        return True

    def _request_once(
        self,
        api_id: str,
        body: dict[str, Any] | None = None,
        *,
        cont_yn: str = "",
        next_key: str = "",
        record_cont: bool = True,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Make a single API request. Returns (body_json, response_headers)."""
        if not self.token:
            raise KiwoomAuthError()
        url_path = get_url(api_id)
        headers = self._headers(api_id, cont_yn, next_key)
        if self._should_spin():
            with err_console.status("[dim]조회 중...[/]", spinner="dots"):
                resp = self._http.post(url_path, headers=headers, json=body or {})
        else:
            resp = self._http.post(url_path, headers=headers, json=body or {})
        resp.raise_for_status()
        try:
            data = resp.json()
        except json.JSONDecodeError:
            # HTTP 200이면서 바디가 JSON이 아닌 경우(예: 점검 페이지) — raise_for_status()를
            # 통과하므로 여기서 잡지 않으면 KiwoomGroup.invoke의 핸들러 목록을 escape한다.
            raise KiwoomAPIError(1999, f"API 응답이 JSON이 아닙니다 (HTTP {resp.status_code})")

        rc = data.get("return_code")
        if rc is not None and rc != 0:
            raise KiwoomAPIError(rc, data.get("return_msg", "Unknown error"))

        resp_headers = {
            "cont-yn": resp.headers.get("cont-yn", ""),
            "next-key": resp.headers.get("next-key", ""),
        }

        # 연속조회 커서를 Click 컨텍스트에 보관 → json envelope의 meta.cont로 노출
        # (라이브러리로 쓰일 때는 컨텍스트가 없으므로 조용히 건너뜀)
        # record_cont=False: 보조 호출(internal)은 본 조회의 커서 기록을 덮어쓰지 않는다.
        # ctx.obj["suppress_cont"]: _mutation.suppress_pagination()이 변이 요청
        # 직전에 세팅한다 — 업스트림이 실제로 cont-yn: Y를 보내더라도 meta.cont는
        # 항상 None으로 고정한다. 변이(주문 전송·환전 신청 등) 응답에 살아있는
        # meta.cont는 "--next-key로 이어서 실행"을 유도하는데, 변이에서 그 반복은
        # 진짜 동작을 한 번 더 실행하는 것이다. suppress_pagination()이 all_pages/
        # next_key를 되돌리는 시점(요청 전)과 달리 이 판단은 응답을 받은 뒤에만
        # 가능하므로 suppress_pagination() 내부가 아니라 여기서 처리한다.
        if record_cont:
            ctx = click.get_current_context(silent=True)
            if ctx is not None and isinstance(ctx.obj, dict):
                if ctx.obj.get("suppress_cont"):
                    ctx.obj["last_cont"] = None
                elif resp_headers["cont-yn"] == "Y" and resp_headers["next-key"]:
                    ctx.obj["last_cont"] = {"next_key": resp_headers["next-key"]}
                else:
                    ctx.obj["last_cont"] = None

        return data, resp_headers

    _ALL_PAGES_CAP = 50

    def request(
        self,
        api_id: str,
        body: dict[str, Any] | None = None,
        *,
        cont_yn: str = "",
        next_key: str = "",
        internal: bool = False,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """단일 요청 + 전역 페이지네이션 플래그 처리.

        --next-key: 명령의 첫 API 요청에만 커서를 주입한다 (소비형).
        --all-pages: cont-yn이 끝날 때까지 반복, 리스트 필드를 병합한다.
        internal=True: 보조 호출(예: 미국 거래소 자동판별)로 표시 —
        전역 --next-key/--all-pages를 적용하지 않는다 (커서는 본 조회가 소비).
        """
        if internal:
            return self._request_once(
                api_id, body, cont_yn=cont_yn, next_key=next_key, record_cont=False
            )
        ctx = click.get_current_context(silent=True)
        obj = ctx.obj if ctx is not None and isinstance(ctx.obj, dict) else None
        if obj and not next_key and obj.get("next_key"):
            next_key = obj.pop("next_key")
            cont_yn = "Y"
        data, headers = self._request_once(api_id, body, cont_yn=cont_yn, next_key=next_key)
        if not (obj and obj.get("all_pages")):
            return data, headers
        pages = 1
        while headers.get("cont-yn") == "Y" and headers.get("next-key") and pages < self._ALL_PAGES_CAP:
            page, headers = self._request_once(api_id, body, cont_yn="Y", next_key=headers["next-key"])
            for k, v in page.items():
                if isinstance(v, list) and isinstance(data.get(k), list):
                    data[k].extend(v)
            pages += 1
        if headers.get("cont-yn") == "Y":
            err_console.print(f"[dim]--all-pages 상한({self._ALL_PAGES_CAP}페이지) 도달 — meta.cont로 계속 조회 가능[/]")
        return data, headers

    def issue_token(self, appkey: str | None = None, secretkey: str | None = None) -> str:
        """Issue an access token via au10001."""
        ak = appkey or config.get_appkey(profile=self.profile)
        sk = secretkey or config.get_secretkey(profile=self.profile)
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
        try:
            data = resp.json()
        except json.JSONDecodeError:
            # _request_once()와 동일한 실패 모드 — HTTP 200 + 비-JSON 바디.
            raise KiwoomAPIError(1999, f"API 응답이 JSON이 아닙니다 (HTTP {resp.status_code})")

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
            auth.save_token(token, profile=self.profile)
            self.token = token
        return token

    def revoke_token(self, force: bool = False) -> dict[str, Any]:
        """Revoke the current access token via au10002.

        어느 토큰을 폐기했고 키체인 항목을 지웠는지를 돌려준다
        (`{"revoked": bool, "token_source": "env"|"keychain",
        "keychain_token_deleted": bool}`).

        force=True는 상단 폐기가 실패해도 로컬 정리를 진행한다(서버 도달 불가로
        영영 정리를 못 하는 상황의 탈출구). 이때도 revoked를 True로 만들지
        않는다 — 확인하지 않은 것을 성공이라 보고하는 것이 애초의 결함이었다.

        auth.load_token은 KIWOOM_TOKEN을 키체인보다 먼저 반환하므로, env 토큰을
        폐기해 놓고 키체인의 {profile}:token을 지우면 **폐기한 적 없는 다른 살아
        있는 토큰**을 없애 영영 폐기 불가능하게 만든다. 그래서 키체인 항목은
        그것이 방금 폐기한 바로 그 토큰일 때만 지운다.
        """
        ak = config.get_appkey(profile=self.profile)
        sk = config.get_secretkey(profile=self.profile)
        env_token = os.environ.get("KIWOOM_TOKEN")
        token = self.token or auth.load_token(profile=self.profile)
        if not token:
            raise click.ClickException("No token to revoke.")

        resp = self._http.post(
            "/oauth2/revoke",
            headers={"content-type": CONTENT_TYPE, "api-id": "au10002"},
            json={"appkey": ak, "secretkey": sk, "token": token},
        )
        revoked = True
        try:
            # issue_token과 같은 확인. 종전에는 응답을 이름에 묶지도 않아
            # HTTP 4xx/5xx와 return_code 8015/8016이 전부 성공으로 보고됐고,
            # 그 뒤 로컬 토큰까지 지워 재폐기를 불가능하게 만들었다.
            resp.raise_for_status()
            data = resp.json()
            rc = data.get("return_code")
            if rc is not None and str(rc) != "0":
                raise KiwoomAPIError(rc, data.get("return_msg", "토큰 폐기 실패"))
        except (httpx.HTTPError, KiwoomAPIError):
            if not force:
                raise
            revoked = False

        from_env = bool(env_token) and token == env_token
        # 키체인이 방금 폐기한 토큰을 들고 있으면 출처와 무관하게 지운다
        # (죽은 토큰을 남기면 auth status가 유효한 것처럼 보고한다).
        keychain_token = auth.load_keychain_token(profile=self.profile)
        delete_keychain = keychain_token == token or not from_env
        if delete_keychain:
            auth.delete_token(profile=self.profile)
        self.token = None
        return {
            "revoked": revoked,
            "token_source": "env" if from_env else "keychain",
            "keychain_token_deleted": bool(delete_keychain and keychain_token is not None),
        }
