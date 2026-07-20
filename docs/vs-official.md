# kiwoom-cli vs 키움증권 공식 CLI (kwcli)

키움증권은 공식 저장소 [Kiwoom-Securities/Kiwoom-REST-API](https://github.com/Kiwoom-Securities/Kiwoom-REST-API)에서
CLI(`kwcli`, 명령어 `kiwoomcli`)를 제공한다. 이 문서는 두 도구의 역량을
있는 그대로 비교한다.

> 기준: kwcli v0.1.1 (PyPI 배포 메타데이터 기준, 2026-07-09 업로드 — 2026-07-20
> 재확인 시 변동 없음) / kiwoom-cli v2.14.0. 2026-07-17 작성, 2026-07-20 갱신.
> 공식 CLI는 빠르게 바뀔 수 있으므로 최신 상태는
> [PyPI](https://pypi.org/project/kwcli/)와 저장소에서 직접 확인할 것.

## 역량 비교

| 역량 | 공식 kwcli | kiwoom-cli |
| --- | --- | --- |
| 출력 형식 | pretty / json / jsonl / yaml (`--format`) | Rich 테이블 / JSON / CSV (`-f`) |
| 기계가 읽는 계약 | JSON 출력은 있으나 응답 envelope·오류 코드·exit code **계약이 문서화되어 있지 않음** | `{ok, schema, data, meta, error}` envelope v1 + 타입 있는 정규화 필드 + 안정적 error.code 32종(retryable 포함) + exit code 0/1/2/3 계약 ([AGENTS.md](../AGENTS.md)) |
| 시장 | 국내 주식만 | 국내 + **미국주식 29 API** (티커 자동 라우팅, 원화+달러 통합 잔고) |
| 실시간 스트리밍 | 있음: `--count`/`--duration`, 복수 종목, `--output file.jsonl` 녹화, `--named` 필드명 | WebSocket 19종, 이벤트당 envelope 한 줄(NDJSON) + `--max-events`/`--duration`/`--until`(절대시각) + 오류도 envelope + exit code 계약 |
| 녹화/히스토리 | 스트림 파일 녹화(`--output`)까지 | `--record` 녹화 → **`history list/query/export`** (sqlite/csv/parquet) 조회·내보내기 도구 |
| 주문 안전장치 | 미리보기 기본값(`--confirm` 없으면 미전송) + 가격 규칙 사전검증 | `--dry-run`(전송 body 그대로 출력) / **`order validate`**(잔고·장운영 실조회 read-only 사전점검) / **`--client-order-id` 멱등성**(재시도 중복주문 방지) / json 모드 구조화된 CONFIRMATION_REQUIRED |
| 계좌번호 마스킹 | 전 출력 형식에서 계좌 식별자 마스킹 | 없음 (로드맵) |
| 자기서술 | `spec search/show/groups/apis` (번들 스펙, 네트워크 불필요), `-h`에 OpenAPI 매핑 | `kiwoom describe -f json` (명령 트리+옵션 스키마) + [AGENTS.md](../AGENTS.md) 기계 계약 |
| 스크립팅 | json 한 줄 출력은 에이전트 파싱 가능. exit code·stdout 순수성 계약은 미문서화 | stdout 순수성(진행 메시지는 전부 stderr), `--fields` 투영, `jq` 파이프 전제 설계 |
| 요구 환경 | Python ≥3.13, pandas ≥3.0.3 의존 | Python ≥3.10, pandas 없음 (경량 의존성) |
| 인증 UX | OS 자격증명 저장소, 멀티 alias, `doctor` 진단, env 모드(APP_KEY/APP_SECRET) | OS 키체인, 프롬프트 제로, 멀티 프로필, **`KIWOOM_TOKEN`**(키 노출 없이 토큰만, CI/샌드박스/에이전트) |

## 구체적 차이 하나로: litmus loop

에이전트가 "시세 확인 → 사전점검 → dry-run → 멱등키 주문 → 재시도 안전 확인
→ 미체결/잔고"를 **사람 개입 없이 stdout JSON과 exit code만으로** 완주할 수
있는가. kiwoom-cli는 이것을 실행 가능한 증명으로 제공한다:

- 모의투자 서버 대상 재현 스크립트: [benchmark/litmus.sh](../benchmark/litmus.sh)
  (`jq -e`로 매 단계 검증, 첫 실패에서 비0 exit)
- CI에서 항상 도는 네트워크 없는 버전:
  `tests/test_order.py::test_litmus_loop_json_driven`

kwcli의 json 출력으로도 개별 응답 파싱은 가능하다. 차이는 **분기 계약**이다:
2단계(잔고·장운영을 실조회하는 read-only `validate`)와 4–5단계(멱등키 재시도
안전)는 kwcli에 대응 기능이 없고, 문서화된 exit code·error.code 계약이 없어
실패 분기가 출력 휴리스틱에 의존하게 된다.

## 공식 저장소가 더 잘하는 것

정직하게, 다음은 공식 쪽이 낫거나 공식만 가능한 영역이다:

- **1차 제공자 신뢰**: 키움증권이 직접 유지하므로 API 변경이 가장 먼저
  반영될 개연성이 높고, 장애/스펙 문의의 공식 창구가 있다.
- **번들 스펙 + OpenAPI 매핑**: 로컬에 포함된 공식 스펙을 네트워크 없이
  탐색하고, 각 명령 `-h`에서 API 계약을 바로 확인할 수 있다.
- **계좌번호 마스킹**: 모든 출력에서 계좌 식별자를 마스킹한다. 로그·에이전트
  트랜스크립트 공유 시 유리하다.
- **Python SDK**: CLI 외에 라이브러리로 직접 임베드할 수 있는 공식 SDK를
  함께 제공한다. 파이썬 코드 안에서 쓰려면 그쪽이 자연스럽다.
- **Postman 컬렉션**: REST 엔드포인트를 GUI로 탐색·실험하기에 좋다.
- **표준 문서**: API 명세의 원본(canonical docs)은 공식 저장소/포털이다.
  kiwoom-cli의 스펙 해석이 갈리는 경우 공식 문서가 기준이다.

## 결론

- 파이썬 코드에 임베드하거나 공식 지원이 필요하면 → 공식 SDK/kwcli.
- 터미널에서 사람이 쓰거나, **AI 에이전트/스크립트가 안전하게 주문까지
  자동화**해야 하면 → kiwoom-cli. 위 표의 차이 중 envelope·exit code 계약,
  read-only validate, 멱등성, 미국주식, history 도구가 이 사용례를 위해
  존재한다.
