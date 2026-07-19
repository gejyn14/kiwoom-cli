# benchmark: litmus loop

AI 에이전트가 kiwoom-cli를 실제로 밟게 될 경로를 **모의투자(mock) 도메인에서
재현 가능하게 증명**하는 스크립트. 사람 개입(프롬프트) 없이, 각 단계가 이전
단계의 stdout JSON만으로 구동되고 `jq -e`로 검증된다. 첫 실패에서 즉시
비0 exit. CI에 그대로 물릴 수 있다.

```
0. auth status        env=mock 확인 (prod면 즉시 중단) + 토큰 존재
1. stock info         .data.price가 number (부호/문자열 파싱 불필요)
2. order validate     read-only 사전점검. .data.valid == true
3. order buy --dry-run  전송될 body 확인. .data.would_send == true (미전송)
4. order buy --confirm --client-order-id  실제 매수. .data.order_no
5. 같은 명령 재실행    .data.idempotent_replay == true, 같은 order_no (재전송 없음)
6. account orders pending  미체결 조회
7. account balance    잔고 조회
```

같은 흐름의 네트워크 없는 pytest 버전이 CI에서 항상 돌고 있다:
[`tests/test_order.py::test_litmus_loop_json_driven`](../tests/test_order.py)
(FakeKiwoomClient 기반). 이 스크립트는 그 증명을 실제 모의투자 서버에 대고
재현하는 용도다.

## 사전 조건

1. **모의투자 appkey/secretkey**: [키움 REST API](https://openapi.kiwoom.com)에서 발급
2. **kiwoom-cli 설정** (도메인을 반드시 mock으로):
   ```bash
   uv tool install kiwoom-cli   # 또는 pipx install / pip install
   # jq는 별도로: brew install jq / apt install jq
   kiwoom config setup          # 도메인 질문에 mock 입력
   kiwoom auth login
   ```
3. 이미 prod 프로필을 쓰고 있다면 모의투자용 프로필을 따로 만들면 된다:
   ```bash
   kiwoom config setup --profile paper   # domain: mock
   KIWOOM_PROFILE=paper ./benchmark/litmus.sh
   ```

스크립트는 시작 전에 `meta.env == "mock"`을 확인하고, 아니면 아무 주문도
보내지 않고 중단한다.

## 실행

```bash
./benchmark/litmus.sh                 # 005930(삼성전자) 1주
CODE=000660 QTY=2 ./benchmark/litmus.sh
KIWOOM=".venv/bin/kiwoom" ./benchmark/litmus.sh   # 로컬 개발 바이너리로
```

성공 시 exit 0과 단계별 ✓, 실패 시 실패한 단계의 응답 JSON을 stderr로
보여주고 exit 1.

## 참고

- **모의투자 계좌에 실제로 주문이 들어간다** (mock 도메인이라 실제 돈은
  아니지만, 미체결/잔고에 흔적이 남는다). 장 운영시간 밖에서는 2단계
  `market_open` 체크나 주문 단계가 실패할 수 있다. 모의투자 장중에 돌리는
  것을 권장.
- 멱등키는 실행마다 `litmus-<epoch>`로 새로 생성된다. 5단계는 같은 실행 안에서
  같은 키를 재사용해 재전송이 없음을 증명한다 (원장:
  `~/.kiwoom/idempotency/<profile>-mock.jsonl`).
- 각 단계가 정확히 무엇을 검증하는지는 스크립트의 `jq` 필터가 곧 문서다.
  envelope 계약 전체는 [AGENTS.md](../AGENTS.md) 참고.
