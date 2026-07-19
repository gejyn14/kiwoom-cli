# AGENTS.md: kiwoom-cli를 도구로 쓰는 에이전트를 위한 계약

kiwoom-cli는 AI 에이전트가 파싱 없이 안전하게 쓰도록 설계된 키움증권 CLI입니다.
이 문서는 기계가 의존해도 되는 **안정 계약**만 다룹니다.

## 기본 규칙

- 항상 `-f json`으로 호출하세요. stdout은 **단일 JSON 문서** 하나만 담습니다
  (진행 메시지·미리보기는 전부 stderr).
- json/csv 모드는 **절대 대화형 프롬프트를 띄우지 않습니다**. 확인이 필요한
  명령을 `--confirm` 없이 호출하면 즉시 `CONFIRMATION_REQUIRED` 오류(exit 1)로
  응답합니다. 세션이 입력 대기로 멈추는 일이 없습니다.
- 명령 스키마는 `kiwoom -f json describe [명령...]`으로 조회하세요 (아래 참고).

## Envelope (schema v1)

```json
{
  "ok": true,
  "schema": "v1",
  "data": { "...": "정규화된 필드", "raw": { "...": "원본 응답" } },
  "meta": { "profile": "default", "env": "mock", "cont": null },
  "error": null
}
```

- `ok`: `error === null`과 동치.
- `data`: 성공 페이로드. API 응답은 **정규화된 타입 필드** + 원본(`data.raw`).
  리스트형 응답은 `{"items": [...], "raw": [...]}`.
- `meta.env`: `"mock"`(모의투자) 또는 `"prod"`(실거래). **주문 전 반드시 확인하세요.**
  설정을 읽을 수 없는 오류 envelope(`NOT_CONFIGURED`, 손상된 config.toml)에서는
  `null`일 수 있습니다. 실제로 알 수 없는 값을 `"mock"`으로 지어내지 않습니다.
- `meta.cont`: 연속조회 커서. 값이 있으면 `--next-key <값>`으로 다음 페이지.
- `error`: `{"code", "retryable", "message", "upstream_code", "details"?}`.

## 정규화된 데이터 (data)

키움 API는 모든 값이 문자열이고 가격류의 +/-는 부호가 아니라 **방향지시자**입니다
("+70000" = 70000원, 상승). `data`는 이를 해석해 타입 있는 값으로 제공합니다:

| 정규 필드 | 원본 | 의미 |
|---|---|---|
| `symbol` | stk_cd | 종목코드 (문자열) |
| `name` | stk_nm | 종목명 |
| `price` | cur_prc | 현재가 (숫자, 부호 제거) |
| `change_direction` | cur_prc의 부호 | `"up"` / `"down"` (부호 있을 때만) |
| `change` | pred_pre | 전일대비 (부호 있는 숫자) |
| `change_pct` | flu_rt | 등락율 % (부호 있는 숫자) |
| `volume` | trde_qty | 거래량 |
| `qty` | rmnd_qty | 보유수량 |
| `avg_price` | avg_prc | 평균단가 |
| `eval_amount` | evlt_amt | 평가금액 |
| `pl_amount` | pl_amt | 손익금액 (부호 실제) |
| `pl_pct` | pl_rt | 손익율 % |
| `order_no` | ord_no | 주문번호 (문자열) |
| `dt` / `tm` / `cntr_tm` | 동일 | ISO-8601 (`2026-07-16`, `15:30:45+09:00`) |

- 방향지시 필드(가격류)는 절대값 + `<필드>_direction` 동반 키로 분리됩니다.
- 알 수 없는 키는 원래 이름·값 그대로 통과합니다.
- 원본 인코딩이 필요하면 `data.raw`를 읽으세요.

## --fields: 토큰 절약 투영

```bash
kiwoom -f json --fields symbol,price,change_pct stock info 005930
kiwoom -f json --fields symbol,qty account balance --market kr
```

`data`(및 내부 모든 리스트의 각 요소)를 지정한 키로만 투영하고 `data.raw`를
제거합니다. 대량 조회 시 응답 토큰을 크게 줄입니다.

**값이 dict나 list인 키도 이름으로 통째로 선택할 수 있습니다.** 요청한 키가
컨테이너면 내부를 다시 투영하지 않고 그대로 반환합니다(최상위 `raw` 키만
제거). dry-run의 `body`와 `order validate`의 `checks`가 대표적인 경우입니다.

```bash
kiwoom -f json --fields body order buy 005930 1 --price 70000 --dry-run
kiwoom -f json --fields checks order validate buy 005930 1 --price 70000
```

요청하지 않은 리스트 키는 **요청한 필드를 담은 원소가 하나라도 있을 때만**
남습니다. dict가 들어 있지 않은 리스트(숫자·문자열 배열)는 이름으로 직접
요청하지 않는 한 항상 제거됩니다. 값이 `0`인지 여부는 판단에 쓰이지 않습니다.

요청한 키 중 하나라도 매칭되지 않으면(부분 매칭 포함, 오타 등) 조용히 넘어가지 않고
`meta.fields_unmatched`에 매칭 실패한 키 목록을 담아 반환합니다. (`--fields`는
`-f json` 전용입니다. csv는 아래에서 설명하는 자체 컬럼 규칙을 따릅니다.)

## CSV 출력 형식

`-f csv`는 envelope을 쓰지 않고 순수 CSV만 stdout에 씁니다. 응답이 스칼라
요약과 리스트(예: 계좌 요약 + 보유종목)를 모두 갖고 있으면 **여러 블록**이
하나의 스트림에 이어져 나옵니다:

- 스칼라 요약 블록이 있으면 항상 먼저 나옵니다(딕트 값은 `parent.nested`로
  한 겹만 평탄화됩니다).
- 실제로 출력되는(비어 있지 않은) 블록들 사이에는 빈 줄이 **정확히 하나**
  있고, 마지막 블록 뒤에는 없습니다. 빈 리스트(예: 보유종목 없음)는 블록
  자체가 생략되므로 구분용 빈 줄도 남기지 않습니다.
- 블록마다 헤더 행이 하나씩 있습니다. 여러 블록을 하나의 테이블처럼
  이어붙여 파싱하면 안 됩니다.
- 블록의 컬럼은 **그 블록에 속한 모든 행의 합집합**입니다(첫 행의 키만이
  아님). 행마다 필드가 들쭉날쭉해도 뒤쪽 행에만 있는 컬럼이 잘리지 않습니다.
- 결과가 완전히 비어 있으면(요약도 리스트도 없음) 출력은 0바이트이고
  exit 0입니다. 이는 "성공했지만 보여줄 게 없다"이지 오류가 아닙니다.
- `account balance --market all`은 위 규칙과 다른 **단일 테이블 통합
  스키마**를 씁니다. 요약 블록 없이 국내/미국 보유종목을 한 테이블(`market`,
  `symbol`, `eval_krw` 등 통화 환산 컬럼 포함)로만 냅니다. 환율 환산 소계를
  스칼라 요약으로 낼지가 아직 미확정이라, 이 비대칭은 당분간 의도된
  상태입니다.
- table 모드는 최상위 딕트 값을 아예 표시하지 않고 건너뛰지만, csv는 그
  딕트를 한 겹 평탄화(`부모키.자식키`)해 컬럼으로 노출합니다. 두 포맷이
  같은 데이터를 다르게 보여주는 의도된 비대칭입니다.

## 페이지네이션 (연속조회)

`meta.cont.next_key`가 있으면 다음 페이지가 존재합니다. 전역 옵션 두 가지로
처리하며 동시 사용은 안 됩니다:

```bash
kiwoom -f json --next-key <이전 meta.cont.next_key> account orders executed
kiwoom -f json --all-pages market rank volume
```

- `--next-key <값>`: 명령의 **첫 API 요청에만** 커서를 주입해 해당 페이지부터
  재조회 (소비형). 나머지 페이지는 다시 응답의 `meta.cont`를 읽어 반복하세요.
- `--all-pages`: `cont-yn`이 끝날 때까지 자동으로 반복 요청하고 리스트형
  필드를 모두 병합해 한 번에 반환합니다(스칼라 필드는 첫 페이지 값 유지).
  최대 50페이지입니다. 상한에 도달하면 stderr로 안내하고 `meta.cont`는 유지되므로
  `--next-key`로 이어서 조회할 수 있습니다.

여러 API를 연속 호출하는 명령(`account balance --market all`, `dashboard` 등)에서는
`meta.cont`가 마지막 하위 호출 기준이며, `--next-key`는 명령의 첫 물리적 요청(내부
보조 호출 제외, 아래 참조)에 주입되므로 페이지네이션은 `--market kr|us`처럼
단일 API 경로에서 사용하세요.

변이(주문 전송·환전 신청·조건검색 요청/실시간/해제·raw `kiwoom api`의 주문성
API 등) 응답은 **`meta.cont`를 절대 포함하지 않습니다**. 업스트림이 실제로
연속조회 헤더를 보내더라도 CLI가 항상 `null`로 고정합니다. `--next-key`로
"이어서" 재실행하면 실제 동작(주문·환전 등)이 한 번 더 일어나므로, 변이 응답에서
`meta.cont`를 찾아 반복 호출하려 하지 마세요.

이 변이 예외는 응답 쪽(`meta.cont`)에서 끝나지 않습니다. 요청 쪽에서도
전역 `--all-pages`/`--next-key`를 **그 요청 자체에 대해 조용히 무시**합니다:
반복 실행이 안전한 조회와 달리, 변이에서 자동 반복은 실제 동작(주문 체결·자금
이동·서버측 구독 변경)을 여러 번 실행하는 것과 같기 때문입니다. 적용 대상은
다음 7개 커맨드/경로입니다 (모두 `_mutation.suppress_pagination()`을 요청
직전에 호출):

- `order buy`/`sell`/`modify`/`cancel`: 국내주식(`kt10000-3`)
- `order credit buy`/`sell`/`modify`/`cancel`: 신용(`kt10006-9`)
- `order gold buy`/`sell`/`modify`/`cancel`: 금현물(`kt50000-3`)
- `order buy`/`sell`/`modify`/`cancel`: 미국주식(`ust20000-3`, 위와 같은
  `send_order()` 경로 공유)
- `account exchange apply`: 환전 신청(`ust31302`, 실제 자금 이동)
- `order condition search`/`realtime`/`stop`: 조건검색 요청/실시간등록/해제
  (`ka10172-4`, `MUTATION_APIS`에는 없지만 `confirm_gate`가 걸린 서버측
  상태 변경이라 동일하게 예외 처리됨)
- raw `kiwoom api <api_id>`: `api_id`가 `MUTATION_APIS`(17개)에 있는 모든 호출

이 커맨드들에 `--all-pages`나 `--next-key`를 붙여도 아무 효과가 없습니다.
실제로 나가는 HTTP 요청은 항상 정확히 1개이고, 그 요청에는 `cont-yn`/
`next-key` 헤더가 실리지 않습니다. 값을 조용히 무시하는 것이지 오류로
거부하지 않으므로, 스크립트에 남아 있는 전역 플래그가 있어도 안전합니다.

미국 심볼 거래소 자동판별 보조 호출(usa10098)과 주문 `--dry-run`의 시세 조회
보조 호출(`_quote_price_kr`/`_quote_price_us`)은 내부(`internal`) 호출로
표시되어 전역 `--next-key`/`--all-pages`가 적용되지 않고 `meta.cont`도
기록하지 않습니다. 커서는 항상 명령의 본 조회가 소비/기록합니다. 이 시세
조회 결과(cur_prc)를 숫자로 해석할 수 없으면(빈 값/0 이하/NaN/Inf 포함)
`price`/`est_cost`를 0으로 조용히 채운 미리보기 대신 `QUOTE_UNAVAILABLE`
(exit 2)로 실패합니다. `price_source: "market_quote"`가 실제로는 실패한
조회에 붙는 것을 막기 위함입니다.

금현물(`order gold buy`/`sell`, kt50000/kt50001)은 시장가가 없고 전체
유형이 지정가 계열(`limit`/`ioc`/`fok`)이라 `--price`가 항상 필수입니다.
생략하면 시세를 조회해 채우지 않고 `INVALID_INPUT`(exit 1)으로 즉시
실패합니다. (과거엔 ka50010 기반 시세 조회로 금현물 시장가를 흉내 냈으나,
존재하지 않는 기능이었으므로 제거했습니다.)

`order validate`도 같은 시세 파서를 씁니다: `--price`를 생략하면 현재가(cur_prc)로
예상비용을 계산하는데, 이 조회가 실패/해석불가면 (validate는 dry-run과 달리
exit 2로 하드 실패하지 않고) `checks.price_known`이 `false`가 되어 `valid`가
`false`로 떨어집니다. 가격을 확정하지 못한 사전점검이 `valid: true`를 주장하지
않도록 하기 위함입니다. 매수 측 `checks.sufficient_balance`도 `price_known`에
연동됩니다: `price_known`이 `false`이면 `est_cost`가 신뢰할 수 없는 0이므로
"주문가능금액 >= 0"이 공허하게 참이 되는 것을 막기 위해 `sufficient_balance`는
`true`를 보고하지 않습니다. `checks`는 `data` 안에 실리므로, `valid` 필드를
보지 않고 개별 항목만 읽는 에이전트도 미수행 점검을 참으로 오인하지 않습니다.

## Exit codes

| code | 의미 | 대응 |
|---|---|---|
| 0 | 성공 | 없음 |
| 1 | 입력 오류 (인자, CONFIRMATION_REQUIRED, VALIDATION_FAILED) | 호출 수정 |
| 2 | API/네트워크 오류 | `error.retryable` 확인 후 재시도 판단 |
| 3 | 인증 필요 (토큰 없음/만료: `TOKEN_EXPIRED`(upstream 8005), HTTP 401 포함) | `kiwoom auth login` 또는 `KIWOOM_TOKEN` |

## Error codes (`error.code`)

| code | retryable | 의미 |
|---|---|---|
| `CONFIRMATION_REQUIRED` | ✗ | 변이 명령에 `--confirm`/`--yes` 누락 (json/csv 모드) |
| `VALIDATION_FAILED` | ✗ | `order validate` 실패. 실패 항목은 `error.details` |
| `IDEMPOTENCY_CONFLICT` | ✗ | 같은 `--client-order-id`가 다른 주문 내용으로 이미 사용됨. 재시도라면 인자가 이전 실행과 동일한지 확인, 새 주문이면 새 키 사용. exit 1, 전송되지 않음 |
| `LEDGER_BUSY` | ✓ | 멱등성 원장 잠금을 획득하지 못함. 같은 프로필의 다른 주문이 전송 중. 잠시 후 재시도. exit 2 (`IDEMPOTENCY_CONFLICT`와 달리 exit 1이 아님에 유의) |
| `ORDER_STATUS_UNKNOWN` | ✗ | 이전 시도가 전송 후 응답을 받지 못함. 주문이 체결되었을 수 있어 재전송하지 않음. `account orders pending`으로 확인 후 새 키 사용. exit 2 |
| `QUOTE_UNAVAILABLE` | ✗ | `--dry-run` 시장가 예상비용 계산용 시세 조회 결과를 숫자로 해석할 수 없음 (빈 값/0 이하/NaN/Inf 등, 금현물 dry-run 포함). 조용히 0으로 채우지 않고 exit 2로 실패. `order validate`는 같은 조건에서 exit 2 대신 `checks.price_known: false` → `VALIDATION_FAILED`(exit 1)로 나타남 |
| `AUTH_REQUIRED` | ✗ | 토큰 없음. 키체인 불가 환경이면 메시지가 `KIWOOM_TOKEN` 안내 |
| `TOKEN_EXPIRED` | ✗ | 재로그인 필요 (upstream 8005, HTTP 401) |
| `INVALID_INPUT` | ✗ | 파라미터 형식/누락 (upstream 1511/1512/1517/2) |
| `INVALID_API` | ✗ | 잘못된 API ID. `exit 1`(raw `kiwoom api`가 로컬 레지스트리에 없는 api_id를 보내기 전에 클라이언트 사전검증으로 거부) / `exit 2`(업스트림이 실제로 1501/1504/1505를 응답). 둘 다 같은 `error.code`이므로, exit code만 보고 분기하면 두 경우를 뒤섞는다. `error.code`로 먼저 분기하세요 |
| `NOT_FOUND` | ✗ | 종목/시장 없음 |
| `RATE_LIMITED` | ✓(1700) | 호출 제한. backoff 후 재시도 |
| `ENV_MISMATCH` | ✗ | 실전/모의 불일치 (appkey/token) |
| `IP_MISMATCH` | ✗ | 발급 IP와 요청 IP 다름 |
| `INVALID_CREDENTIALS` / `TOKEN_ISSUE_FAILED` / `TOKEN_REVOKE_FAILED` | ✗ | 키/발급 문제 |
| `NOT_CONFIGURED` | ✗ | 설정 필요. 먼저 `kiwoom config setup` 실행. exit 1 |
| `KEYCHAIN_UNAVAILABLE` | ✗ | OS 키체인 접근 불가. `KIWOOM_TOKEN` 사용. exit 1 |
| `NETWORK_ERROR` | ✓ | 연결 실패·타임아웃 등 전송 오류 (`httpx.RequestError` 전반을 포괄) |
| `DEPENDENCY_MISSING` | ✗ | 선택적 패키지 미설치 (예: `websockets` 없이 `stream`). exit 1 |
| `UPSTREAM_ERROR` | ✓/✗ | 분류되지 않은 서버 오류 (`upstream_code` 참고) |

통합 명령(`account balance/deposit/pnl/orders --market all`)에서 국내·미국이 모두
실패하면 json 모드는 `UPSTREAM_ERROR` envelope + exit 2를 반환합니다. table 모드도
동일한 경우 빨간 stderr 메시지와 함께 exit 2로 종료합니다(이전에는 조용히 exit 0).
`dashboard`(계좌 잔고+거래량 상위)도 동일한 계약입니다. 두 API가 모두 실패하면
포맷 불문 exit 2, 하나만 실패하면 나머지로 계속 진행(exit 0, json은 해당 키가
명시적 `null`). 단, `data.account` 키는 두 상태를 구분합니다: 토큰이 없어
애초에 조회를 시도조차 안 했으면 키 자체가 **없고**, 토큰은 있는데 조회가
실패했으면 `account`가 명시적으로 **`null`**입니다. 전자는 "로그인하면
나올 수도 있다", 후자는 "시도했지만 실패했다"로 의미가 다릅니다.
`data.top_volume`은 계좌와 달리 토큰 유무로 게이팅되지 않고 항상 시도되므로,
실패 시에는 (조회를 아예 안 하는 경우가 없어) 언제나 `null`로 나타납니다.

## 주문 안전장치

| 플래그 | 효과 |
|---|---|
| `--confirm` / `--yes` | 확인 게이트 통과 (없으면 json/csv에서 `CONFIRMATION_REQUIRED`) |
| `--dry-run` | 전송될 body를 그대로 출력, **아무것도 전송하지 않음**. `--confirm`보다 우선 |
| `--client-order-id KEY` | 멱등키. 같은 키 재실행 → 재전송 없이 이전 응답 + `idempotent_replay: true` |
| `order validate buy\|sell CODE QTY` | read-only 사전점검: `symbol_ok` / `market_open`(KST 시계 휴리스틱, `heuristic: true`) / `sufficient_balance` / `price_ok` / `price_known`(현재가 조회로 예상비용을 계산할 수 있었는지) |

멱등키는 주문 내용(api_id+body)의 fingerprint에 바인딩되며, 조회→전송→기록
구간은 원장 파일 잠금으로 프로세스 간 직렬화된다. 같은 키로 다른 내용을
보내면 `IDEMPOTENCY_CONFLICT`. 잠금 대기는 POSIX(fcntl)에서는 무한 대기하며,
Windows(msvcrt)에서만 약 10초 재시도 후 획득 실패로 `LEDGER_BUSY`
(exit 2, retryable)가 발생한다. 잠시 후 재시도하면 된다.

전송 직전에 원장에 "inflight" 표식을 남긴 뒤 전송한다. 이후 결과는 세 가지로
갈린다:

- **전송 성공**: 응답을 원장에 기록. 같은 키 재실행 → 재전송 없이 그 응답을
  반환(`idempotent_replay: true`).
- **업스트림이 구조적으로 거부**(`return_code`가 0이 아님, `KiwoomAPIError`):
  주문이 실행되지 않았다는 것이 확인됐으므로 원장을 "rejected"로 종결하고
  키를 재사용 가능한 상태로 남긴다. 잘못된 부분을 고쳐 같은 키로 다시
  보내면 새 in-flight 기록과 함께 다시 전송된다.
- **전송 결과 자체가 불명**(타임아웃/연결 끊김/프로세스 종료 등 전송 계층
  오류): 응답을 받지 못했으므로 표식이 "inflight"로 남고, 같은 키로
  재시도하면 재전송 대신 `ORDER_STATUS_UNKNOWN`(exit 2, retryable=false)을
  반환한다. 주문이 실제로 체결됐을 수 있으니 `account orders pending`으로
  확인한 뒤 사람이 직접 판단해 새 키로 재시도하라.

미국 주식 주문은 body에 자동판별된 거래소가 포함되므로, 같은
`--client-order-id`로 재실행했는데 그 사이 거래소 판별이 달라지면(캐시 갱신 등)
body가 달라져 `IDEMPOTENCY_CONFLICT`가 날 수 있다. 의도된 동작이다. 같은
주문인지 확인한 뒤 필요하면 새 키로 재시도하라.

권장 주문 순서: **validate → --dry-run → --confirm --client-order-id**.
항상 `meta.env`를 확인하고, 실거래(`prod`)에서는 dry-run을 생략하지 마세요.

## 실시간 스트리밍 (NDJSON)

`-f json`에서 `kiwoom stream *`은 REAL 이벤트마다 **envelope 한 건을 compact
JSON 한 줄**(NDJSON)로 stdout에 출력합니다. 줄 단위로 파싱하세요.

```bash
$ kiwoom -f json stream quote 005930 --max-events 3
{"ok": true, "schema": "v1", "data": {"type": "0B", "type_name": "주식체결", "symbol": "005930", "ts": "15:30:00+09:00", "price": 70000, "change_direction": "up", "change_pct": 0.72, ...}, "meta": {...}, "error": null}
... (총 3줄 후 exit 0)
```

- `data`: 정규화된 이벤트. `type`(실시간 타입 코드), `type_name`, `symbol`,
  `ts`(ISO-8601 +09:00), 그리고 타입 있는 필드(`price`, `change`, `change_pct`,
  `volume`, `acc_volume`, `open`/`high`/`low`, `ask`/`bid` 등). 영문 정규명이
  없는 필드는 한글 이름(예: `주문상태`)으로 제공됩니다.
- 스트림 이벤트에는 `data.raw`가 **없습니다** (크기 절약). 전역 `--fields`는
  각 줄의 `data`에 동일하게 적용됩니다.
- **종료 조건** (모든 stream 명령 공통). 도달 시 소켓을 닫고 exit 0:
  - `--max-events N`: N개 이벤트 수신 후 종료 (정확히 N줄 출력)
  - `--duration 30s|5m|2h`: 경과 시간 후 종료 (이벤트가 없어도 타이머로 종료)
  - `--until <ISO-8601>`: 지정 시각 도달 시 종료 (타임존 없으면 +09:00 가정)
- 오류: WebSocket 오류는 envelope 오류 **한 줄**로 stdout에 출력됩니다.
  연결/등록 오류는 exit 2, 인증 문제는 exit 3. 진행 배너는 전부 stderr.
- 국내 전용 소켓입니다 (미국 실시간은 미지원).

### 녹화 (--record)와 history

- 모든 stream 명령의 `--record [경로]`는 정규화 이벤트(NDJSON 한 줄 = 위
  `data`와 동일한 dict, envelope 없음)를 파일에 기록합니다. 출력 형식과
  무관하게 동작하며, 경로 생략 시 `<설정 디렉토리>/data/<심볼>_<YYYY-MM-DD>.ndjson`
  (계좌성 타입 00/04는 심볼 대신 타입명). 시작/종료 시 파일 경로와 건수가
  stderr로 출력됩니다.
- `kiwoom history list`: 녹화 파일별 `file`/`symbol`/`date`/`events`/`first_ts`/`last_ts`.
- `kiwoom history query CODE --from ISO --to ISO [--type 0B]`: ts 범위/타입
  필터. 파일은 스트리밍으로 읽고, 잘못된 줄은 stderr 경고 후 건너뜁니다.
- `kiwoom history export CODE --dest sqlite|csv|parquet [--out 경로] [--from --to]`:
  sqlite는 `events(ts, symbol, type, price, volume, raw_json)` + `(symbol, ts)`
  인덱스. parquet은 pandas+pyarrow 필요 (없으면 stderr 안내 + exit 1).
- json 모드 출력: list/query는 `data.items`(raw 없음), export는
  `{out, format, events}` 요약.

## describe: CLI 자기서술

```bash
kiwoom -f json describe                 # 전체 명령 트리
kiwoom -f json describe order buy       # 단일 명령 스키마
kiwoom -f json describe --paths         # 경로+한줄설명 평면 목록 (저비용 발견)
kiwoom -f json describe order --depth 1 # 하위 명령 재귀 깊이 제한
```

명령별로 `path` / `help` / `arguments[]` / `options[]`(opts, type, default,
required, choices, is_flag)를 반환합니다. 도움말 파싱 대신 이걸 쓰세요.

- `--paths`: 전체 트리 대신 `{path, help}` 배열만 반환 (스키마 없이 명령을
  먼저 훑어볼 때 토큰 절약). `--depth N`은 전체 스키마 모드에서만 적용되며 `--paths`와 함께 쓰면 무시됩니다.
- `market` 명령들은 docstring에 사용하는 API ID를 명시하므로(예:
  `순위 정보 조회. (ka10016)`) `describe`의 `help` 필드에서 바로 확인됩니다.

### find / api list: 키워드 발견

- `kiwoom -f json find <키워드>` → `data = {"commands": [{"path","help"}], "apis": [{"api_id","description"}]}` (결과 없음 = 빈 배열, exit 0)
- `kiwoom -f json api list [키워드]` → `data = [{"api_id","url_path","description"}]` (토큰 불필요)
- 주문성 API(`kt10000~3`, `kt10006~9`, `kt50000~3`, `ust20000~3`, `ust31302`)를
  `kiwoom api`로 직접 호출하면 확인 게이트가 걸립니다: json/csv 모드는 `--confirm`
  없이 `CONFIRMATION_REQUIRED`(exit 1), table 모드는 body 미리보기 후 y/n 프롬프트.
  자동화에서는 `--confirm`을 명시하세요. 조회 API는 영향 없습니다.

## 인증 (비대화형 환경)

키체인 접근이 불가한 샌드박스/CI/에이전트 환경에서는 사용자 터미널에서 발급한
토큰을 `KIWOOM_TOKEN` 환경변수로 전달받으세요. appkey/secretkey는 환경변수를
지원하지 않습니다(의도된 제약). `KIWOOM_DOMAIN`(prod/mock), `KIWOOM_PROFILE`,
`KIWOOM_ACCOUNT`도 환경변수로 지정 가능합니다.

## Litmus loop: 전체 흐름 예시

각 단계는 이전 단계의 stdout JSON만으로 구동됩니다 (전부 `-f json`):

```bash
# 1. 시세: 타입 있는 필드 (파싱 불필요)
$ kiwoom -f json --fields symbol,price,change_direction stock info 005930
{"ok": true, "data": {"symbol": "005930", "price": 70000, "change_direction": "up"}, ...}

# 2. 사전점검 (read-only, 주문 미전송)
$ kiwoom -f json order validate buy 005930 10 --price 70000
{"ok": true, "data": {"valid": true, "checks": {"symbol_ok": true, "market_open": true,
 "sufficient_balance": true, "price_ok": true, "price_known": true}, "est_cost": 700000,
 "heuristic": true}, ...}

# 3. dry-run: 전송될 body 확인 (미전송)
$ kiwoom -f json order buy 005930 10 --price 70000 --type limit --dry-run
{"ok": true, "data": {"would_send": true, "api_id": "kt10000", "est_cost": 700000,
 "currency": "KRW", "env": "mock", "body": {"stk_cd": "005930", "ord_qty": "10", ...}}, ...}

# 4. 실제 주문: 멱등키와 함께
$ kiwoom -f json order buy 005930 10 --price 70000 --type limit --confirm --client-order-id run-42
{"ok": true, "data": {"order_no": "0000777", "raw": {...}}, ...}

# 4b. 재시도해도 안전: 같은 키는 재전송하지 않음
$ kiwoom -f json order buy 005930 10 --price 70000 --type limit --confirm --client-order-id run-42
{"ok": true, "data": {"order_no": "0000777", "idempotent_replay": true, ...}, ...}

# 5. 미체결 확인
$ kiwoom -f json --fields order_no,symbol account orders pending --market kr

# 6. 잔고 확인
$ kiwoom -f json --fields symbol,qty,pl_amount account balance --market kr
```

실패 시 분기: `.ok`가 false면 `.error.code`로 스위치합니다.
`CONFIRMATION_REQUIRED` → `--confirm` 추가, `AUTH_REQUIRED`(exit 3) → 재인증,
`RATE_LIMITED` + `retryable: true` → backoff 재시도, `VALIDATION_FAILED` →
`error.details`의 실패 체크를 해소한 뒤 재시도.
