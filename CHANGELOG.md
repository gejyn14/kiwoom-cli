# Changelog

## [Unreleased]

`market rank volume`(ka10030)의 `--include-managed` help 문구가 스펙과 정반대였고,
`market rank amount`(ka10032)는 극성이 반대인 동일 이름 옵션을 그대로 쓰고
있었습니다. `market rank broker-by-stock`(ka10038)은 `--period`/`--from`·`--to`를
함께 줘도 기간(`dt`)이 항상 우선하고 있었고, `market elw broker-top`(ka30002)의
`--issuer` 기본값은 자릿수부터 틀린 값(12자리, 필드는 3자리)을 매번 전송하고
있었습니다. 네 곳 모두 교정하고, 이 참에 두 명령의 나머지 자유 텍스트 옵션도
human-readable 이름으로 전환했습니다.

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
- **`market rank broker-by-stock`(ka10038)에서 `--from`만 주고 `--to`를 빠뜨리면
  (또는 그 반대) `end_dt`가 빈 문자열인 채로 전송되고 있었습니다.** 스펙의
  "시작일자와 종료일자로 조회를 원하는 경우"는 둘 다를 뜻하는데, 기존 코드는
  `bool(strt_dt or end_dt)`로 한쪽만 있어도 기간 조회로 취급해 `dt` 키를 뺐습니다.
  이제 `--from`/`--to` 중 하나만 주면 `INVALID_INPUT`으로 exit 1이며, 요청 자체를
  보내지 않습니다(CLI로 직접 확인).

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
- **`market rank broker-by-stock`에서 `--period`와 `--from`/`--to`를 함께 주면
  이제 `INVALID_INPUT`으로 exit 1입니다.** 스펙상 두 조회 방식은 상호 배타적이라
  (기간 조회 시 `dt`는 빈값이어야 함) 동시 지정은 의미가 정의되지 않은 조합이었고,
  전에는 조용히 `dt`가 우선 적용됐습니다.
- **`market rank broker-by-stock`에서 `--from`/`--to` 중 하나만 주면 이제
  `INVALID_INPUT`으로 exit 1입니다.** 전에는 한쪽만 줘도 기간 조회로 간주해
  `dt` 키를 빼고 `end_dt`(또는 `strt_dt`)가 빈 문자열인 채로 전송했습니다 —
  스펙 조건("시작일자와 종료일자로 조회를 원하는 경우")은 둘 다를 뜻하므로,
  이제 `--from`/`--to`는 함께 주거나 둘 다 생략해야 합니다.

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
    (코드값×1,000주)과 어긋납니다. 코드값(`"500"`) 자체는 워크북 기준
    확실하므로 그대로 두되, 사람이 읽는 이름은 패턴을 따라 `500k`로 붙였습니다
    — 이 이름은 확정된 사실이 아니라 보수적 선택입니다.

`market program time-trend`(ka90005)/`market program daily-trend`(ka90010)의
`--market`이 스펙에 정의되지 않은 코드를 보내고 있었고, 정정과 함께
`--unit`/`--tick-type`에 human-readable 이름을 추가했습니다(하위호환).

**Fixed**

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

**Breaking**

- **`--market` 전송값이 `"0"`/`"1"`에서 P-코드로 바뀝니다.** 이전 기본값
  `"0"`은 스펙에 없는 값이었으므로 이건 고쳐진 것이지 기능이 바뀐 게
  아닙니다. 다만 `--market`은 이전에 자유 텍스트(`type=` 없음)였다가 이제
  `click.Choice(["kospi","kosdaq"])`로 좁아져, 임의 문자열(예: raw P-코드를
  직접 넘기던 호출)을 그대로 전달하던 동작은 더 이상 동작하지 않습니다 —
  `--unit`/`--tick-type`과 달리 `--market`은 `HumanChoice`가 아니라 순수
  `click.Choice`라 raw 코드 하위호환이 없습니다(값이 `stex_tp`와 함께 2단
  조회에 쓰이기 때문입니다).
- **`--exchange`가 이제 `all`(통합, `stex_tp=3`)도 받습니다.** 스펙에
  `3:통합`이 있었는데 기존 코드는 `KRX`/`NXT` 두 값만 허용했습니다. 순수
  추가라 기존 호출은 영향 없습니다(기본값 `KRX` 그대로, 실제로 CLI를
  실행해 기본값 호출의 전송 body가 변경 전후 동일함을 확인했습니다).

**Non-breaking (사람이 읽는 이름 추가, 하위호환)**

- **`--unit`/`--tick-type`이 이제 `amount`/`quantity`, `tick`/`minute` 같은
  사람이 읽는 이름도 받습니다.** 기존에 숫자 코드(`1`/`2`, `0`/`1`)를 직접
  넘기던 스크립트는 **그대로 동작합니다** — `HumanChoice`가 raw API 코드를
  하위호환으로 계속 허용하기 때문입니다. 전송값도 이름 추가 전과 동일합니다:
  `amount`→`amt_qty_tp=1`, `quantity`→`amt_qty_tp=2`;
  `tick`→`min_tic_tp=0`, `minute`→`min_tic_tp=1`. 다만 두 옵션 모두 이전엔
  자유 텍스트(`type=` 없음)였으므로, 매핑에 없는 임의 문자열을 넘기던
  호출은 이제 거부됩니다(enum 축소 — CLI로 직접 확인: 매핑에 없는 값을
  넘기면 exit code 1).

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

`stock investor consecutive`(ka10131)의 `--amount-qty` 값이 스펙과 반대였고,
정정과 함께 세 옵션에 raw 숫자코드와 함께 쓸 수 있는 human-readable 이름을
추가했습니다(하위호환).

**Fixed**

- **`--amount-qty` 기본값이 실제로는 수량(1) 데이터를 반환하고 있었습니다.**
  스펙(ka10131 Request Body)은 `amt_qty_tp`를 `0:금액, 1:수량`으로 정의하는데,
  기존 코드는 `Choice(["1","2"])`에 `default="1"`이었고 help는 `1=금액,
  2=수량`이라고 적어 실제 동작과 어긋났습니다(전송값 `1`은 스펙상 수량이지
  help가 말한 금액이 아니었습니다). 스펙에 없는 값 `2`도 Choice 목록에는
  올라 있었습니다.

**Non-breaking (사람이 읽는 이름 추가, 하위호환)**

- **`--amount-qty`/`--period`/`--stock-sector`가 이제 `amount`/`quantity`,
  `recent`/`3d`/`5d`/`10d`/`20d`/`120d`/`range`, `stock`/`sector` 같은 사람이
  읽는 이름도 받습니다.** 기존에 숫자 코드를 직접 넘기던 스크립트는 **그대로
  동작합니다** — `HumanChoice`가 raw API 코드를 하위호환으로 계속 허용하기
  때문입니다. 전송값도 이름 추가 전과 동일합니다: `recent`→`dt=1`,
  `3d`→`dt=3`, `5d`→`dt=5`, `10d`→`dt=10`, `20d`→`dt=20`, `120d`→`dt=120`,
  `range`→`dt=0`; `stock`→`stk_inds_tp=0`, `sector`→`stk_inds_tp=1`.

  다만 **`--period`는 이전에 자유 입력이라 아무 값이나 그대로 API로
  전송했습니다.** 이제 위 7개 값만 받습니다 — `--period 7`처럼 스펙에 없는
  값은 전송 전에 `exit 1`로 거부됩니다(이전에는 `dt=7`이 그대로 나갔고, 이
  값은 ka10131 스펙에 정의되어 있지 않습니다). 스펙에 없던 값을 쓰던
  스크립트만 영향을 받습니다.

  `--net-type`도 사람이 읽는 이름(`net-buy`)만 노출되도록 바뀌었지만 스펙상
  값이 `2`(순매수) 하나뿐이라 기존 자유 입력 `--net-type 2`도 계속
  `netslmt_tp=2`를 보냅니다. `--exchange`는 이미 이전 정리에서 전환되어
  이번 변경 대상이 아닙니다.

**Breaking**

- **`--amount-qty`의 기본값이 `amt_qty_tp=1`(수량)에서 `amt_qty_tp=0`(금액)로
  바뀌었습니다.** 이건 이름 체계와 무관한 별개의 변경입니다 — raw 코드를
  직접 지정하는 호출(`--amount-qty 1`, `--amount-qty quantity` 등)은 위와
  같이 계속 똑같은 데이터(수량)를 반환하지만, **`--amount-qty`를 아예
  지정하지 않고 기본값에 의존하던 호출**은 이제 다른 데이터(금액)를
  받습니다. 이전에 기본값으로 수량 데이터를 받던 스크립트는 명시적으로
  `--amount-qty quantity`를 추가해야 이전과 같은 데이터를 계속 받습니다.

`stock investor intraday`(ka10063)는 요청 바디 6개 필드 중 5개가 스펙과 어긋나
있었습니다. 정정과 함께 네 옵션에 raw 숫자코드와 함께 쓸 수 있는
human-readable 이름을 추가했습니다(하위호환).

**Fixed**

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

**Non-breaking (사람이 읽는 이름 추가, 하위호환)**

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
  하위호환하지 않습니다 — 아래 Breaking 참고.**

**Breaking**

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

`stock credit inquiry`(kt20017)는 필수 필드를 받을 방법이 없어 `{}`만
전송했고, `stock credit available`(kt20016)도 필수 `mrkt_deal_tp`를
누락하고 있었습니다.

**Fixed**

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

**Breaking**

- **`credit inquiry`가 이제 종목코드 인자를 요구합니다.** 인자 없이
  호출하면 `exit 1`(Click 필수 인자 누락 → 이 프로젝트는 `UsageError`를
  `EXIT_INPUT=1`로 재매핑합니다, `main.py`)로 종료합니다. 다만 인자 없는
  기존 호출은 어차피 `{}`를 보내 API가 거부하고 있었으므로, "정상 동작하던
  것이 깨지는" 종류의 breaking은 아닙니다.
- `credit available --market`은 `MARKET_KOSPI_KOSDAQ`(kospi=0, kosdaq=1)과
  극성이 반대인 `CREDIT_MARKET`(kospi=1, kosdaq=0)을 씁니다 — kt20016
  고유 코드북이라 다른 엔드포인트에 영향 없습니다. `HumanChoice`가 원시
  코드도 하위호환으로 허용하고, 두 커맨드 모두 이전에는 옵션이 하나도
  없었으므로 여기서 "옵션 하위호환 깨짐"에 해당하는 변경은 없습니다.

`stock daily`(ka10005)가 스펙에 없는 `qry_tp` 필드를 지어내 보내고 있었습니다.
이번 릴리스에서 유일하게 "원래 되던 것이 안 되는" breaking 변경입니다 —
위 항목들과 달리 옵션 자체가 제거됩니다.

**Breaking**

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

`stock analysis trader-analysis`(ka10043)는 `--from`/`--to`가 이미
`required=True`인데도 `--date-type`(`qry_dt_tp`) 기본값이 `"0"`(기간으로 조회)이라
그 필수 날짜를 API가 무시하고 있었고, `--broker`(`mmcm_cd`, Required=Y)는
기본값이 빈 문자열이었습니다. 두 곳을 고치고, 나머지 원시 숫자 코드 옵션
(`--date-type`/`--pot`/`--sort`/`--days`)도 human-readable 이름으로 전환했습니다.

**Fixed**

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

**Breaking**

- **`--date-type` 기본 전송값이 `qry_dt_tp="0"`에서 `"1"`로 바뀝니다.** 다만
  이전 동작은 사용자가 필수로 입력한 `--from`/`--to`를 API가 조용히 무시하는
  것이었으므로, 이는 **고쳐진 것이지 기능이 바뀐 게 아닙니다** — 이전에
  기본 호출로 얻던 "기간(dt) 기준 조회 결과"에 의존하던 스크립트만 영향을
  받으며, 그 결과 자체가 사용자가 지정한 날짜 범위와 무관했습니다.
- **`--broker`가 이제 필수입니다.** 이전엔 생략 시 빈 값(`mmcm_cd=""`)을
  전송했고 — Required=Y 필드에 빈 값이므로 서버가 거부했을 값입니다 — 이제
  생략하면 `Error: Missing option '--broker'.`로 `exit 1`이고 요청 자체가
  나가지 않습니다(CLI로 직접 실행해 확인).
- **자유 텍스트였던 `--date-type`/`--pot`/`--sort`/`--days`가 enum(`HumanChoice`)
  으로 좁혀졌습니다.** 매핑에 없는 값(스펙 밖 raw 문자열)을 넘기던 호출만
  이제 `exit 1`로 거부됩니다. `HumanChoice` 전환 자체는 breaking이 아닙니다 —
  기존에 쓰던 raw 숫자 코드(`"0"`/`"1"`/`"5"`.../`"120"` 등)는 계속 그대로
  받습니다.

**Non-breaking (사람이 읽는 이름 추가, 하위호환)**

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
