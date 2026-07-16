# kiwoom-cli vs 키움증권 공식 CLI (kwcli)

키움증권은 공식 저장소 [Kiwoom-Securities/Kiwoom-REST-API](https://github.com/Kiwoom-Securities/Kiwoom-REST-API)에서
CLI(`kwcli`, 명령어 `kiwoomcli`)를 제공한다. 이 문서는 두 도구의 역량을
있는 그대로 비교한다.

> 기준: kwcli v0.1.1 / kiwoom-cli v2.4+ (feature/normalized-data 포함),
> 2026-07-17 작성. 공식 CLI는 빠르게 바뀔 수 있으므로 최신 상태는 저장소에서
> 직접 확인할 것.

## 역량 비교

| 역량 | 공식 kwcli | kiwoom-cli |
| --- | --- | --- |
| 출력 형식 | pandas DataFrame 출력만 | Rich 테이블 / **JSON envelope** / CSV (`-f`) |
| 기계가 읽는 계약 | 없음 (DataFrame repr 파싱 필요) | `{ok, schema, data, meta, error}` + 타입 있는 정규화 필드 + 안정적 error.code 32종 + exit code 0/1/2/3 |
| 시장 | 국내 주식만 | 국내 + **미국주식 29 API** (티커 자동 라우팅) |
| 실시간 스트리밍 | 없음 | WebSocket 19종, **NDJSON** + `--max-events/--duration/--until` 종료조건 |
| 녹화/히스토리 | 없음 | `--record` → `history list/query/export` (sqlite/csv) |
| 주문 안전장치 | 없음 | `--dry-run` / `order validate`(read-only 사전점검) / `--client-order-id` 멱등성 / 구조화된 CONFIRMATION_REQUIRED |
| 자기서술 | `spec search` (API 스펙 탐색) | `kiwoom describe -f json` (명령 트리+옵션 스키마) + [AGENTS.md](../AGENTS.md) 기계 계약 |
| 스크립팅 | exit code/stdout 계약 없음 | stdout 순수성(진행 메시지는 전부 stderr), `--fields` 투영, `jq` 파이프 전제 설계 |
| 요구 환경 | Python ≥3.13, pandas 의존 | Python ≥3.10, pandas 없음 (콜드 스타트 빠름) |
| 인증 UX | — | OS 키체인, 프롬프트 제로, 멀티 프로필, `KIWOOM_TOKEN`(CI/샌드박스) |

## 구체적 차이 하나로: litmus loop

에이전트가 "시세 확인 → 사전점검 → dry-run → 멱등키 주문 → 재시도 안전 확인
→ 미체결/잔고"를 **사람 개입 없이 stdout JSON과 exit code만으로** 완주할 수
있는가. kiwoom-cli는 이것을 실행 가능한 증명으로 제공한다:

- 모의투자 서버 대상 재현 스크립트: [benchmark/litmus.sh](../benchmark/litmus.sh)
  (`jq -e`로 매 단계 검증, 첫 실패에서 비0 exit)
- CI에서 항상 도는 네트워크 없는 버전:
  `tests/test_order.py::test_litmus_loop_json_driven`

DataFrame 출력만 있는 CLI에서는 이 루프의 어느 단계도 프로그램이 안전하게
분기할 수 없다 — 성공/실패 판정부터 repr 문자열 파싱이 된다. 특히 4~5단계
(멱등 재시도)는 해당 기능 자체가 없다.

## 공식 저장소가 더 잘하는 것

정직하게, 다음은 공식 쪽이 낫거나 공식만 가능한 영역이다:

- **1차 제공자 신뢰**: 키움증권이 직접 유지하므로 API 변경이 가장 먼저
  반영될 개연성이 높고, 장애/스펙 문의의 공식 창구가 있다.
- **Python SDK**: CLI 외에 라이브러리로 직접 임베드할 수 있는 공식 SDK를
  함께 제공한다. 파이썬 코드 안에서 쓰려면 그쪽이 자연스럽다.
- **Postman 컬렉션**: REST 엔드포인트를 GUI로 탐색·실험하기에 좋다.
- **표준 문서**: API 명세의 원본(canonical docs)은 공식 저장소/포털이다.
  kiwoom-cli의 스펙 해석이 갈리는 경우 공식 문서가 기준이다.

## 결론

- 파이썬 코드에 임베드하거나 공식 지원이 필요하면 → 공식 SDK/kwcli.
- 터미널에서 사람이 쓰거나, **AI 에이전트/스크립트가 안전하게 주문까지
  자동화**해야 하면 → kiwoom-cli. 위 표의 차이 대부분(envelope, 안전장치,
  스트리밍, 미국주식)이 이 사용례를 위해 존재한다.
