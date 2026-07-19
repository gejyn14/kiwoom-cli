# Changelog

## [Unreleased]

`stock investor after-close`(ka10066)의 `--trade` 값이 스펙과 반대였고, 정정과
함께 두 옵션에 raw 숫자코드와 함께 쓸 수 있는 human-readable 이름을
추가했습니다(하위호환).

**Fixed**

- **`--trade` 기본값이 실제로는 순매도(2) 데이터를 반환하고 있었습니다.**
  스펙(ka10066 Request Body)은 `trde_tp`를 `0:순매수, 1:매수, 2:매도`로
  정의하는데, 기존 코드는 `Choice(["1","2"])`에 `default="2"`였고 help는
  `1=순매도, 2=순매수`라고 적어 실제 동작과 정반대로 안내했습니다. 진짜
  순매수 코드인 `0`은 Choice 목록에 없어 애초에 지정할 수 없었습니다.

**Non-breaking (사람이 읽는 이름 추가, 하위호환)**

- **`--trade`/`--amount-qty`가 이제 `net-buy`/`buy`/`sell`, `amount`/`quantity`
  같은 사람이 읽는 이름도 받습니다.** 기존에 숫자 코드(`1`/`2`/`0`)를 직접
  넘기던 스크립트는 **그대로 동작합니다** — `HumanChoice`가 raw API 코드를
  하위호환으로 계속 허용하기 때문입니다(`kiwoom_cli/commands/_constants.py`
  `HumanChoice.convert`). 전송값도 이름 추가 전과 동일합니다:
  `net-buy`→`trde_tp=0`, `buy`→`trde_tp=1`, `sell`→`trde_tp=2`;
  `amount`→`amt_qty_tp=1`, `quantity`→`amt_qty_tp=2`. 이름으로 바꿀 필요
  없이 기존 호출을 그대로 둬도 됩니다.
- **`--market`이 이제 `all`도 받습니다.** 스펙에 `000:전체`가 있었는데
  기존 코드는 `kospi`/`kosdaq` 두 값만 허용했습니다. 순수 추가라 기존
  호출은 영향 없습니다(기본값 `kospi` 그대로).

**Breaking**

- **`--trade`의 기본값이 `trde_tp=2`(매도)에서 `trde_tp=0`(순매수)로
  바뀌었습니다.** 이건 이름 체계와 무관한 별개의 변경입니다 — raw 코드를
  직접 지정하는 호출(`--trade 2`, `--trade sell` 등)은 위와 같이 계속
  똑같은 데이터를 반환하지만, **`--trade`를 아예 지정하지 않고 기본값에
  의존하던 호출**은 이제 다른 데이터(순매수 상위 종목)를 받습니다. 이전에
  기본값으로 매도 데이터를 받던 스크립트는 명시적으로 `--trade sell`을
  추가해야 이전과 같은 데이터를 계속 받습니다.

## [2.10.1] - 2026-07-19

금현물 주문(`order gold buy`/`sell`, kt50000/kt50001)이 API가 받지 않는 주문타입을
`--type`에 노출하던 결함을 수정했습니다 (live money-path 핫픽스).

**Fixed**

- **`--type limit`(기본값)이 스펙에 없는 `trde_tp="0"`(한 자리)을 보내고
  있었습니다.** 금현물 kt50000/kt50001의 `trde_tp`는 `"00"`/`"10"`/`"20"`
  (2자리) 세 값만 허용합니다. 지금까지 `limit`은 국내주식용 `trde_tp="0"`을
  그대로 전송해 실제 API가 정의하지 않은 값을 매 주문마다 보내고 있었습니다.
  이제 `limit` → `"00"`, `ioc` → `"10"`, `fok` → `"20"`을 보냅니다
  (`ioc`/`fok`는 원래도 정확했습니다).
- **`--price` 없이 `order gold buy/sell`을 실행하면 빈 `ord_uv`("")가
  전송되고 있었습니다.** 금현물은 세 유형 모두 지정가(보통) 계열이라
  시장가가 없는데도, `--price`를 생략하면 국내주식 공용 기본값 로직이
  조용히 "시장가"로 해석해 가격 없이 주문을 구성했습니다. 이제 `--price`
  없이는 `INVALID_INPUT`으로 즉시 종료합니다(전송하지 않음).

**Breaking**

- **`order gold buy`/`sell --type`이 이제 `limit`/`ioc`/`fok` 세 값만
  허용합니다.** 이전에는 국내주식 18종 전체(`market`, `conditional`,
  `after-hours`, `best` 등)를 문법상 받아줬지만, 실제로는 `limit`/`ioc`/
  `fok`을 뺀 15종 모두 API가 정의하지 않은 `trde_tp` 값을 전송하는
  결함이었습니다. 이 15종 중 하나를 쓰던 스크립트는 `--type limit`
  (지정가) + `--price <값>`으로 바꿔야 합니다. `--type`을 아예 생략해
  왔다면 이제 `--price`를 반드시 함께 지정해야 합니다(금현물은 시장가가
  없습니다).
- `kt50002`/`kt50003`(금현물 정정/취소)은 영향 없습니다 — 두 API에는
  애초에 `trde_tp` 필드가 없고, 해당 명령에는 `--type` 옵션 자체가
  없습니다.

## [2.10.0] - 2026-07-19

에이전트 계약(agent contract) 정비. `-f json`은 stdout에 **파싱 가능한 envelope
하나만**, `-f csv`는 **CSV 데이터만** 내보낸다는 보장을 실제로 지키도록 7개 결함을
고쳤습니다. 소비자가 "데이터가 없음"과 "조회가 실패했음"을 구분할 수 있게 하는
것이 이번 릴리스의 핵심입니다.

**Breaking**

- **`-f csv`의 dict 응답이 스칼라 요약 블록을 함께 출력합니다.** 이전에는 응답에
  리스트가 하나라도 있으면 스칼라 값이 **통째로 버려졌습니다**. 이제 요약 블록,
  빈 줄 하나, 그리고 리스트 블록 순서로 나옵니다. `account balance`의 예수금·
  총매입금액과 `dashboard`의 계좌 블록이 여기 해당합니다. CSV를 단일 테이블로
  가정하고 파싱하던 스크립트는 수정이 필요합니다.

  ```
  # 2.9.0 (요약 소실)
  stk_cd,stk_nm,rmnd_qty
  005930,삼성전자,10
  000660,SK하이닉스,5

  # 2.10.0
  entr,tot_pur_amt
  1000000,5000000

  stk_cd,stk_nm,rmnd_qty
  005930,삼성전자,10
  000660,SK하이닉스,5
  ```

- **값이 전부 dict/list인 응답이 `-f csv`에서 0바이트 + exit 0을 내던 문제.**
  `_flat_dict`가 스칼라만 남기고 `[]`를 반환해 아무것도 출력하지 않았습니다.
  이제 dict 값을 한 단계 재귀해 `부모.자식` 형태의 컬럼으로 펼칩니다. 예:
  `{"account": {"entr": 1000}}` → 컬럼 `account.entr`.
- **테이블·CSV 컬럼이 첫 행이 아니라 전체 행의 합집합으로 결정됩니다.**
  이전에는 첫 레코드에 없는 키가 모든 행에서 보이지 않았습니다. 서로 다른 이벤트
  타입이 한 파일에 섞인 `history query`(예: `stream multi --record`가 0B와 0D를
  같은 파일에 기록)에서 뒤쪽 타입의 컬럼이 전부 공백이던 문제가 사라집니다.
  컬럼 수가 늘어날 수 있습니다.
- **`--fields`가 요청하지 않은 리스트 키를 더 이상 무조건 남기지 않습니다.**
  이전에는 모든 리스트 키가 원소를 `{}`로 채운 채 살아남았습니다. 이제 요청한
  필드를 담은 원소가 하나라도 있을 때만 남습니다. dict가 없는 리스트(스칼라
  배열)는 이름으로 직접 요청하지 않는 한 항상 제거됩니다.
- **`dashboard -f json`의 부분 실패 표현이 바뀝니다.** 조회에 실패한 쪽은 키가
  사라지는 대신 명시적 `null`로 남습니다. 양쪽 모두 실패하면 `UPSTREAM_ERROR`
  envelope + **exit 2**입니다(이전에는 `{"ok": true}` + exit 0). table 모드도
  동일하게 exit 2로 끝납니다.
- **`stock sync -f json`이 평문 대신 envelope을 출력합니다**
  (`{"synced": N, "cache": "..."}`). `-f csv`에서는 stdout이 비고 완료 메시지가
  stderr로 갑니다. `stock search`와 미국 `stock search`의 빈 결과도 평문이 아니라
  `{"items": [], "raw": []}`가 됩니다 — 미국 쪽은 이전에 **stdout이 완전히 비어
  exit 0**이었습니다.

**Fixed**

- 손상된 `config.toml` 위에서 `config setup`이 실행되지 않던 문제. 오류 메시지가
  복구 방법으로 `config setup`을 안내하는데 그 명령 자체가 같은 예외로 죽어,
  안내를 따른 에이전트가 무한루프에 빠졌습니다. 게다가 appkey/secretkey가 실패
  지점보다 **먼저** 키체인에 기록돼 재시도마다 자격증명을 덮어썼습니다. 이제
  루트 콜백과 `config setup` 양쪽이 손상된 파일을 견디고, 키체인 기록은 설정
  로드 이후로 옮겼습니다.
- `KiwoomGroup`의 오류 출력 11곳이 `-f csv`에서 stdout으로 나가 리다이렉트한
  CSV 파일을 한국어 산문과 ANSI 이스케이프로 오염시키던 문제. 전부 stderr로
  보냅니다.
- 미처리 예외 3종이 traceback + 빈 stdout + exit 1로 끝나 "인자 오류"로
  오인되던 문제. 잘못된 api_id → `INVALID_API`(exit 1), 손상된 `config.toml` →
  `NOT_CONFIGURED`(exit 1), JSON이 아닌 응답 바디(HTTP 200 점검 페이지 등) →
  `UPSTREAM_ERROR`(exit 2).
- `--fields`가 dict/list 값을 가진 키를 이름으로 선택하지 못하던 문제.
  `AGENTS.md`가 문서화한 `--fields body`(dry-run)와 `--fields checks`(validate)가
  `data: {}` + `fields_unmatched`를 반환해, 존재하는 필드를 오타로 안내했습니다.
- 오류 envelope의 `meta.env`가 설정을 읽을 수 없을 때 `"mock"`으로 위조되던 문제.
  `meta.env`는 에이전트가 주문 안전을 판단하는 필드이므로 이제 `null`을 냅니다.

### Changed
- `AGENTS.md`에 **`## CSV 출력 형식`** 절이 추가됐습니다. 블록 순서, 빈 줄 구분,
  블록당 헤더 1행, 컬럼 합집합 규칙, 빈 결과의 0바이트 + exit 0을 명시합니다.
  `account balance --market all`은 환율 환산 소계 스키마가 미확정이라 요약 블록
  없는 단일 테이블을 유지하며, 이 비대칭도 문서에 적었습니다.
- `INVALID_API`가 클라이언트 사전검증에서는 exit 1, 업스트림 응답에서는 exit 2로
  끝난다는 점을 `AGENTS.md` 오류 코드 표에 명시했습니다.
- 설치 문서를 uv·pipx 중심으로 개편했습니다. 패키징은 바뀌지 않았고(기존에도
  `uv tool install`/`pipx install`이 그대로 동작했습니다) 문서만 바뀌었습니다.
  README에 `## 설치` 절이 추가되어 격리 설치(uv/pipx/pip), 설치 없이 실행
  (`uvx --from kiwoom-cli kiwoom`), 프로젝트 의존성(`uv add`), 업그레이드·삭제,
  그리고 예전 `pip install` 실행 파일이 PATH에서 새 설치본을 가리는 경우의
  진단 방법을 다룹니다. `SECURITY.md`·`CONTRIBUTING.md`·`benchmark/README.md`의
  설치·업그레이드 안내도 함께 갱신했습니다.

## [2.9.0] - 2026-07-19

**Breaking**
- `-f json`(`data` 필드)와 **테이블(`-f table`, 기본값) 렌더링** 양쪽에서 아래 26개
  필드의 타입/표시가 바뀝니다 (`kiwoom_cli/formatters.py`의 `_ABS_FIELDS`/
  `_SIGNED_FIELDS`에 새로 편입 → json은 `normalize.py`의 `_NUMERIC_FIELDS`가 그대로
  이어받고 테이블은 같은 분류를 `_needs_fmt`가 공유). **`-f csv`는 영향이 없습니다.**
  CSV는 `normalize_record`/`_smart_fmt`를 거치지 않고 원본 값을 그대로 씁니다.
  json은 문자열이던 값이 숫자로 파싱되고 `_ABS_FIELDS` 필드는 부호가 제거된
  절대값 + (부호가 있었을 때만) `<필드>_direction`("up"/"down") 동반 키가
  추가됩니다. 예: `"sel_bid": "-96"` → `"sel_bid": 96, "sel_bid_direction":
  "down"`, `"trde_qty_n": "890"` → `"trde_qty_n": 890`. 테이블은 같은 필드의
  방향지시자 부호가 더 이상 표시되지 않습니다(아래 Fixed 참고, 하락 종목
  가격이 음수로 보이던 버그의 수정이기도 합니다).
  - `_ABS_FIELDS`로 편입(부호 제거 + `_direction` 동반 키 추가 가능): `sel_bid`, `buy_bid`,
    `cntr_pric`, `pri_sel_bid_unit`, `pri_buy_bid_unit`, `wonju_pric`, `past_curr_prc`,
    `52wk_hgst_pric`, `52wk_lwst_pric`, `tdy_high_pric`, `tdy_low_pric`, `sel_1th_bid`,
    `sel_2th_bid`, `sel_3th_bid`, `sel_4th_bid`, `sel_5th_bid`, `buy_1th_bid`, `buy_2th_bid`,
    `buy_3th_bid`, `buy_4th_bid`, `buy_5th_bid`, `cur_prc_n`, `trde_qty_n`, `acc_trde_qty_n`
  - `_SIGNED_FIELDS`로 편입(부호 유지, 숫자 타입만 변경): `pred_pre_n`, `flu_rt_n`
- 시장가 계열 주문유형에 대한 `--price` 가드 확장. 국내는 `best`/`best-ioc`/
  `best-fok`/`first`/`mid`/`mid-ioc`/`mid-fok` 7종(기존 시장가/시장가IOC/
  시장가FOK 3종 → 10종), 미국은 `moc`/`vwap`/`twap`/`stop` 4종(기존 0종 → 5종,
  `market` 포함)에 `--price`를 지정하면 이제 `INVALID_INPUT`(exit 1)으로
  거부됩니다. **이전에는 조용히 받아들여지고 지정한 가격이 버려진 채 시장가로
  체결**됐습니다. `order buy/sell`, `order validate`, 신용/금현물/미국 주문
  등 `_resolve_order_type`/`_validate_us_type`을 공유하는 모든 커맨드에
  적용되므로, 이 조합으로 주문을 자동화한 에이전트/스크립트는 인자를
  수정해야 합니다.

### Added
- 멱등성 원장(`~/.kiwoom/idempotency/<프로필>-<환경>.jsonl`)이 전송 직전
  `inflight` 상태를 먼저 기록합니다. 응답 유실(타임아웃/연결 끊김/프로세스
  종료) 후 같은 `--client-order-id`로 재시도하면 재전송 대신
  `ORDER_STATUS_UNKNOWN`(신규 오류 코드, exit 2, retryable: false)으로
  차단합니다. 업스트림이 구조적으로 거부했거나(`return_code != 0`) 애초에
  업스트림에 도달하지 못한 시도(예: 토큰 없음. 실제 HTTP 전송 이전 단계에서만
  발생함이 코드 구조상 보장되는 경우)는 `rejected` 상태로 종결되어 같은 키로
  안전하게 재시도할 수 있습니다. 원장에 `status` 필드(`inflight`/`done`/
  `rejected`)가 추가됩니다. `status` 키가 없는 기존(v2.4~v2.8) 원장은
  `done`으로 간주해 하위호환됩니다.
- 신규 오류 코드 `QUOTE_UNAVAILABLE`: `--dry-run` 시장가 예상비용 계산용
  시세를 숫자로 해석할 수 없을 때(빈 값/0 이하/NaN/Inf 등) exit 2로 실패
  (아래 Fixed 참고).

### Fixed
- 호가·체결가 방향지시자 부호가 테이블에 그대로 노출되던 문제 보완. `sel_bid`/`buy_bid`/
  `cntr_pric`/`pri_sel_bid_unit`/`pri_buy_bid_unit`/`wonju_pric`/`past_curr_prc`/`52wk_hgst_pric`/
  `52wk_lwst_pric`/`tdy_high_pric`/`tdy_low_pric`/ka10095 호가 1~5단계(`buy_5th_bid` 포함,
  형제 필드만 벗겨지고 이것만 남아 비대칭으로 보이던 문제)/`cur_prc_n` 등 22개 필드
  (Breaking 섹션의 26개 중 `trde_qty_n`/`acc_trde_qty_n`은 애초에 부호가 노출된 적이
  없고 `pred_pre_n`/`flu_rt_n`은 실제 등락폭이라 부호를 의도적으로 유지하므로
  테이블 렌더링 버그 수정 대상이 아니다)
- 계좌 잔고(평가현황/통합잔고)·대시보드 거래량상위·`stock compare`의 현재가가
  `strip_sign=True` 누락으로 방향지시자 부호를 그대로 노출하던 문제(하락
  종목이 음수 가격으로 표시됨).
- 날짜(YYYYMMDD)/시각(HHMMSS) 필드가 길이 기반 숫자 휴리스틱을 통과해 콤마로
  묶여 표시되던 문제 (예: `20260716` → `20,260,716`). 스펙 전수 스윕으로
  `_CODE_FIELDS`를 17→55개, 이어서 4개 추가로 총 59개까지 확장.
- 미국주식 시장가 `--dry-run`의 예상비용(`est_cost`)이 항상 0으로 나오던 문제.
  스펙에 없는 필드명(`now_pric`)을 참조하던 것을 실제 스펙 필드(`cur_prc`)로 수정.
- 금현물 `--dry-run` 시세 조회가 스펙상 금현물 종목코드(`M04020000`)를 받지 않는
  `ka10001`(주식기본정보)을 호출하던 문제. `ka50010`(금현물체결추이)으로 라우팅 수정.
- `--dry-run` 시장가 예상비용 계산용 시세가 빈 값/NaN/Inf/0 이하일 때 조용히
  0으로 채워 `price_source: "market_quote"`를 거짓 주장하던 문제. 국내/미국/
  금현물 공통으로 `QUOTE_UNAVAILABLE`(exit 2) 실패로 교정.
- `order validate`에 `Infinity` 가격을 넘기면 `OverflowError` traceback으로
  크래시하던 문제. `VALIDATION_FAILED`(exit 1)로 교정. 신규 `price_known`
  검사(`--price` 미지정 시 현재가로 예상비용을 계산할 수 있었는지)를 추가하고,
  매수 측 `sufficient_balance`가 `price_known: false`일 때(`est_cost=0`) 공허하게
  `true`를 보고하던 문제를 수정.
- `account exchange apply`(환전)와 주문 조건검색 3종(`order condition
  search`/`realtime`/`stop`)이 업스트림 `cont-yn: Y` 응답 시 전역 `--all-pages`를
  따라 최대 50회까지 반복 전송(재이체/재구독)될 수 있던 문제. 변이 요청은
  페이지네이션 대상에서 제외.
- 변이(주문 전송/환전/조건검색) 응답의 json envelope에 `meta.cont`가 남아있어
  `--next-key`로 이어서 실행하라는 안내가 실제로는 같은 동작을 한 번 더
  실행하도록 유도하던 문제. 변이 응답은 이제 항상 `meta.cont: null`.
- `kiwoom api`로 주문성 API를 raw 호출할 때 `cont-yn: Y` stderr 힌트("연속조회
  가능")가 위 `meta.cont` 억제와 무관하게 계속 출력되던 문제.
- 전송 전 인증 실패(토큰 없음)가 실제로는 아무것도 전송하지 않았는데도
  멱등성 키를 `inflight`로 영구히 소진해, 재로그인 후 재시도가
  `ORDER_STATUS_UNKNOWN`으로 영구히 막히던 문제. 실제 HTTP 전송 이전 단계에서만
  발생함이 보장되는 `KiwoomAuthError`를 `KiwoomAPIError`와 동일하게 `rejected`로
  종결 처리. 업스트림 `return_code: 8005`(만료)도 HTTP 200이므로 `rejected`가 되어
  키가 재사용 가능하다. 다만 HTTP 401은 요청이 이미 업스트림에 도달한 것이므로
  의도적으로 `inflight`로 남는다.

## [2.8.0] - 2026-07-18

**Breaking**
- 프로필 이름이 `[A-Za-z0-9_-]{1,64}` allowlist로 제한됩니다 (경로 조작 차단).
  점(.)·공백 등이 포함된 기존 프로필은 `config setup`으로 재생성이 필요합니다.
- 주문성 API 17개(`kt10000~3`, `kt10006~9`, `kt50000~3`, `ust20000~3`, `ust31302`)를
  `kiwoom api`로 직접 호출하면 확인 게이트가 적용됩니다. json/csv 모드는
  `--confirm` 없이 `CONFIRMATION_REQUIRED`(exit 1).

### Security
- `~/.kiwoom` 디렉토리 0700, `config.toml`·주문 원장·레코딩 파일 0600으로 생성.
  기존 설치본도 아무 명령 실행 시 일괄 조임 (`--record` 명시 경로는 제외)
- raw `kiwoom api` 주문성 호출 확인 게이트 (table: body 미리보기 + y/n, 자동화: `--confirm`)
- 프로필 이름 allowlist: 원장 파일명·키링 키로의 경로 조작 차단
- PyPI 배포를 Trusted Publishing(OIDC)으로 전환. 장기 API 토큰 제거
- main 브랜치 보호 룰셋 복원 (PR + CI 필수, force push/삭제 차단, 관리자 bypass)

## [2.7.0] - 2026-07-18

### Added
- `kiwoom find <키워드>`: 명령어 + API 통합 검색
- `kiwoom api list [키워드]`: API 레지스트리 목록/검색 (토큰 불필요)
- 사람이 읽는 옵션 값 (`--side sell`, `--period 1h` 등, account/market 19개 옵션). 기존 숫자 코드도 계속 허용
- `--all-pages` 상한 도달 테스트, 통합 명령 양쪽 실패 시 json 모드는 `UPSTREAM_ERROR` envelope + exit 2, table 모드도 동일하게 빨간 stderr 메시지 + exit 2 (이전엔 조용히 exit 0)

### Fixed
- `stock price`가 방향지시자 부호를 가격에 그대로 노출하던 문제 (하락 시 음수 가격 표시) + `-f json` envelope 미적용
- `--no-color`가 동작하지 않던 문제 (import 시점 Console 바인딩)
- 테이블 50행(차트 30행) 초과 시 무언 절단 → 안내 문구 표시
- `config setup`이 루트 `-p/--profile`을 무시하던 문제
- 미국 거래소 자동판별 호출(usa10098)과 주문 `--dry-run`의 시세 보조 호출이 전역 `--next-key`/`--all-pages` 커서를 소비하거나 `meta.cont`를 남기던 문제. 두 호출 모두 `internal`로 표시해 커서 계약에서 제외
- `find`가 사용자 입력·매칭 결과 값의 Rich 마크업을 이스케이프하지 않던 문제 (예: `kiwoom find "[/]"`가 `MarkupError`로 크래시)
- 금현물 주문 예시 종목코드 통일 (`M04020000`)

### Changed
- `describe`/`--help`의 choices가 숫자 코드 대신 human 이름을 노출 (json describe 소비자 주의)

## v2.6.0 (2026-07-17) 에이전트 계약 강화 (Tier-2)

**Breaking (json 모드만)**: `config set`/`config use`의 오류·성공 출력이
envelope로 바뀝니다 (기존엔 `-f json`에서도 일반 텍스트/에러였습니다).
`TOKEN_EXPIRED`(upstream 8005)의 exit code가 2 → **3**으로 바뀝니다
(인증 오류로 재분류: 재로그인 필요를 exit code만으로 구분 가능).

### Added
- 전역 `--next-key <값>` / `--all-pages`: 페이지네이션을 명시적으로 제어.
  `--all-pages`는 `cont-yn`이 끝날 때까지 반복해 리스트 필드를 병합(최대
  50페이지, 상한 도달 시 stderr 안내 + `meta.cont` 유지). 둘은 함께 쓸 수
  없음(UsageError). 주문 전송 명령은 두 플래그를 조용히 무시(방어적).
- `kiwoom describe --paths`: 경로+한줄설명 평면 목록만 반환하는 저비용
  발견 모드. `--depth N`으로 하위 명령 재귀 깊이 제한(전체 스키마 모드에서만
  적용되며 `--paths`와 함께 쓰면 무시됨).
- `meta.fields_unmatched`: `--fields`로 지정한 키 중 하나라도 매칭되지 않으면
  (부분 매칭 포함) 매칭 실패한 키 목록을 반환(오타 감지).
- `market` 명령 docstring에 사용 API ID 명시(예: `순위 정보 조회. (ka10016)`)
  (`describe`의 `help` 필드에서 바로 확인 가능).
- `config setup`/`config set`/`config use`/`account list`/`stream types`가
  json/csv 모드에서 대화형 프롬프트 없이 동작하고 envelope로 응답.
- 신규 오류 코드: `NOT_CONFIGURED`(설정 필요, exit 1), `LEDGER_BUSY`(멱등성
  원장 잠금 경합. 재시도, retryable, exit 2).

### Fixed
- 입력 오류(잘못된 인자/옵션 등)를 json/csv 모드에서 `err_console` 직접
  출력 대신 전부 `fail_input` envelope로 통일(29개 지점). stdout이 항상
  파싱 가능한 단일 문서가 되도록.
- `httpx.RequestError`(타임아웃 등 `ConnectError` 외 전송 오류)를
  `NETWORK_ERROR`(retryable)로 분류. 이전엔 처리되지 않아 traceback이
  노출될 수 있었음.
- `kiwoom stream *`의 `websockets` 미설치 시 오류가 json 모드에서
  `DEPENDENCY_MISSING`으로 exit 1 (이전엔 메시지만 출력하고 exit 0), `--raw`를
  json 모드와 함께 쓰면 `INVALID_INPUT`으로 exit 1.
- Ctrl+C로 스트림 종료 시 안내 메시지가 stderr로 출력(stdout 오염 방지).
- `order validate buy|sell`이 `--price`/`--type` 추론 규칙(`_resolve_order_type`)을
  실제 주문 경로와 동일하게 적용. 사전점검과 실제 전송의 판정이 어긋나지 않음.

## v2.5.1 (2026-07-17) 주문 안전 패치

### Fixed: 주문 안전 (v2.5.0 전수 리뷰 Tier 1)
- 모든 주문 명령(주식/신용/금현물/미국)에서 주문 **미리보기가 확인 프롬프트보다 먼저** 표시되도록 수정. 미국 주문은 자동 판별된 거래소까지 확인 전에 표시.
- `--price` 지정 + `--type` 미지정 시 **limit으로 추론** (기존: 조용히 시장가 전송). `--price` + 시장가 계열 `--type`은 INVALID_INPUT으로 거부.
- `account exchange apply`(환전)가 공용 confirm_gate를 사용하도록 수정. json/csv 모드에서 프롬프트 없이 CONFIRMATION_REQUIRED(exit 1), `--yes` 별칭 추가.
- 멱등성 원장 강화: `--client-order-id`가 주문 내용 fingerprint에 바인딩되어 같은 키+다른 주문은 **IDEMPOTENCY_CONFLICT**(exit 1)로 거부. 조회→전송→기록 구간 파일 잠금으로 동시 실행 시 중복 주문 방지.
- `stream`/`watch`가 `--profile`과 `KIWOOM_DOMAIN`을 REST 경로와 동일하게 존중 (기존: 항상 기본 프로필/설정 도메인으로 접속).

### Added
- 신용/금현물 주문에 `--dry-run`, `--client-order-id` 지원 (주식/미국 주문과 동일한 안전장치).

## v2.5.0 (2026-07-17) 에이전트 네이티브: 정규화 데이터·NDJSON 스트리밍·녹화/히스토리

**기존 `-f json` 소비자에게 breaking change**입니다. API 응답의 `data`가
정규화된 타입 있는 필드(canonical 영문 이름, 숫자는 number)로 바뀌고 원본은
`data.raw`로 이동했습니다 (리스트 응답은 `{"items": [...], "raw": [...]}`).
기존 키를 그대로 쓰던 스크립트는 `data.raw`에서 읽거나 canonical 이름으로
옮기면 됩니다. table/csv 모드와 exit code 계약(0/1/2/3)은 변경 없습니다.

### Added
- **정규화된 json data**: `cur_prc→price`, `stk_cd→symbol`, `flu_rt→change_pct` 등
  canonical 이름 + 타입 변환(부호 문자열 파싱 불필요), ABS 필드는
  `change_direction`(up/down) 동반, 날짜/시각은 ISO-8601(+09:00).
- **전역 `--fields a,b`**: json `data`(및 내부 리스트 요소)를 지정 키로 투영하고
  `raw`를 제거. 에이전트 토큰 절약.
- **`kiwoom describe [명령...]`**: 명령 트리/인자/옵션(타입·기본값·choices)
  자기서술. 도움말 파싱 대신 스키마로.
- **NDJSON 스트리밍**: `-f json`에서 모든 `stream` 명령이 REAL 이벤트당 compact
  envelope 한 줄을 출력. 종료조건 `--max-events N` / `--duration 30s|5m|2h` /
  `--until <ISO-8601>` 도달 시 exit 0. ws 오류는 envelope 오류 한 줄 + exit 2(인증 3).
- **녹화와 히스토리**: 모든 `stream` 명령의 `--record [경로]`가 이벤트를 NDJSON
  파일로 저장 (기본 `~/.kiwoom/data/<심볼>_<날짜>.ndjson`). `history list` /
  `history query CODE --from --to [--type]` / `history export CODE --dest
  sqlite|csv|parquet`.
- **AGENTS.md**: envelope·오류코드·안전장치·스트리밍의 기계 계약 문서.
- **benchmark/litmus.sh** + `docs/vs-official.md`: 모의투자 대상 재현 가능한
  litmus loop 증명 스크립트와 공식 CLI(kwcli) 대비 비교 문서. README 최상단에
  "AI-agent native" 섹션.

## v2.4.0 (2026-07-16) 에이전트 안전 주문 (dry-run · validate · 멱등성)

### Added
- **`--dry-run`** (buy/sell/modify/cancel): 전송 없이 전송될 body를 출력. `--confirm`보다 우선.
- **`order validate buy|sell`**: read-only 사전점검 (symbol_ok / market_open /
  sufficient_balance / price_ok). 실패 시 `VALIDATION_FAILED` + exit 1.
- **`--client-order-id` 멱등키**: 같은 키 재실행 시 재전송 없이 이전 응답을
  반환 (`idempotent_replay: true`). 원장: `~/.kiwoom/idempotency/<프로필>-<환경>.jsonl`.
- **구조화된 확인 게이트**: json/csv 모드에서 `--confirm` 없는 주문은 프롬프트
  대신 `CONFIRMATION_REQUIRED` 오류 + exit 1로 즉시 반환 (에이전트가 멈추지 않음).

### Fixed
- 미국주식 `stock info`의 `stex_tp` 오류 수정.
- 키체인 접근 불가 환경 안내가 `KIWOOM_TOKEN` 경로를 정확히 가리키도록 수정.

## v2.3.0 (2026-07-16) JSON 응답 envelope v1

`-f json`의 모든 응답(성공/실패)이 하나의 안정적인 envelope로 통일됩니다. **기존 `-f json` 소비자에게는 breaking change**입니다. 본문이 `data` 필드 아래로 이동했습니다 (`jq '.[]'` → `jq '.data[]'`). table/csv 모드와 exit code 계약(0/1/2/3)은 변경 없습니다.

### Added
- **JSON envelope v1**: `{"ok": bool, "schema": "v1", "data": ..., "meta": {...}, "error": ...}`. `meta`에 해석된 프로필, 도메인(prod/mock), 연속조회 커서(`cont`) 포함.
- **타입화된 에러**: `error`가 `{"code", "retryable", "message", "upstream_code"}`. 키움 공식 오류코드 32개 + HTTP 401/429/5xx를 stable enum(`TOKEN_EXPIRED`, `RATE_LIMITED`, `INVALID_INPUT`, `NOT_FOUND` 등)으로 분류. 에이전트가 메시지 파싱 없이 `error.code`로 분기하고 `retryable`로 재시도를 결정할 수 있습니다. README에 전체 코드 표.
- **연속조회(페이지네이션) 커서 노출**: 응답에 다음 페이지가 있으면 `meta.cont.next_key`로 노출되고 `kiwoom api <api_id> <body> --next-key <커서>`로 다음 페이지를 조회합니다.
- `auth login`/`auth logout`/`config profiles`도 json 모드에서 envelope를 출력합니다. login 응답의 토큰 원문은 env 모드에서만 포함됩니다.
- CLI 인자/옵션 오류도 json 모드에서 `INVALID_INPUT` envelope로 출력됩니다 (exit 1 유지). `api --raw`는 json 모드에서 envelope로 감싸되 `data`에 원본을 그대로 담습니다.

### Fixed
- **`auth login` 실패가 exit 0으로 삼켜지던 버그**: 발급 실패 시 exit 2와 에러 envelope(table 모드는 에러 메시지)를 반환합니다.

## v2.2.1 (2026-07-16) 에러 처리 개선

v2.2.0 실배포 테스트(샌드박스 셸)에서 발견된 두 이슈를 수정했습니다.

### Fixed
- **키체인 접근 불가 시 크래시 수정**: 키체인이 잠겨 있거나 비대화형 세션이라 쓸 수 없을 때(`config setup`, `auth login` 등) raw traceback 대신 친절한 안내(KIWOOM_TOKEN 환경변수 경로)를 출력하고 exit 1로 종료합니다. v2.1.1은 읽기 실패만 graceful했습니다.
- **토큰 부재 시 exit code 계약 준수**: 토큰이 없으면 요청을 보내기 전에 감지하여 문서화된 exit 3(인증필요) + `kiwoom auth login` 힌트를 출력합니다 (기존: authorization 헤더 없이 요청 후 서버 거절 → exit 2). `-f json`에서는 단일 JSON 에러 문서를 출력합니다.

## v2.2.0 (2026-07-16) 키체인 없는 환경 지원

### Added
- **`KIWOOM_TOKEN` 환경변수**: OS 키체인에 접근할 수 없는 환경(샌드박스 셸, CI, 컨테이너, AI 에이전트)에서 접근토큰을 환경변수로 전달할 수 있습니다. 설정 시 키체인 토큰보다 우선하며 `auth status`가 토큰 출처(키체인/환경변수)를 표시합니다. appkey/secretkey는 계속 환경변수를 지원하지 않습니다. 만료·폐기 가능한 접근토큰만 키체인 밖으로 나갑니다.
- **토큰 저장 방식 선택 (`token_storage`)**: `config setup`에서 keychain(기본)/env 중 선택합니다. env 모드에서는 `auth login`이 토큰을 키체인에 저장하지 않고 `export KIWOOM_TOKEN=...` 명령을 출력해 사용자가 직접 관리합니다. 이후 전환은 `kiwoom config set token_storage keychain|env`.

## v2.1.1 (2026-07-16) 자동화 안정성

### Fixed
- **stdout 순수성**: `-f json`/`-f csv` 모드에서 stdout이 항상 단일 파싱 가능 문서가 되도록 수정. 주문/환전 미리보기 패널·확인 프롬프트·안내 메시지·스트리밍 배너는 stderr로 출력됩니다 (table 모드는 변경 없음). `auth status`/`config show`가 `-f json`에서 JSON 문서를 출력합니다.
- **잠긴/없는 키체인에서 크래시 수정**: 헤드리스 서버, CI, 샌드박스 셸에서 `config show`, `auth status` 등 읽기 명령이 KeyringError 트레이스백 대신 "미설정"으로 정상 동작합니다.
- **exit code 계약 준수**: 잘못된 인자(옵션 값, 누락 인자)가 문서화된 대로 1을 반환합니다 (기존에는 Click 기본값 2로 API 오류와 구분 불가).
- `kiwoom api`: API 오류 시 사람용 텍스트 + exit 0 대신 전역 핸들러를 통해 JSON 에러 문서 + exit 2를 반환합니다.

## v2.1.0 (2026-07-15) 비밀번호 프롬프트 제거

### Changed
- **인증정보 저장 방식 변경 (breaking)**: 앱 자체 비밀번호/Fernet 암호화 계층을 제거하고 appkey/secretkey를 OS 키체인에 직접 저장합니다. `config setup`, `auth login`, `auth logout`에서 더 이상 비밀번호를 묻지 않습니다. 모든 명령이 프롬프트 없이 동작합니다 (AI 에이전트/자동화 친화).
- 기존 사용자는 업그레이드 후 `kiwoom config setup`을 한 번 다시 실행해야 합니다 (이전 암호화 형식 자동 감지 + 안내 메시지 표시).

### Removed
- `cryptography` 의존성 제거.

## v2.0.0 (2026-07-15) 미국주식 지원

키움 REST API의 미국주식 29개 엔드포인트를 기존 명령 체계에 그대로 통합한 메이저 릴리스입니다.
티커만 입력하면 시장을 자동 판별하므로, 미국 주문도 국내 주문과 똑같이 짧게 입력합니다.

> ⚠️ **라이선스 변경 (MIT → Source-Available)**: v2.0.0부터 **kiwoom-cli Source-Available License, Version 1.0**을 적용합니다.
> **개인**은 영리 목적(자기 계좌 매매 등)을 포함해 자유롭게 사용/수정/배포 가능(출처 표기만).
> **조직**이 영리 목적으로 사용할 경우 상용 라이선스가 필요하며 수정 후 영리 사용 시에는 상용 라이선스를 구매하거나 전체 코드를 동일 라이선스로 공개해야 합니다(어느 경우든 수정 소스를 Licensor에게 전달).
> v2.0 이전 릴리스는 계속 MIT로 제공됩니다. 자세한 내용은 [LICENSE](LICENSE)·[COMMERCIAL.md](COMMERCIAL.md) 참조.

### 새 기능

- **자동 시장 라우팅**: 6자리 숫자(005930)는 국내, 알파벳 티커(NVDA, BRK.B)는 미국으로 자동 판별. `--exchange nasdaq|nyse|amex`로 강제 지정 가능
- **미국주식 주문**: `order buy/sell/modify/cancel`이 미국 티커를 그대로 지원
  - 소수점 가격 (`--price 213.04`, 페니스톡 `0.0012`까지)
  - 미국 전용 주문유형: vwap/twap/vwap-limit/twap-limit/loc (매수·매도), moc/stop/stop-limit (매도 전용, `--stop` 가격)
  - 정정은 가격만(전량), 취소는 전량만. 키움 API 제약을 명확한 안내와 함께 처리
- **거래소 자동 판별**: usa10098 조회 + `~/.kiwoom/cache/us_exchanges.json` 캐시. 복수 상장 종목만 `--exchange` 필요
- **통합 계좌 뷰**: `account balance`가 국내+미국을 한 테이블로 보여줍니다. 종목별 USD/원화 병기, 통화별 소계, 원화 총평가액. `deposit/pnl/orders/history`도 동일하게 통합 (`--market kr|us`로 필터, 한쪽 실패 시 경고 후 나머지 표시)
- **미국 시세/차트**: `stock info/price/orderbook/search`(`--market us`)와 `stock chart tick~year` 6종 (`--krw` 원화 환산 옵션)
- **환전**: 새 `account exchange rate|estimate|apply` 서브그룹 (환율 조회/예상금액/신청, apply는 확인 게이트 필수)
- **주문가능수량**: `account orderable margin-qty NVDA --price 213.04`
- **USD 포매팅**: 소수점 4자리 보존, 후행 0 제거, 방향 부호 규칙 유지
- **AI/자동화 친화**: 통합 명령의 `--format json`이 단일 `{"kr", "us"}` 문서를 출력, exit code 계약 유지 (0=성공, 1=입력오류, 2=API오류)

### 변경 사항

- `order buy/sell/modify`의 `--price`/`PRICE`가 정수→실수 타입으로 변경 (국내 경로는 정수만 허용, 동작 동일)
- `account balance/deposit/pnl/orders/history`가 기본적으로 국내+미국 통합 표시 (`--market kr`로 기존 국내 전용 동작)
- SECURITY.md의 주문 안전 설명을 실제 동작(미리보기 + 대화형 확인 + `--confirm`)에 맞게 정정

### 내부

- 신규 패키지 `kiwoom_cli/commands/us/` (detect/order_ops/stock_ops/account_ops/exchange)
- API 레지스트리 188 → 217개 (REST), 테스트 155 → 245개
