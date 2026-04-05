# kiwoom-cli 전용 Subagent 설계

**Date**: 2026-04-05
**Status**: Approved

## 목적

kiwoom-cli 개발 워크플로우에서 반복적으로 발견된 약점(설계 없이 구현 시작, 컨벤션 위반)을 자동화된 subagent로 보완한다.

## 생성할 Subagent

### 1. kiwoom-feature-planner

**파일**: `.claude/agents/kiwoom-feature-planner.md`

**호출 시점**: Claude가 사용자 요청의 복잡도를 판단하여, 설계 결정이 필요한 요청일 때 자동 dispatch.

**예시**:
- "dangerous-mode 추가하자" → dispatch
- "새 주문 유형 만들자" → dispatch
- "오타 고쳐줘" → dispatch 안 함
- "README 수정해줘" → dispatch 안 함

**내장 질문 템플릿**:

1. 어느 명령어 그룹에 속하나요? (stock/account/order/market/stream, 또는 신규)
2. 어떤 키움 API를 사용하나요? (API ID, api_spec.py 등록 여부)
3. 인자와 옵션 설계:
   - 필수 인자
   - 날짜 범위 필요? (`--from/--to`)
   - 시장 구분 필요? (`_constants.MARKET_ALL`)
   - 거래소 구분 필요? (`_constants.EXCHANGE_TWO`)
4. 출력 형식:
   - 일반 조회 → `print_api_response`
   - 특수 포맷 필요?
5. 보안 관련:
   - 주문 명령어? → `_verify_order()` 적용
6. 테스트 대상:
   - mocked 테스트
   - 엣지 케이스

**출력**: `/Users/yujin-an/.claude/plans/mellow-wandering-forest.md`에 플랜 저장 → ExitPlanMode로 사용자 승인 요청.

---

### 2. kiwoom-convention-linter

**파일**: `.claude/agents/kiwoom-convention-linter.md`

**호출 시점**: `kiwoom_cli/commands/` 내 파일을 추가/수정한 후 Claude가 자동 dispatch.

**검사 항목 (4개)**:

#### 1) 옵션 이름 규칙

| 위반 | 권장 |
|------|------|
| `--start`, `--start-date` | `--from` |
| `--end`, `--end-date` | `--to` |

#### 2) 옵션 값 (human-readable)

| 위반 | 권장 |
|------|------|
| `["000", "001", "101"]` (시장) | `["all", "kospi", "kosdaq"]` |
| `["001", "101"]` (시장) | `["kospi", "kosdaq"]` |
| `["1", "2"]` (거래소) | `["KRX", "NXT"]` |
| `["1", "2", "3"]` (거래소) | `["KRX", "NXT", "all"]` |

예외: `sort_tp`, `qry_tp` 같은 단순 구분 숫자는 OK.

#### 3) _constants.py 사용

| 위반 | 권장 |
|------|------|
| 함수 내부 `_market_map = {...}` | `from ._constants import MARKET_ALL` |
| 함수 내부 `_exchange_map = {...}` | `from ._constants import EXCHANGE_TWO` |

#### 4) 출력 함수 사용

| 위반 | 권장 |
|------|------|
| `_find_list` + 수동 분기 반복 | `print_api_response(data, title)` |
| `click.echo`로 수동 테이블 | `print_generic_table(data, title)` |

**출력 형식**:

```
📋 Convention 검사 결과: kiwoom_cli/commands/stock.py

❌ N개 위반 발견:

[1] Line 45: 옵션 이름 규칙
    현재:  @click.option("--start-date", ...)
    권장:  @click.option("--from", ...)

수정하시겠습니까? [Y/n]
```

사용자 승인 후 자동 수정.

---

## 전체 흐름

```
사용자 요청
    ↓
Claude 복잡도 판단
    ↓ (설계 필요)
kiwoom-feature-planner 자동 dispatch
    ↓ (6개 질문 → 플랜 생성)
사용자 승인
    ↓
Claude가 구현
    ↓ (커맨드 파일 변경)
kiwoom-convention-linter 자동 dispatch
    ↓ (4개 항목 검사)
위반 리포트 + 사용자 승인
    ↓
자동 수정 적용
```

## 문서화

- `CLAUDE.md`에 subagent 사용 가이드 추가
- `CONTRIBUTING.md`에 개발 워크플로우 섹션 추가

## 성공 기준

1. "새 기능 만들자" 요청 시 planner가 자동 호출되어 6개 질문으로 설계 수집
2. 새 커맨드 추가 후 linter가 자동 호출되어 4개 항목 검사
3. 위반 발견 시 구체적인 라인 번호와 수정안 제시
4. 사용자 승인 시 자동으로 수정 적용
