#!/usr/bin/env bash
# litmus.sh — AI 에이전트 관점의 재현 가능한 증명 (모의투자 전용)
#
# 시세 → 사전점검 → dry-run → 멱등키 매수 → 같은 키 재실행(재전송 없음 검증)
# → 미체결 → 잔고. 모든 단계가 `-f json` stdout만으로 구동되고 `jq -e`로
# 검증된다. 첫 실패에서 즉시 비0 exit — CI에 그대로 물릴 수 있다.
#
# 사전 조건: benchmark/README.md 참고 (모의투자 키로 config setup, auth login, jq)
#
# 사용법:
#   ./benchmark/litmus.sh              # 005930(삼성전자) 1주
#   CODE=000660 QTY=2 ./benchmark/litmus.sh
set -euo pipefail

KIWOOM="${KIWOOM:-kiwoom}"   # 다른 바이너리로 실행하려면 KIWOOM=... 지정
CODE="${CODE:-005930}"
QTY="${QTY:-1}"
CLIENT_ORDER_ID="${CLIENT_ORDER_ID:-litmus-$(date +%s)}"

fail() { echo "✗ $*" >&2; exit 1; }

command -v "$KIWOOM" >/dev/null || fail "kiwoom을 찾을 수 없습니다: pip install kiwoom-cli"
command -v jq >/dev/null || fail "jq가 필요합니다: brew install jq / apt install jq"

LAST=""  # 직전 단계 stdout (envelope JSON)

# step <이름> <jq 필터> <kiwoom 인자...>
# 명령 실행 → stdout이 jq 필터를 만족하는지 검증. 실패 시 응답을 보여주고 종료.
step() {
    local name="$1" filter="$2"
    shift 2
    echo "▶ $name" >&2
    if ! LAST="$("$KIWOOM" -f json "$@")"; then
        echo "$LAST" | jq . >&2 2>/dev/null || echo "$LAST" >&2
        fail "$name: 명령 실패 — kiwoom -f json $*"
    fi
    if ! echo "$LAST" | jq -e "$filter" >/dev/null; then
        echo "$LAST" | jq . >&2
        fail "$name: 검증 실패 — jq: $filter"
    fi
    echo "✓ $name" >&2
}

# ── 0. 안전장치: 모의투자(mock)에서만 진행 ─────────────────────
step "0. 환경 확인 (env=mock, 토큰 있음)" \
    '.ok == true and .meta.env == "mock" and .data.has_token == true' \
    auth status
# ↑ 실패 시: env가 prod면 `kiwoom config set domain mock`, 토큰이 없으면 `kiwoom auth login`

# ── 1. 시세 — 타입 있는 정규화 필드 (부호/문자열 파싱 불필요) ──
step "1. 시세 조회 (price는 number)" \
    '.ok == true and (.data.price | type == "number") and .data.symbol != null' \
    stock info "$CODE"
PRICE="$(echo "$LAST" | jq -r '.data.price')"
echo "  → ${CODE} 현재가: ${PRICE}" >&2

# ── 2. 사전점검 — read-only, 주문 미전송 ──────────────────────
step "2. order validate (valid=true)" \
    '.ok == true and .data.valid == true and .data.checks.symbol_ok == true' \
    order validate buy "$CODE" "$QTY" --price "$PRICE"

# ── 3. dry-run — 전송될 body 확인, 실제 전송 없음 ─────────────
step "3. dry-run (would_send=true)" \
    '.ok == true and .data.would_send == true and .data.body.stk_cd != null' \
    order buy "$CODE" "$QTY" --price "$PRICE" --type limit --dry-run

# ── 4. 실제 매수 — 멱등키와 함께 ──────────────────────────────
step "4. 매수 (client-order-id=$CLIENT_ORDER_ID)" \
    '.ok == true and (.data.order_no | length > 0)' \
    order buy "$CODE" "$QTY" --price "$PRICE" --type limit \
    --confirm --client-order-id "$CLIENT_ORDER_ID"
ORDER_NO="$(echo "$LAST" | jq -r '.data.order_no')"
echo "  → 주문번호: ${ORDER_NO}" >&2

# ── 5. 같은 키 재실행 — 재전송 없이 이전 응답 (중복 주문 방지) ─
step "5. 멱등 재실행 (idempotent_replay=true, 같은 주문번호)" \
    ".ok == true and .data.idempotent_replay == true and .data.order_no == \"$ORDER_NO\"" \
    order buy "$CODE" "$QTY" --price "$PRICE" --type limit \
    --confirm --client-order-id "$CLIENT_ORDER_ID"

# ── 6. 미체결 조회 ─────────────────────────────────────────────
# (모의투자에서 즉시 체결될 수 있어 목록에 남아있는지는 단정하지 않음)
step "6. 미체결 조회 (kr 섹션 존재)" \
    '.ok == true and (.data | has("kr"))' \
    account orders pending --market kr

# ── 7. 잔고 조회 ───────────────────────────────────────────────
step "7. 잔고 조회" \
    '.ok == true and (.data | type == "object")' \
    account balance --market kr

echo >&2
echo "✓ litmus loop 통과 — 7단계 전부 stdout JSON + exit code만으로 구동됨" >&2
