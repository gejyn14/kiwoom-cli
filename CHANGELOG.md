# Changelog

## [2.12.0] - 2026-07-20

`market`의 rank·sector·theme·etf·elw·gold·program 41개 커맨드에서 숫자코드
옵션 116개를 human-readable 이름으로 전환했습니다(`--sort rise-rate`,
`--stk-cnd exclude-managed`, `--period six-months`, `--right-type call` 등).
전환한 자리는 raw 숫자코드도 그대로 받으므로 스펙 값을 쓰던 호출은 종전과
똑같이 동작하고, 기본값도 아래 Fixed 두 건을 빼면 전부 그대로입니다.

다만 이 116개 자리는 전환 전에 타입 제약이 없는 자유 텍스트였습니다 — 아무
문자열이나 받아 그대로 서버로 넘겼습니다. 지금은 스펙에 문서화된 값만
받으므로, 스펙에 없는 값을 보내던 호출은 이제 로컬에서 거부됩니다. 받아들이는
값의 집합이 줄어든 것이라 Breaking으로 분류합니다.

`stock`의 `daily-price`/`today-exec`/`today-volume`/`analysis price-cluster`/
`analysis open-change`/`analysis instant-volume`/`analysis vi-trigger`/
`analysis warrant`/`investor daily-trade`/`investor stock-institution`/
`investor daily-by-investor`/`investor by-stock`/`investor by-stock-total`
13개 커맨드의 옵션 31개에서도 같은 방식으로 숫자코드를 human-readable
이름으로 전환했습니다(`--display quantity`, `--when today`, `--session
after-hours`, `--stock-cond exclude-managed` 등). `stock investor
intraday`/`after-close`/`consecutive`, `stock analysis trader-analysis`
(`--date-type`/`--pot`/`--sort`), `stock credit available`는 이번 작업 전에
이미 human-readable였습니다(선행 fix 커밋들, 손대지 않았습니다). 이 중 8개는
전환 전에 자유 텍스트였고(`open-change`의 `--stock-cond`/`--credit-cond`/
`--amount-cond`/`--volume-cond`, `instant-volume`의 `--price-type`,
`vi-trigger`의 `--volume-type`/`--amount-type`, `daily-by-investor`의
`--investor-type`), 위 116개와 같은 이유로 Breaking입니다.

**Fixed**

- **`market rank` 8개 커맨드의 `--vol-type` 기본 전송값이 스펙 값이
  아니었습니다.** `new-highlow`(ka10016)/`limit`(ka10017)/
  `near-highlow`(ka10018)/`surge`(ka10019)는 `"0"` → `"00000"`,
  `orderbook-top`(ka10020)은 `"0"` → `"0000"`으로 고쳤습니다. 넷은 스펙의
  전체조회, `orderbook-top`은 장시작전(0주 이상)에 해당해 종전 의도인
  "거래량 필터 없음"이 그대로 유지됩니다. 여덟 API의 값 폭이 5자리 zero-pad /
  4자리 zero-pad / 무패딩 정수로 제각각인데 한 값을 공유하고 있었던 탓입니다.
  나머지 `orderbook-surge`(ka10021)는 `"0"` → `"1"`,
  `balance-rate-surge`(ka10022)/`volume-surge`(ka10023)는 `"0"` → `"5"`로
  고쳤습니다. 이 셋은 스펙에 전체조회 값이 없어 "거래량 필터 없음" 의도가
  유지되지 않으므로 아래 Breaking 절을 함께 보세요.
- **`market rank change`(ka10027)의 `--vol-cnd` 기본 전송값이 스펙 값이
  아니었습니다.** `"0"` → `"0000"`으로 고쳤습니다. 이 API의 거래량조건은
  4자리 zero-pad(`0000`~`1000`)만 받는데 `"0"`은 그 목록에 없었습니다. 스펙의
  전체조회 값이라 종전 의도인 "거래량 필터 없음"이 그대로 유지됩니다.
- **`stock analysis open-change`(ka10028)의 `--volume-cond` 기본 전송값이
  스펙 값이 아니었습니다.** `"0"` → `"0000"`으로 고쳤습니다. `market rank
  change`(ka10027)와 완전히 같은 결함 패턴입니다 — 이 API의 거래량조건도
  4자리 zero-pad만 받는데 `"0"`이 목록에 없었습니다. 스펙의 전체조회 값이라
  종전 의도인 "거래량 필터 없음"이 그대로 유지됩니다.

**Breaking**

- **전환한 116개 옵션이 스펙 밖의 값을 거부합니다(exit 1).** 종전에는 어떤
  문자열이든 그대로 전송하고 서버 판단에 맡겼지만, 이제 전송 전에 로컬에서
  `INVALID_INPUT`으로 막습니다. 스펙에 문서화된 raw 코드와 새 human-readable
  이름은 양쪽 다 통과하므로 정상적인 호출은 영향이 없고, 스펙에 없는 값을
  보내던 호출만 깨집니다. 값 목록이 형제 API끼리 다른 자리가 특히 위험합니다
  — 예를 들어 다섯 개 elw 커맨드를 3자리 권리구분 표 하나로 돌리던
  스크립트는 `change-rank`/`balance-rank`에서 깨집니다. 두 API는 스펙에
  `005`(EX) 코드 자체가 없어 `--right-type 005`가 종전에는 그대로 전송됐지만
  이제 거부됩니다(`surge`/`disparity`에서는 그대로 통과합니다). 같은 이유로
  `elw surge --right-type 5`(무패딩은 `search`용), `etf returns --period 9`,
  `gold chart-day --price-type 2`도 거부됩니다.
- **`--vol-type 0`이 ka10016~ka10023 8개 커맨드 전부에서, `--vol-cnd 0`이
  `market rank change`에서 거부됩니다(exit 1).** 위 Fixed 두 건에서 고친
  종전 기본값이라 help도 그 값을 암시했고, 스크립트에 박혀 있을 가능성이 가장
  높은 값입니다. 각 API의 스펙 값(`00000`/`0000`/`1`/`5` 등)이나
  `--vol-type all` 같은 human-readable 이름으로 바꿔야 합니다.
- **`orderbook-surge`(ka10021)/`balance-rate-surge`(ka10022)/
  `volume-surge`(ka10023)는 기본 결과가 좁아질 수 있습니다.** 이 셋은 스펙에
  전체조회 값 자체가 없어 최하단이 각각 `"1"`(천주 이상), `"5"`(5천주 이상),
  `"5"`(5천주 이상)입니다. 새 기본값은 실제 거래량 하한으로 동작하므로,
  서버가 종전 `"0"`을 관대하게 무필터로 처리하고 있었다면 `--vol-type` 없이
  부르던 호출의 결과 집합이 줄어듭니다. 종전 폭을 원하면 명시적으로 값을
  지정해야 합니다.
- **`stock analysis open-change`(ka10028)의 `--stock-cond`/`--credit-cond`/
  `--amount-cond`/`--volume-cond`, `stock analysis instant-volume`(ka10052)의
  `--price-type`, `stock analysis vi-trigger`(ka10054)의
  `--volume-type`/`--amount-type`, `stock investor
  daily-by-investor`(ka10058)의 `--investor-type`이 스펙 밖의 값을
  거부합니다(exit 1).** 전환 전에는 타입 제약이 없는 자유 텍스트였습니다 —
  위 116개 옵션과 같은 이유로 Breaking입니다. `--price-type`/
  `--volume-type`/`--amount-type`/`--investor-type`은 스펙에 정의된 값이
  전부 라벨을 갖고 있어 전체를 옮겼지만, `instant-volume`의
  `--volume-type`(`qty_tp`)은 스펙 코드 `3`/`5`의 라벨이 워크북·kwcli
  양쪽 모두 비어 있어 이번에는 전환하지 않고 자유 텍스트로 남겼습니다
  (전환하면 두 코드가 거부됩니다).
- **`market rank net-buyer`(ka10042)의 `--period`가 스펙 밖의 값을
  거부합니다(exit 1).** `stock analysis trader-analysis`(ka10043)의
  동일 필드 `--days`는 v2.11.0부터 이미 `HumanChoice`로 배포돼 있었는데,
  `--period`는 그때 자유 텍스트로 남아 `--period 999` 같은 값도 검증 없이
  그대로 전송되고 있었습니다. 이번에 두 필드가 같은 값 목록
  (5/10/20/40/60/120, 워크북으로 character-for-character 동일함을 확인)을
  쓰는 걸 근거로 `--period`도 `HumanChoice`로 끌어올려 둘을
  `TRADER_ANALYSIS_PERIOD_5_120` 하나로 통일했습니다 — 스펙 숫자 코드와
  `5d`/`10d`/`20d`/`40d`/`60d`/`120d` human 이름은 그대로 통과하고, 목록
  밖의 값만 이제 로컬에서 거부됩니다.
- **`stock investor by-stock-total`(ka10061)의 `--trade`가 `1`/`2`를 더
  이상 받지 않습니다.** 스펙의 `trde_tp`는 `0`(순매수) 단일값뿐인데 기존
  코드는 `click.Choice(["0","1","2"])`로 스펙에 없는 `1`/`2`까지 받고
  있었습니다. `HumanChoice({"net-buy":"0"})`로 좁히며 그 두 값이 거부되게
  됐습니다 — 이미 `click.Choice`였던 자리가 값 집합이 줄어드는 경우라
  Breaking입니다(이미 `click.Choice`였더라도 값 집합이 줄면 Breaking입니다).

이번 릴리스에서 human-readable 이름을 받게 된 옵션을 명령 그룹별로 정리하면
다음과 같습니다. **스펙에 있는 raw 숫자코드는 두 구분 모두에서 계속
통과합니다** — "Breaking"은 스펙 밖의 값만 이제 로컬에서 거부된다는 뜻입니다.
다만 스펙 밖에는 종전 기본값이던 `--vol-type 0`/`--vol-cnd 0`, `elw
change-rank`/`balance-rank`의 `--right-type 005`, `by-stock-total`의
`--trade 1`/`2`처럼 실제로 쓰이던 숫자 코드도 들어갑니다. 쓰던 값이 여기
해당하는지는 위 Breaking 절에서 확인하세요.

| 그룹 | 옵션 수 | 구분 |
| --- | ---: | --- |
| `market rank` 신고저가~거래량급증(ka10016~23, 8개 커맨드) | 39 | Breaking(자유 텍스트 이력) |
| `market rank` 등락률~상위거래원(ka10027/29/31/33/34/35/36/37/39, 9개 커맨드) | 28 | Breaking(자유 텍스트 이력) |
| `market rank` 순매수~외국계기관(ka10042/62/65/98, ka90009, 5개 커맨드) | 17 | Breaking(자유 텍스트 이력) |
| `market sector`(5개 커맨드) | 5 | Breaking(자유 텍스트 이력) |
| `market theme`(1개 커맨드) | 2 | Breaking(자유 텍스트 이력) |
| `market etf`(2개 커맨드) | 4 | Breaking(자유 텍스트 이력) |
| `market elw`(5개 커맨드) | 15 | Breaking(자유 텍스트 이력) |
| `market gold`(4개 커맨드) | 4 | Breaking(자유 텍스트 이력) |
| `market program`(2개 커맨드) | 2 | Breaking(자유 텍스트 이력) |
| **`market` 소계(41개 커맨드)** | **116** | **전부 Breaking(자유 텍스트 이력)** |
| `stock`(13개 커맨드 중 전환 전 자유 텍스트였던 자리) | 8 | Breaking(자유 텍스트 이력) |
| `stock`(같은 13개 커맨드 중 이미 `click.Choice`였는데 값 집합이 줄어든 자리) | 1 | Breaking(값 집합 축소) |
| `stock`(같은 13개 커맨드 중 이미 `click.Choice`였고 값 집합이 그대로인 자리) | 22 | Non-breaking(순수 확장) |
| **`stock` 소계(13개 커맨드)** | **31** | **Breaking 9 / Non-breaking 22** |
| **합계** | **147** | **Breaking 125 / Non-breaking 22** |

`market`의 116개는 전부 자유 텍스트에서 전환된 자리라 예외 없이 Breaking이고,
`stock`의 31개만 두 구분이 섞여 있습니다 — 어느 쪽이었는지는 위 Breaking
섹션(자유 텍스트 8개와 값 집합이 줄어든 `by-stock-total`의 `--trade`를 목록으로
명시)과 아래 Non-breaking 섹션(나머지 22개) 본문에서 커맨드·옵션 단위로
확인할 수 있습니다. 이 표에 넣지 않은 항목:
`--exchange`를 `3:통합`까지 넓힌 4개 커맨드와 `stock chart
intraday-investor`의 `--market` 확대는 값 집합을 넓힌 것이지 raw 코드를
human 이름으로 바꾼 게 아니라 별도로 아래에 적었고, `--vol-type`/`--vol-cnd`
기본값 교정 10곳은 위 Fixed에 있습니다.

**Non-breaking (사람이 읽는 이름 추가, 하위호환)**

- `market rank`의 신고저가~거래량급증 8개 커맨드(ka10016~ka10023) 옵션 39개가
  human-readable 이름을 받습니다(`--stk-cnd exclude-managed`, `--sort
  spike-rate`, `--credit all-financing` 등). 값 목록이 API마다 다른 자리
  (`stk_cnd`/`sort_tp`/가격조건)는 형제 API에만 있는 이름이 거부되는지까지
  테스트로 못 박았습니다.
- `market rank`의 `change`/`expected-change`/`prev-volume`/`credit-ratio`/
  `foreign-period`/`foreign-consecutive`/`foreign-exhaust`/`foreign-broker`/
  `broker-top`(ka10027/29/31/33/34/35/36/37/39) 9개 커맨드의 옵션 28개가
  human-readable 이름을 받습니다(`--sort rise-rate`, `--type net-buy`,
  `--period previous` 등). `ka10034`/`ka10036`/`ka10037`의 `--period`(`dt`)는
  값이 완전히 동일해 하나의 코드북으로 수렴시켰습니다.
- `market rank`의 `net-buyer`/`same-net-trade`/`investor-top`/
  `afterhours-change`/`foreign-inst`(ka10042/62/65/98, ka90009) 5개 커맨드의
  옵션 16개가 human-readable 이름을 받습니다(`--date-type start-end`,
  `--investor pension`, `--vol-cnd 5k+` 등). `net-buyer`(ka10042)의
  `--date-type`/`--pot-type`/`--sort`는 워크북으로 값이 완전히 동일함을
  확인해 기존 `stock analysis trader-analysis`(ka10043)의 코드북을 그대로
  공유합니다. `investor-top`(ka10065)/`foreign-inst`(ka90009)의
  `--unit`(`amt_qty_tp`)도 같은 이유로 서로 공유합니다. `net-buyer`의
  `--period`(`dt`)도 `trader-analysis`의 `--days`와 코드북을 공유하도록
  전환했지만, 전환 전이 자유 텍스트였던 탓에 값 목록이 좁아지는 쪽이라
  위 Breaking 절에 따로 적었습니다.
- `sector investor`(ka10051)의 `--unit`(`amt_qty_tp`)이 human-readable
  이름을 받습니다(`--unit quantity` 등). `stock investor consecutive`
  (ka10131)와 코드북이 동일해(0:금액,1:수량) 기존 `AMT_QTY_TP_0_1`을
  공유합니다.
- `sector current`/`sector stocks`/`sector daily`(ka20001/02/09)의
  `--market`(`mrkt_tp`)이 human-readable 이름을 받습니다(`kospi`/`kosdaq`/
  `kospi200`). 세 API 모두 워크북 문구가 character-for-character 동일해
  하나의 코드북(`SECTOR_PRICE_MARKET`)으로 수렴시켰습니다. 기존
  `MARKET_KOSPI_KOSDAQ`(kospi/kosdaq 2값)의 진짜 상위집합이지만 재사용하지
  않고 별도 상수를 새로 뒀습니다.
- `sector codes`(ka10101)의 `--market`이 human-readable 이름 5개
  (`kospi`/`kosdaq`/`kospi200`/`kospi100`/`krx100`)를 받습니다. 위
  `SECTOR_PRICE_MARKET`의 진짜 상위집합이라 별도 이름(`SECTOR_CODES_MARKET`)
  으로 분리했습니다 — `sector current`/`stocks`/`daily`에서 `kospi100`/
  `krx100`을 주면 거부됩니다(그 3개 API 스펙엔 없는 값입니다).
- `theme groups`(ka90001)의 `--type`(`qry_tp`)/`--sort`(`flu_pl_amt_tp`)가
  human-readable 이름을 받습니다(`--type stock`, `--sort change-top` 등).
  `sector index`(ka20003)의 `--inds-cd`, `sector chart tick/minute`
  (ka20004/05)의 `--scope`, `theme groups`/`theme stocks`의 `--date-type`은
  각각 업종코드 조회 대상, 자기서술적 수량, 자유 입력 일수(1~99일)라 전환
  대상이 아닙니다(raw 텍스트 유지).
- `etf returns`(ka40001)의 `--period`(`dt`), `etf all`(ka40004)의
  `--tax-type`/`--nav`/`--taxable`이 human-readable 이름을 받습니다
  (`--period six-months`, `--tax-type foreign` 등). `etf all`의
  `--company`(`mngmcomp`)/`--index`(`trace_idex`)는 스펙에 예시 몇 개+
  "기타운용사"만 있는 개방형 코드북이라 전환 대상이 아닙니다(raw 텍스트
  유지, kwcli도 동일하게 자유 코드로 둡니다).
- `elw surge`(ka30001)의 `--type`/`--time-type`/`--vol-type`/`--right-type`/
  `--exclude-expired`, `elw disparity`(ka30004)의 `--right-type`/
  `--exclude-expired`, `elw search`(ka30005)의 `--right-type`/`--sort`,
  `elw change-rank`(ka30009)와 `elw balance-rank`(ka30010)의 `--sort`/
  `--right-type`/`--exclude-expired`가 human-readable 이름을 받습니다.
  `--issuer`(`isscomp_cd`)/`--underlying`(`bsis_aset_cd`)/`--lp`(`lpcd`)는
  예시 5~6개 발행사/지수만 있고 전체 코드표가 없는 개방형 필드라 전환하지
  않았습니다(raw 텍스트 유지).
  - `--exclude-expired`(거래종료ELW제외)는 `elw surge`/`elw broker-top`/
    `elw disparity`/`elw change-rank`/`elw balance-rank` 5개 커맨드가 워크북
    확인 결과 값이 완전히 동일해(`include`=0, `exclude`=1) 하나의 상수
    (`EXCLUDE_ENDED_ELW`)로 수렴시켰습니다. `elw broker-top`(ka30002)은
    v2.11.0에서 이미 HumanChoice였는데, 이번에 상수 이름만
    `EXCLUDE_ENDED_ELW`로 바뀌었습니다(전송값은 그대로 `include`=0/
    `exclude`=1이라 사용자에게 보이는 동작 변화는 없습니다).
  - `--right-type`(권리구분)은 자릿수/EX 포함 여부가 API마다 달라 3개
    상수로 분리했습니다: `elw surge`/`elw disparity`(3자리 zero-pad, EX
    포함), `elw search`(무패딩, EX 포함), `elw change-rank`/
    `elw balance-rank`(3자리 zero-pad, EX 없음 — 두 API 스펙 모두 `005`
    코드 자체가 없습니다. `ex`를 주면 거부됩니다).
- `gold chart-tick`(ka50079)/`chart-day`(ka50081)/`chart-week`(ka50082)/
  `chart-month`(ka50083)의 `--price-type`(`upd_stkpc_tp`)이 human-readable
  이름을 받습니다(`raw`/`adjusted`).
- `program cumulative`(ka90007)/`program stock-time`(ka90008)의
  `--unit`(`amt_qty_tp`)이 human-readable 이름을 받습니다(`amount`/
  `quantity`). `program time-trend`/`program daily-trend`(ka90005/ka90010)는
  v2.11.0에서 이미 전환돼 있습니다.
- `gold chart-minute`(ka50080)의 `--price-type`과 `program stock-daily`
  (ka90013)의 `--unit`은 raw 텍스트로 남겼습니다. 둘 다 기존 기본값이 빈
  문자열인데 `HumanChoice`에는 빈 문자열에 대응하는 이름을 둘 수 없어,
  감싸면 기본 호출 자체가 깨집니다. 빈 문자열이 아닌 기본값을 새로 만들면
  전송 바이트가 바뀌고요. 옵션을 선택형으로 바꿔 값이 없을 때 키를 아예
  빼는 방식(ka10038 `dt`와 같은 모양)이면 이름도 주고 생략 의미도 지킬 수
  있는데, 그건 전송 바이트가 바뀌는 변경이라 별도 작업으로 미뤘습니다.
- `market rank volume`(ka10030)/`market program arbitrage-balance`
  (ka90006)/`market program cumulative`(ka90007)/`market etf all`(ka40004)의
  `--exchange`가 `all`(통합, `stex_tp`=3)을 받습니다. 네 API 모두 워크북에서
  `3:통합`을 직접 확인했습니다. 기존 `KRX`/`NXT` 호출과 기본값(`KRX`)은
  그대로 동작하는 순수 확대(widening)입니다 — `rank amount`(ka10032)가
  v2.11.0에서 먼저 넓혀진 것과 같은 모양으로 맞췄습니다.
- `stock daily-price`(ka10086)의 `--display`가 human-readable 이름을
  받습니다(`quantity`/`amount`). 기존 `AMT_QTY_TP_0_1`(0:금액,1:수량)과
  키 집합은 같지만 극성이 정반대(0:수량,1:금액)라 별도 상수
  (`DAILY_PRICE_DISPLAY`)를 뒀습니다.
- `stock today-exec`(ka10084)/`stock today-volume`(ka10055)의 `--when`이
  human-readable 이름을 받습니다(`today`/`previous`). 두 API 모두 워크북에서
  값이 character-for-character 동일함을 확인해 하나의 코드북
  (`TODAY_PREV_1_2`)으로 수렴시켰습니다. 다른 today/previous 계열 상수
  (`today`:0,`previous`:1)와는 극성이 반대라 절대 합치지 않았습니다.
  `today-exec`의 `--mode`(`tic_min`)도 human-readable 이름을 받습니다
  (`tick`/`minute`).
- `stock analysis price-cluster`(ka10025)의 `--include-current`가
  human-readable 이름을 받습니다(`yes`/`no`).
- `stock analysis open-change`(ka10028)의 `--sort`/`--include-limit`/
  `--direction` 3개 옵션이 human-readable 이름을 받습니다(`--sort open` 등).
  나머지 `--stock-cond`/`--credit-cond`/`--amount-cond`/`--volume-cond` 4개는
  전환 전이 자유 텍스트라 위 Breaking 절에 있습니다. `--amount-cond`
  (`trde_prica_cnd`)는 `market rank change`(ka10027)의
  `--amount-cond`(`trde_prica_cnd`)와 값이 완전히 동일하지만(구분 불가),
  `market rank volume`(ka10030)의 `trde_prica_tp`와는 키 집합이
  겹치면서도 `50m` 값이 다른 극성 해저드라 절대 합치지 않았고 리터럴로
  핀 고정했습니다.
- `stock analysis instant-volume`(ka10052)의 `--market`/`--price-type`이
  human-readable 이름을 받습니다(`--market kospi`, `--price-type
  under-1k` 등). `--market`(`mrkt_tp`)은 이 코드베이스에서 4번째로 확인된
  서로 다른 `mrkt_tp` 코드북입니다(전체=0,코스피=1,코스닥=2,종목=3 — 표준
  `MARKET_ALL`(000/001/101)과도, sector 계열의 0/1/2와도 순서가 다릅니다).
- `stock analysis vi-trigger`(ka10054)의 `--session`/`--trigger-type`/
  `--volume-type`/`--amount-type`/`--direction` 5개 옵션이 human-readable
  이름을 받습니다. `--session`(`bf_mkrt_tp`)은 `market rank volume`
  (ka10030)의 `mrkt_open_tp`와 `all`/`regular`는 값이 같지만
  `after-hours`만 다른(2 대 3) 극성 해저드라 리터럴로 핀 고정했습니다.
- `stock analysis warrant`(ka10011)의 `--type`이 human-readable 이름을
  받습니다(`all`/`warrant-security`/`warrant-certificate`).
- `stock investor daily-trade`(ka10044)의 `--trade`가 human-readable
  이름을 받습니다(`net-sell`/`net-buy`). `market rank broker-top`
  (ka10039)의 `--type`(`net-buy`:1,`net-sell`:2)과 극성이 정반대인 클러스터
  (`net-sell`:1,`net-buy`:2)라 리터럴로 핀 고정했고, 별도 이름
  (`INVESTOR_DAILY_TRADE_SIDE`)을 새로 뒀습니다.
- `stock investor stock-institution`(ka10045)의 `--inst-price`/
  `--foreign-price`가 human-readable 이름을 받습니다(`buy`/`sell`, 두
  옵션이 코드북을 공유합니다).
- `stock investor daily-by-investor`(ka10058)의 `--trade`/`--investor-type`
  이 human-readable 이름을 받습니다. `--trade`는 `daily-trade`(ka10044)와
  같은 극성 해저드가 있어 별도 이름(`DAILY_BY_INVESTOR_TRADE_SIDE`)으로
  분리했습니다.
- `stock investor by-stock`(ka10059)의 `--amount-qty`/`--trade`/`--unit`이
  human-readable 이름을 받습니다. `--amount-qty`/`--trade`는 기존
  `AMT_QTY_TP_1_2`/`TRDE_TP_NET_BUY_BUY_SELL`을 그대로 공유합니다(두
  상수 모두 이 API를 미래 확장 대상으로 이미 예약해 두고 있었습니다).
  `--unit`은 `stock investor by-stock-total`(ka10061)과 코드북을 공유하는
  새 상수(`INVESTOR_BY_STOCK_UNIT`)를 씁니다.
- `stock investor by-stock-total`(ka10061)의 `--amount-qty`/`--unit`이
  human-readable 이름을 받습니다(위와 동일한 상수 공유).
- `stock investor program-top`(ka90003)의 `--trade`/`--amount-qty`가
  human-readable 이름을 받습니다(`--trade net-buy`, `--amount-qty
  quantity` 등). `--amount-qty`는 기존 `AMT_QTY_TP_1_2`를 공유합니다.
  `--trade`(`PROGRAM_TOP_SIDE`)는 `market rank broker-top`(ka10038)의
  `--type`과 값이 완전히 동일해 구분 불가지만, `elw broker-top`(ka30002)
  등 여러 API의 동명 필드와는 키 집합은 같고 극성이 반대라 리터럴로 핀
  고정했고, `market rank foreign-period`(ka10034)의 상위집합(`net-trade`
  값 추가)이기도 해 거부 테스트로 방어했습니다.
- `stock chart tick`(ka10079)/`minute`(ka10080)/`day`(ka10081)/
  `week`(ka10082)/`month`(ka10083)/`year`(ka10094)의 `--adjusted`가
  human-readable 이름을 받습니다(`raw`/`adjusted`). 여섯 API 모두
  워크북에서 값이 character-for-character 동일함을 확인해 하나의 코드북
  (`CHART_ADJUSTED_PRICE`)으로 수렴시켰습니다. `market gold
  chart-tick/day/week/month`의 `GOLD_PRICE_TYPE`과도 값이 완전히
  같지만(구분 불가) 금현물과 국내주식은 별개 상품군이라 상수는
  분리했습니다. `--range`(`chart tick`)/`--interval`(`chart minute`)는
  값과 라벨이 동일한 자기서술적 수량 프리셋이라 전환 대상이
  아닙니다(raw 텍스트 유지).
- `stock chart investor`(ka10060)의 `--amount-qty`/`--trade`/`--unit`이
  human-readable 이름을 받습니다. 세 옵션 모두 기존
  `AMT_QTY_TP_1_2`/`TRDE_TP_NET_BUY_BUY_SELL`/`INVESTOR_BY_STOCK_UNIT`을
  그대로 공유합니다(세 상수 모두 이 API를 미래 확장 대상으로 이미
  예약해 두고 있었습니다).
- `stock chart intraday-investor`(ka10064)의 `--amount-qty`/`--trade`가
  human-readable 이름을 받습니다(위와 동일한 상수 공유).
- `stock chart intraday-investor`(ka10064)의 `--market`이 `all`(전체,
  `mrkt_tp`=`000`)을 받습니다. 스펙 값은 `000:전체, 001:코스피, 101:코스닥`
  셋인데 기존 `click.Choice(["kospi","kosdaq"])`는 `전체`에 아예 도달할 방법이
  없었습니다(이번 전환 전부터 있던 결함입니다). 기존 `kospi`/`kosdaq` 호출과
  기본값(`kospi`)은 그대로 `001`을 보내는 순수 확대(widening)입니다 —
  `market rank volume` 등의 `--exchange` 스윕과 같은 종류의 수정입니다.
- `stock lending trend`(ka10068)/`lending by-stock`(ka20068)의 `--all`은
  전환하지 않았습니다. 두 API 모두 스펙에 값이 하나만 문서화돼 있어
  (각각 `1:전체표시`, `0:종목코드 입력종목만 표시`) 반대쪽 코드를 확인할
  수 없습니다 — raw 텍스트로 남겼습니다(자유 텍스트 그대로라 breaking
  아닙니다).
- `market`의 API 약어 옵션 5개(`--stk-cnd`/`--vol-cnd`/`--price-cnd`/
  `--amount-cnd`/`--inds-cd`)에 human 이름 별칭을 추가했습니다
  (`--stock-cond`/`--volume-cond`/`--price-cond`/`--amount-cond`/
  `--sector-code`). `--help`에는 새 이름이 대표로 뜨지만 구 이름도 계속
  통합니다 — 전송값은 그대로입니다.
- `account orders detail`(kt00007)/`orders status`(kt00009)/`history
  transactions`(kt00015)의 `--exchange`가 `all`(전체, `dmst_stex_tp`=`%`)을
  받습니다. 기존 `%`/`KRX`/`NXT`/`SOR`(kt00015는 `SOR` 제외) 호출과
  기본값은 그대로 동작하는 순수 확대(widening)입니다. kt00007/kt00009는
  `SOR`을 받지만 kt00015는 스펙에 없어 계속 거부됩니다 — 두 자리를
  하나의 상수로 합치지 않고 `ACCOUNT_EXCHANGE_WITH_SOR`/
  `ACCOUNT_EXCHANGE_NO_SOR`로 분리했습니다.


## [2.11.0] - 2026-07-19

`market rank volume`(ka10030)의 `--include-managed` help 문구가 스펙과 정반대였고,
`market rank amount`(ka10032)는 극성이 반대인 동일 이름 옵션을 그대로 쓰고
있었습니다. `market rank broker-by-stock`(ka10038)은 `--period`/`--from`·`--to`를
함께 줘도 기간(`dt`)이 항상 우선하고 있었고, `market elw broker-top`(ka30002)의
`--issuer` 기본값은 자릿수부터 틀린 값(12자리, 필드는 3자리)을 매번 전송하고
있었습니다. 네 곳 모두 교정하고, 이 참에 두 명령의 나머지 자유 텍스트 옵션도
human-readable 이름으로 전환했습니다.

`market program time-trend`(ka90005)/`market program daily-trend`(ka90010)의
`--market`이 스펙에 정의되지 않은 코드를 보내고 있었고, 정정과 함께
`--unit`/`--tick-type`에 human-readable 이름을 추가했습니다(하위호환).

`stock investor after-close`(ka10066)의 `--trade` 값이 스펙과 반대였고, 정정과
함께 두 옵션에 raw 숫자코드와 함께 쓸 수 있는 human-readable 이름을
추가했습니다(하위호환).

`stock investor consecutive`(ka10131)의 `--amount-qty` 값이 스펙과 반대였고,
정정과 함께 세 옵션에 raw 숫자코드와 함께 쓸 수 있는 human-readable 이름을
추가했습니다(하위호환).

`stock investor intraday`(ka10063)는 요청 바디 6개 필드 중 5개가 스펙과 어긋나
있었습니다. 정정과 함께 네 옵션에 raw 숫자코드와 함께 쓸 수 있는
human-readable 이름을 추가했습니다(하위호환).

`stock credit inquiry`(kt20017)는 필수 필드를 받을 방법이 없어 `{}`만
전송했고, `stock credit available`(kt20016)도 필수 `mrkt_deal_tp`를
누락하고 있었습니다.

`stock daily`(ka10005)가 스펙에 없는 `qry_tp` 필드를 지어내 보내고 있었습니다.
이번 릴리스에서 유일하게 "원래 되던 것이 안 되는" breaking 변경입니다 —
위 항목들과 달리 옵션 자체가 제거됩니다.

`stock analysis trader-analysis`(ka10043)는 `--from`/`--to`가 이미
`required=True`인데도 `--date-type`(`qry_dt_tp`) 기본값이 `"0"`(기간으로 조회)이라
그 필수 날짜를 API가 무시하고 있었고, `--broker`(`mmcm_cd`, Required=Y)는
기본값이 빈 문자열이었습니다. 두 곳을 고치고, 나머지 원시 숫자 코드 옵션
(`--date-type`/`--pot`/`--sort`/`--days`)도 human-readable 이름으로 전환했습니다.

미국주식 주문(`order buy`/`sell`, ust20000/ust20001)에서 지정가 계열
(`limit`/`vwap-limit`/`twap-limit`/`loc`/`stop-limit`)에 `--price`를 주지 않으면
`ord_uv=""`로 조용히 전송되고 있었습니다. 이 유형은 미국·국내·금현물 주문
경로가 반복해서 갖고 있던 같은 버그의 **세 번째 인스턴스**입니다 — "가격을
쓰지 않는 유형에 `--price`를 준 경우"는 이미 막고 있었지만, 반대 방향인
"가격이 필수인 유형에 `--price`가 없는 경우"는 막지 않았습니다. 금현물
(kt50000/kt50001)은 v2.10.1에서 이미 같은 가드를 받았습니다.

**Fixed**

- **`market rank volume`(ka10030) `mang_stk_incls`(관리종목포함) help가 스펙과
  반대였습니다.** 스펙은 `0:관리종목 포함, 1:관리종목 미포함`인데 help 문구는
  `"(0=미포함, 1=포함)"`이라고 정반대로 적혀 있었습니다. 실제 기본값(`"0"`)
  전송 자체는 안 바뀌었지만(코드값은 원래도 `"0"`), 사용자가 문구를 믿고
  값을 뒤집어 지정하면 반대 결과를 받았습니다. 이번에 옵션을
  `--stock-condition`(`STOCK_CONDITION`, 15개 값)으로 바꾸며 스펙대로 고쳤습니다.
- **`market elw broker-top`(ka30002) `--issuer`의 기본값이 12자리(`"000000000000"`)
  였는데 스펙(`isscomp_cd`)은 길이 3입니다.** 형제 ELW 커맨드에서 복붙된
  값으로, 지정하지 않고 호출하면 매번 무효한 발행사코드를 그대로 전송하고
  있었습니다. 기본값을 제거하고 필수 옵션으로 바꿨습니다.
- **`market rank broker-by-stock`(ka10038)에서 `--from`/`--to`(기간 조회)를 줘도
  `dt`가 항상 함께 전송돼 기간 조회가 무시되고 있었습니다.** 스펙은 "시작일자와
  종료일자로 조회를 원하는 경우 기간(dt)값은 빈값으로 설정"이라고 명시하는데,
  기존 코드는 `dt` 기본값(`"1"`)을 항상 보냈습니다. 이제 `--from`/`--to`가
  주어지면 `dt` 키 자체를 body에서 제외합니다(빈 문자열이 아니라 키 제외 —
  CLI로 직접 확인).
- **`--market`(`mrkt_tp`)이 스펙에 없는 코드를 보내고 있었습니다.** ka90005/
  ka90010 스펙(Request Body, `docs/미국 REST API 문서.xlsx`)의 `mrkt_tp`는
  길이 10의 P-코드이고 값이 `stex_tp`(거래소구분)와 **연동**됩니다(코스피
  -1:`P00101`, -2:`P001_NX01`, -3:`P001_AL01`; 코스닥-1:`P10102`,
  -2:`P101_NX02`, -3:`P101_AL02`). 기존 코드는 `--market`이 자유 텍스트였고
  기본값 `"0"`을 그대로 전송했는데, 이는 형제 API인 ka90007
  (`0:코스피,1:코스닥`)의 코드북에서 복붙된 값으로 이 두 엔드포인트에는
  애초에 정의되어 있지 않았습니다.
- ka90010 스펙 시트는 코스닥+거래소구분값3을 `P001_AL02`로 적어 ka90005의
  `P101_AL02`와 모순됩니다. 이 모순은 워크북뿐 아니라 키움 공식 GitHub
  저장소(`kiwoom_docs/시세.md`, Postman 컬렉션, examples 스크립트,
  `kiwoom_api_spec.json`) 전체에서 동일하게 나타나, 키움 자체 소스로는
  어느 쪽이 오타인지 판정할 수 없었습니다. 코스닥 코드가 전부 `P101_`
  접두사라는 점에 근거해 두 엔드포인트 모두 `P101_AL02`로 통일했습니다 —
  이건 검증된 사실이 아니라 판단이며, 근거는
  `kiwoom_cli/commands/_constants.py`의 `PROGRAM_MARKET_BY_EXCHANGE` 주석에
  남겨 두었습니다.
- **`--trade` 기본값이 실제로는 순매도(2) 데이터를 반환하고 있었습니다.**
  스펙(ka10066 Request Body)은 `trde_tp`를 `0:순매수, 1:매수, 2:매도`로
  정의하는데, 기존 코드는 `Choice(["1","2"])`에 `default="2"`였고 help는
  `1=순매도, 2=순매수`라고 적어 실제 동작과 정반대로 안내했습니다. 진짜
  순매수 코드인 `0`은 Choice 목록에 없어 애초에 지정할 수 없었습니다.
- **`--amount-qty` 기본값이 실제로는 수량(1) 데이터를 반환하고 있었습니다.**
  스펙(ka10131 Request Body)은 `amt_qty_tp`를 `0:금액, 1:수량`으로 정의하는데,
  기존 코드는 `Choice(["1","2"])`에 `default="1"`이었고 help는 `1=금액,
  2=수량`이라고 적어 실제 동작과 어긋났습니다(전송값 `1`은 스펙상 수량이지
  help가 말한 금액이 아니었습니다). 스펙에 없는 값 `2`도 Choice 목록에는
  올라 있었습니다.
- **`--investor-type`(`invsr`) 기본값이 스펙 밖 값 `"1000"`을 보내고
  있었습니다.** ka10063 스펙(Request Body)의 `invsr`는 Length=1인
  `6:외국인, 7:기관계, 1:투신, 0:보험, 2:은행, 3:연기금, 4:국가, 5:기타법인`
  코드북인데, 기존 기본값 `"1000"`은 다른 API(ka10058)의 `invsr_tp`
  코드북을 복붙한 것이라 길이부터 이 엔드포인트에 정의되지 않은 값이었습니다.
- **`--market`(`mrkt_tp`)이 `000:전체`를 지정할 방법이 없었습니다.** 기존
  코드는 `kospi`/`kosdaq` 두 값만 허용했습니다(`MARKET_TWO`). 스펙에는
  `000:전체, 001:코스피, 101:코스닥` 세 값이 있어 `MARKET_ALL`로
  교체했습니다.
- **`--amount-qty`(`amt_qty_tp`)가 자유 텍스트였습니다.** 스펙상 값이
  `1: 금액&수량` 하나뿐인데 자유 텍스트 `default="1"`이라 임의 값을 그대로
  전송할 수 있었습니다. 전송값 자체(`"1"`)는 맞았으므로 동작 변화는
  없습니다.
- **`--foreign-all`(`frgn_all`)/`--simultaneous`(`smtm_netprps_tp`)가 원시
  코드 `0`/`1`만 노출했습니다.** 둘 다 스펙상 `1:체크, 0:미체크`인 동일
  코드북이라 공용 상수 하나(`CHECK_YES_1_NO_0`)로 정리했습니다.
- `--exchange`(`stex_tp`)는 이미 `EXCHANGE_ALL`(`1:KRX, 2:NXT, 3:통합`)로
  스펙과 정확히 일치해 이번 변경 대상이 아닙니다.
- **`credit inquiry`가 필수 `stk_cd`를 아예 보내지 않아 호출 자체가
  성립하지 않았습니다.** kt20017 Request Body는 `stk_cd`(Required=Y)
  하나뿐인데 커맨드에 이를 받을 인자/옵션이 없어 항상 `{}`를 전송했고,
  API가 이를 거부했습니다. 이제 종목코드를 위치 인자로 받아
  `{"stk_cd": <code>}`를 전송합니다.
- **`credit available`이 필수 `mrkt_deal_tp`를 누락했습니다.** kt20016
  Request Body는 `mrkt_deal_tp`(Required=Y, `%:전체, 1:코스피,
  0:코스닥`)를 요구하는데 기존 코드는 아예 보내지 않았습니다. 이제
  `--market`(기본 `all`→`"%"`)으로 항상 전송합니다. 같은 요청 바디의
  선택 필드 `crd_stk_grde_tp`(`--grade`, 기본 `all`→`"%"`, 항상 전송)와
  `stk_cd`(`--code`, 미지정 시 키 자체를 생략— 빈 문자열 아님)도 함께
  노출했습니다.
- **`--date-type` 기본값이 사용자가 반드시 입력해야 하는 `--from`/`--to`를
  무력화하고 있었습니다.** ka10043 Request Body(`docs/미국 REST API 문서.xlsx`)의
  `qry_dt_tp`는 `0:기간으로 조회, 1:시작일자·종료일자로 조회`인데, 기존 기본값
  `"0"`은 `--from`/`--to`가 `required=True`로 항상 채워지는데도 API가 이를 무시하고
  `dt`(기간) 기준으로 조회하게 만들었습니다. 기본값을 `"1"`(start-end)로
  바꿨습니다 — CLI로 직접 확인: `stock analysis trader-analysis 005930 --from
  20260101 --to 20260107 --broker 001` 기본 호출의 전송 body가
  `qry_dt_tp="0"`에서 `"1"`로 바뀝니다.
- **`--broker`(`mmcm_cd`)가 Required=Y 필드인데 기본값이 빈 문자열이었습니다.**
  옵션을 생략하면 항상 빈 `mmcm_cd`를 전송했습니다(회원사 코드 조회는
  `stock brokers`, ka10102). 이제 필수 옵션으로 승격했고, help에
  `stock brokers`를 안내합니다.
- **`order buy NVDA 10 --type limit`이 `--price` 없이 `ord_uv=""`로
  전송되고 있었습니다.** ust20000/ust20001 스펙(`docs/미국 REST API
  문서.xlsx`)의 `ord_uv` Description은 "trde_tp가 00(지정가),30(LOC)...인
  경우 필수 입력, 그 외 시장가 거래유형 설정 시 입력 값은 빈 값 처리"라고
  명시합니다 — `Required` 컬럼만 보면 `N`이라 선택 항목처럼 보이지만,
  지정가 계열에서는 사실상 필수입니다. 이제 지정가 계열
  (`US_LIMIT_TYPES` = `limit`/`vwap-limit`/`twap-limit`/`loc`/`stop-limit`,
  시장가 계열의 정확한 여집합)에서 `--price` 없이 호출하면 `INVALID_INPUT`으로
  즉시 종료하고, 요청 자체를 전송하지 않습니다(CLI로 직접 확인 — 5종 전부와
  `--type market`/`--type market --price` 회귀 케이스 포함).
- 국내 주문(`order buy`/`sell`, `order credit buy`)에는 아직 같은 가드가
  없습니다. 국내 지정가도 `ord_uv`를 빈 문자열로 전송하고 있어 문제는 그대로
  남아 있지만, 서버가 이 값을 거부하기 때문에 잘못된 주문이 나가지는 않습니다.
  CLI가 미리 걸러줬을 `exit 1` 대신 API 오류(`exit 2`)가 돌아오는 차이입니다.
  가드의 근거는 있습니다 — 키움 공식 CLI(kwcli)가 함께 배포하는
  `order_price_policies.csv`가 국내 지정가 매수·매도·신용매수에 대해 `--price`를
  required로 지정합니다. 워크북의 `ord_uv` Description은 "단위: 원"이 전부라
  이번 검토에서는 근거가 없다고 판단했는데, 확인이 부족했습니다. 다음
  릴리스에서 국내 경로에도 같은 가드를 넣겠습니다.

**Breaking**

- **`market rank volume`에서 `--include-managed`가 제거되고 `--stock-condition`으로
  대체됩니다.** 필드(`mang_stk_incls`)가 boolean이 아니라 15종 종목필터이기
  때문입니다(kwcli `rankings today-volume --stock-condition`과 이름을 맞췄습니다).
  기존 `--include-managed` 호출은 이제 "No such option" 오류로 exit 1이 됩니다.
- **`market elw broker-top`의 `--issuer`가 이제 필수입니다.** 이전엔 항상
  무효한 기본값을 전송했으므로, 이는 "동작하던 게 깨지는" 변경이 아니라
  "항상 실패하던 호출이 이제 명확히 실패"하는 변경입니다. `--issuer` 없이
  호출하면 exit 1.
- **자유 텍스트였던 아래 옵션들이 enum으로 좁혀져, 스펙 밖 값을 넘기면
  exit 1이 됩니다** (모두 `HumanChoice`라 기존에 쓰던 raw 숫자 코드는 계속
  동작합니다 — 하위호환):
  - `market rank volume`: `--sort`, `--stock-condition`(신규, 舊 `--include-managed`),
    `--credit-type`, `--vol-type`, `--price-type`, `--amount-type`, `--session`
  - `market rank amount`: `--include-managed`
  - `market rank broker-by-stock`: `--type`, `--period`
  - `market elw broker-top`: `--vol-type`, `--type`, `--period`, `--exclude-expired`
- **자유 텍스트였던 아래 옵션들도 enum으로 좁혀져, 매핑에 없는 값을 넘기면
  exit 1이 됩니다** (모두 `HumanChoice`라 기존 raw 숫자 코드는 계속
  동작합니다):
  - `market program time-trend`/`daily-trend`: `--unit`, `--tick-type`
  - `stock investor consecutive`: `--period`, `--net-type`
- **`market rank broker-by-stock`에서 `--period`와 `--from`/`--to`를 함께 주면
  이제 `INVALID_INPUT`으로 exit 1입니다.** 스펙상 두 조회 방식은 상호 배타적이라
  (기간 조회 시 `dt`는 빈값이어야 함) 동시 지정은 의미가 정의되지 않은 조합이었고,
  전에는 조용히 `dt`가 우선 적용됐습니다.
- **`market rank broker-by-stock`에서 `--from`/`--to` 중 하나만 주면 이제
  `INVALID_INPUT`으로 exit 1입니다.** 전에는 한쪽만 줘도 요청이 나갔지만
  `dt`(기본 `"1"`)가 함께 전송돼, 스펙상 기간 조회가 이겨 사용자가 준 날짜는
  무시됐습니다. 스펙 조건("시작일자와 종료일자로 조회를 원하는 경우")은 둘
  다를 뜻하므로, 이제 `--from`/`--to`는 함께 주거나 둘 다 생략해야 합니다.
- **`--market` 전송값이 `"0"`/`"1"`에서 P-코드로 바뀝니다.** 이전 기본값
  `"0"`은 스펙에 없는 값이었으므로 이건 고쳐진 것이지 기능이 바뀐 게
  아닙니다. 다만 `--market`은 이전에 자유 텍스트(`type=` 없음)였다가 이제
  `click.Choice(["kospi","kosdaq"])`로 좁아져, 임의 문자열(예: raw P-코드를
  직접 넘기던 호출)을 그대로 전달하던 동작은 더 이상 동작하지 않습니다 —
  `--unit`/`--tick-type`과 달리 `--market`은 `HumanChoice`가 아니라 순수
  `click.Choice`라 raw 코드 하위호환이 없습니다(값이 `stex_tp`와 함께 2단
  조회에 쓰이기 때문입니다).
- **`--trade`의 기본값이 `trde_tp=2`(매도)에서 `trde_tp=0`(순매수)로
  바뀌었습니다.** 이건 이름 체계와 무관한 별개의 변경입니다 — raw 코드를
  직접 지정하는 호출(`--trade 2`, `--trade sell` 등)은 위와 같이 계속
  똑같은 데이터를 반환하지만, **`--trade`를 아예 지정하지 않고 기본값에
  의존하던 호출**은 이제 다른 데이터(순매수 상위 종목)를 받습니다. 이전에
  기본값으로 매도 데이터를 받던 스크립트는 명시적으로 `--trade sell`을
  추가해야 이전과 같은 데이터를 계속 받습니다.
- **`--amount-qty`의 기본값이 `amt_qty_tp=1`(수량)에서 `amt_qty_tp=0`(금액)로
  바뀌었습니다.** 이건 이름 체계와 무관한 별개의 변경입니다 — raw 코드를
  직접 지정하는 호출(`--amount-qty 1`, `--amount-qty quantity` 등)은 위와
  같이 계속 똑같은 데이터(수량)를 반환하지만, **`--amount-qty`를 아예
  지정하지 않고 기본값에 의존하던 호출**은 이제 다른 데이터(금액)를
  받습니다. 이전에 기본값으로 수량 데이터를 받던 스크립트는 명시적으로
  `--amount-qty quantity`를 추가해야 이전과 같은 데이터를 계속 받습니다.
- **`--amount-qty`(ka10131)에서 `2`를 더 이상 받지 않습니다.** 이전 Choice
  목록은 `["1","2"]`였고 `--amount-qty 2`는 `amt_qty_tp="2"`를 그대로
  전송했지만, 스펙(`0:금액, 1:수량`)에 없는 값이었습니다. 이제 `2`를 넘기면
  전송 전에 `exit 1`입니다. raw `0`/`1`은 계속 동작합니다.
- **`--investor-type`의 기본 전송값이 `invsr="1000"`에서 `invsr="6"`(외국인)로
  바뀌었습니다.** 기존 기본 호출은 스펙 밖 값을 보내고 있었으므로, 이전에
  기본값에 의존하던 호출은 이제 다른(그리고 실제로 유효한) 데이터를
  받습니다.
- **`--investor-type`가 자유 텍스트에서 스펙값 8개(`invsr` 코드북)만 받는
  enum이 되었습니다.** 기존엔 `type=` 지정이 없어 어떤 문자열이든 그대로
  `invsr`로 전송했습니다. 이제 그 8개 값(및 대응하는 사람이 읽는 이름)
  이외의 입력은 전송 전에 `exit 1`로 거부됩니다. 실제로 확인된 회귀:
  이전 기본값이었던 `--investor-type 1000`, 그리고 `--investor-type 9`
  둘 다 이전에는 각각 `invsr="1000"`/`invsr="9"`를 그대로 전송했지만
  지금은 `exit 1`입니다. 스펙에 없는 값을 쓰던 스크립트만 영향을
  받습니다.
- **`--amount-qty`가 자유 텍스트에서 스펙값 하나(`combined`/`1`)만 받는
  enum이 되었습니다.** `1` 이외의 값(예: `--amount-qty 2`)은 이제 전송
  전에 `exit 1`로 거부됩니다. 스펙에 없는 값을 쓰던 스크립트만 영향을
  받습니다.
- **`credit inquiry`가 이제 종목코드 인자를 요구합니다.** 인자 없이
  호출하면 `exit 1`(Click 필수 인자 누락 → 이 프로젝트는 `UsageError`를
  `EXIT_INPUT=1`로 재매핑합니다, `main.py`)로 종료합니다. 다만 인자 없는
  기존 호출은 어차피 `{}`를 보내 API가 거부하고 있었으므로, "정상 동작하던
  것이 깨지는" 종류의 breaking은 아닙니다.
- **`--type`(`week`/`month`) 옵션이 제거됐습니다.** ka10005 Request Body는
  `stk_cd` 하나뿐이고(스펙: `docs/미국 REST API 문서.xlsx`) 기간을 고르는
  파라미터가 존재하지 않습니다. 기존 코드는 `qry_tp`라는 필드를 지어내
  보냈는데, 서버는 이 필드를 인식하지 못해 무시하고 항상 일별 데이터를
  반환했습니다 — 다만 CLI는 `--type week`/`--type month`일 때 제목만
  "주별"/"월별"로 바꿔 달았습니다. 즉 **이전에도 실제로는 항상 일별
  데이터였고, 라벨만 잘못돼 있었습니다.** `--type week`/`--type month`를
  쓰던 스크립트는 이제 `exit 1`, `Error: No such option '--type'.`로
  실패합니다(Click의 "No such option" 경로 — 이 프로젝트는 `UsageError`를
  `EXIT_INPUT=1`로 재매핑하므로 Click 기본값 2가 아니라 1로 종료합니다).
  주/월별 시세가 실제로 필요하면 `stock chart week`/`stock chart month`
  (ka10082/ka10083)를 쓸 것 — 이쪽은 실제로 다른 기간 데이터를 반환하는
  진짜 엔드포인트입니다.
- **`--date-type` 기본 전송값이 `qry_dt_tp="0"`에서 `"1"`로 바뀝니다.** 다만
  이전 동작은 사용자가 필수로 입력한 `--from`/`--to`를 API가 조용히 무시하는
  것이었으므로, 이는 **고쳐진 것이지 기능이 바뀐 게 아닙니다** — 이전에
  기본 호출로 얻던 "기간(dt) 기준 조회 결과"에 의존하던 스크립트만 영향을
  받으며, 그 결과 자체가 사용자가 지정한 날짜 범위와 무관했습니다.
- **`--broker`가 이제 필수입니다.** 이전엔 생략 시 빈 값(`mmcm_cd=""`)을
  전송했고 — Required=Y 필드에 빈 값이므로 서버가 거부했을 값입니다 — 이제
  생략하면 `Error: Missing option '--broker'.`로 `exit 1`이고 요청 자체가
  나가지 않습니다(CLI로 직접 실행해 확인).
- **지정가 계열 미국주식 주문에서 `--price`를 생략하던 호출이 이제
  `exit 1`입니다.** 다만 이 호출은 **원래 정상 동작한 적이 없습니다** —
  `ord_uv=""`를 서버가 거부했거나, 사용자가 의도하지 않은 방식으로
  처리됐을 주문입니다. 조용히 잘못 나가던 요청이 이제 전송 전에
  막힙니다. 영향받는 명령: `order buy`/`sell --type limit|vwap-limit|
  twap-limit|loc`(매수/매도), `order sell --type stop-limit`(매도 전용),
  그리고 `--dry-run`도 동일하게 막힙니다 — `order buy NVDA 10 --type limit
  --dry-run`은 이제 body를 출력하는 대신 `exit 1`입니다. `--price`를
  지정하면 이전과 동일하게 동작합니다.

**Non-breaking (사람이 읽는 이름 추가, 하위호환 / 순수 확장)**

- **`market rank amount`(ka10032)의 `--include-managed`가 이제 `no`/`yes`
  이름도 받습니다.** 전송값은 그대로입니다: `no`→`mang_stk_incls=0`,
  `yes`→`mang_stk_incls=1`. `market rank volume`(ka10030)의 동일 이름 필드와
  **극성이 정반대**임을 두 커맨드 모두 테스트로 고정했습니다
  (`STOCK_CONDITION`은 `0=포함`, `MANAGED_STOCK_INCLUDE`는 `0=미포함`).
- **`market rank amount`의 `--exchange`가 이제 `all`(통합, `stex_tp=3`)도
  받습니다.** 스펙(`stex_tp`)에 `3:통합`이 있었는데 기존 코드는 `KRX`/`NXT`
  두 값만 허용했습니다. 순수 추가이며 기본값(`KRX`) 호출의 전송 body는
  변경 전후 동일함을 CLI로 확인했습니다.
- **`market rank broker-by-stock`(ka10038)의 `--period`가 이제 `previous`/`5d`/
  `10d`/`20d`/`40d`/`60d`/`120d` 같은 이름도 받습니다.** 이 필드는
  코드가 하루씩 어긋난 off-by-one 코드북입니다(`5일=4`, `10일=9`, `120일=119`).
  전송값은 그대로이며(`previous`→`dt=1` 등), kwcli
  `rankings broker-by-stock --period` 값과 일치를 확인했습니다.
- **나머지 신규 human-readable 옵션들의 전송값도 전부 전환 전과 동일합니다**
  (기본 호출의 body를 CLI로 직접 실행해 확인): `rank volume`의
  `--sort=volume→sort_tp=1`, `--credit-type=all→crd_tp=0`,
  `--vol-type=all→trde_qty_tp=0`, `--price-type=all→pric_tp=0`,
  `--amount-type=all→trde_prica_tp=0`, `--session=all→mrkt_open_tp=0`;
  `elw broker-top`의 `--vol-type=all→trde_qty_tp=0`,
  `--type=net-buy→trde_tp=1`, `--period=previous→dt=1`,
  `--exclude-expired=exclude→trde_end_elwskip=1`.
  - `rank volume`의 `--vol-type`(`trde_qty_tp`) 값 중 `500`은 스펙 원문 설명이
    "500만주이상"(5,000,000)으로 적혀 있어 다른 항목들의 산술 패턴
    (코드값×1,000주)과 어긋납니다. 스펙 문구 쪽이 틀렸다고 보고 이름은 패턴을
    따라 `500k`로 붙였는데, 키움 공식 kwcli의 `maps/arguments.csv`가
    `rankings today-volume`(=ka10030)의 같은 필드를 9개 값 전부 동일하게
    (`500k=500` 포함) 매핑하고 있어 확인됐습니다.
- **`--unit`/`--tick-type`이 이제 `amount`/`quantity`, `tick`/`minute` 같은
  사람이 읽는 이름도 받습니다.** 기존에 숫자 코드(`1`/`2`, `0`/`1`)를 직접
  넘기던 스크립트는 **그대로 동작합니다** — `HumanChoice`가 raw API 코드를
  하위호환으로 계속 허용하기 때문입니다. 전송값도 이름 추가 전과 동일합니다:
  `amount`→`amt_qty_tp=1`, `quantity`→`amt_qty_tp=2`;
  `tick`→`min_tic_tp=0`, `minute`→`min_tic_tp=1`.
- **`--exchange`가 이제 `all`(통합, `stex_tp=3`)도 받습니다.** 스펙에
  `3:통합`이 있었는데 기존 코드는 `KRX`/`NXT` 두 값만 허용했습니다. 순수
  추가라 기존 호출은 영향 없습니다(기본값 `KRX` 그대로, 실제로 CLI를
  실행해 기본값 호출의 전송 body가 변경 전후 동일함을 확인했습니다).
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
- **`--amount-qty`/`--period`/`--stock-sector`가 이제 `amount`/`quantity`,
  `recent`/`3d`/`5d`/`10d`/`20d`/`120d`/`range`, `stock`/`sector` 같은 사람이
  읽는 이름도 받습니다.** 스펙이 정의한 숫자 코드를 직접 넘기던 스크립트는
  **그대로 동작합니다** — `HumanChoice`가 raw API 코드를 하위호환으로 계속
  허용하기 때문입니다. 다만 `--amount-qty 2`는 예외로, 스펙에 없는 값이라
  이제 거부됩니다(아래 Breaking 참고). 전송값은 이름 추가 전과 동일합니다:
  `recent`→`dt=1`,
  `3d`→`dt=3`, `5d`→`dt=5`, `10d`→`dt=10`, `20d`→`dt=20`, `120d`→`dt=120`,
  `range`→`dt=0`; `stock`→`stk_inds_tp=0`, `sector`→`stk_inds_tp=1`.

  `--net-type`도 사람이 읽는 이름(`net-buy`)만 노출되도록 바뀌었지만 스펙상
  값이 `2`(순매수) 하나뿐이라 기존 자유 입력 `--net-type 2`도 계속
  `netslmt_tp=2`를 보냅니다. `--exchange`는 이미 이전 정리에서 전환되어
  이번 변경 대상이 아닙니다.
- **`--investor-type`/`--amount-qty`/`--foreign-all`/`--simultaneous`가
  이제 사람이 읽는 이름도 받습니다.** 새 매핑의 값(=스펙이 정의한 코드)을
  직접 넘기던 스크립트는 **그대로 동작합니다** — `HumanChoice`가 raw API
  코드도 하위호환으로 계속 허용하기 때문입니다. 전송값도 이름 추가 전과
  동일합니다: `foreign`→`invsr=6`, `institution`→`invsr=7`,
  `investment-trust`→`invsr=1`, `insurance`→`invsr=0`, `bank`→`invsr=2`,
  `pension`→`invsr=3`, `state`→`invsr=4`, `other-corporate`→`invsr=5`;
  `combined`→`amt_qty_tp=1`; `yes`→`1`, `no`→`0`(`frgn_all`/
  `smtm_netprps_tp` 공통 — 스펙의 값이 이 두 개뿐이라 완전히
  하위호환입니다). `--market`에 `all`이 추가된 것도 순수 추가라 기존
  호출은 영향 없습니다(기본값 `kospi` 그대로). **단, `--investor-type`과
  `--amount-qty`는 매핑에 없는 값(스펙 밖 raw 코드)을 넘기던 호출까지는
  하위호환하지 않습니다 — 위 Breaking 참고.**
- `credit available --market`은 `MARKET_KOSPI_KOSDAQ`(kospi=0, kosdaq=1)과
  극성이 반대인 `CREDIT_MARKET`(kospi=1, kosdaq=0)을 씁니다 — kt20016
  고유 코드북이라 다른 엔드포인트에 영향 없습니다. `HumanChoice`가 원시
  코드도 하위호환으로 허용하고, 두 커맨드 모두 이전에는 옵션이 하나도
  없었으므로 여기서 "옵션 하위호환 깨짐"에 해당하는 변경은 없습니다.
- **`--date-type`가 `period`(`qry_dt_tp=0`)/`start-end`(`=1`)를, `--pot`가
  `today`(`pot_tp=0`)/`previous`(`=1`)를, `--sort`가 `close`(`sort_base=1`)/
  `date`(`=2`)를 받습니다.** 전송값은 원시 코드와 동일함을 CLI로 확인했습니다.
- **`--days`가 `5d`/`10d`/`20d`/`40d`/`60d`/`120d` 이름도 받습니다.** 이
  코드북은 `5일=5`로 코드가 일수와 그대로 일치합니다 — `market rank
  broker-by-stock`(ka10038)의 `dt`(`5일=4`, `10일=9`, ... 하루씩 어긋나는
  off-by-one 코드북)와 값 집합이 다르므로 절대 혼용하지 않도록 CLI 테스트로
  `--days 5d → dt="5"`(`"4"` 아님)를 고정했습니다.

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
