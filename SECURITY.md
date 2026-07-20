# Security Policy

## Supported Versions

| Version | Supported |
|---------|:---------:|
| 2.x     | ✓         |
| 1.x     | ✗         |
| < 1.0   | ✗         |

보안 수정은 최신 2.x에만 반영합니다. 1.x는 v2.0의 라이선스 경계 이전 버전이라
더 이상 갱신하지 않습니다.

## Security Architecture

- **appkey/secretkey**: `keyring`을 통해 **OS 키체인**(macOS Keychain / Windows
  Credential Manager / Linux Secret Service)에 저장. 키 형식은 `{profile}:appkey`,
  `{profile}:secretkey`. 파일에 평문으로 남지 않습니다.
- **토큰**: 같은 키체인에 `{profile}:token`으로 저장. `token_storage = env`를
  선택하면 키체인에 저장하지 않고 사용자가 `KIWOOM_TOKEN` 환경변수로 직접
  관리합니다(키체인 접근이 불가능한 샌드박스·CI·에이전트 환경용).
- **앱 자체 암호화 계층은 없습니다.** 암호화 경계는 OS 키체인입니다 —
  `gh`, `aws`, `docker` CLI와 같은 모델입니다. 비밀번호·생체인증 프롬프트가
  없으므로 크론잡·CI·AI 에이전트가 그대로 사용할 수 있습니다. 배경은 아래
  [설계 원칙](#설계-원칙-왜-앱-비밀번호-계층이-없는가) 참고.
- **config.toml**: 도메인, 계좌번호, 프로필, `token_storage`만 저장합니다.
  민감정보는 들어가지 않습니다.
- **파일 권한**: `~/.kiwoom`은 0700, `config.toml`·멱등성 원장·레코딩 파일은
  0600. 매 실행 시 느슨한 권한을 조입니다(v2.8.0).
- **프로필 이름**: `^[A-Za-z0-9_-]{1,64}$` allowlist로 검증합니다 — 경로
  조작을 막기 위함입니다.
- **주문**: 실행 전 주문 내용 미리보기 + 대화형 확인 프롬프트(y/n). 자동화 시
  `--confirm`으로 생략합니다. `-f json`/`-f csv` 모드에서는 프롬프트 없이
  `CONFIRMATION_REQUIRED`로 exit 1 — 에이전트가 응답 없는 프롬프트에서
  멈추지 않도록 하기 위함입니다.
- **raw API**: `kiwoom api`로 직접 호출할 때도 주문 계열 API(17개)에는 같은
  확인 게이트가 걸립니다.
- **배포**: PyPI Trusted Publishing(OIDC)으로 게시하며, 장기 API 토큰을
  저장하지 않습니다. `main`은 PR·CI 통과를 요구하는 보호 규칙 아래 있습니다.

### 설계 원칙: 왜 앱 비밀번호 계층이 없는가

v2.0까지는 appkey/secretkey를 앱 자체 비밀번호(PBKDF2 + Fernet)로 한 번 더
암호화했습니다. **v2.1에서 이 계층을 의도적으로 제거했습니다:**

- **자동화가 불가능해집니다.** 대화형 비밀번호 프롬프트는 크론잡, CI, AI
  에이전트가 답할 수 없습니다. 자동화하려면 결국 비밀번호를 파일이나
  환경변수에 평문으로 두게 되어 보안 계층이 형식만 남습니다.
- **마찰 대비 이득이 없습니다.** 공격자가 이미 사용자 계정으로 로컬 셸을
  확보했다면 앱 비밀번호는 키로거·메모리 덤프로 우회됩니다. 실제로 방어해야
  하는 것은 원격·파일 수준 노출이고, 그건 키체인이 해결합니다.

같은 이유로 OS 시스템 인증(Touch ID 등)도 검토 후 채택하지 않았습니다 —
AI 에이전트가 지문을 제시할 수 없어, 이 도구의 핵심 사용처를 막습니다.

## Threat Model

**방어 대상:**
- 저장소·백업·설정 파일 동기화를 통한 인증정보 유출 (키체인에만 두어 해결)
- 같은 머신의 다른 사용자 계정 (파일 권한 0700/0600)
- 의도치 않은 주문 전송 (미리보기 + 확인 게이트 + `--dry-run` + 멱등키)
- 모의/실거래 혼동 (`meta.env`, `config show`/`auth status`가 **실제 접속
  도메인**을 보고 — v2.14.0에서 수정)

**방어 대상이 아닌 것:**
- 사용자 계정을 이미 장악한 로컬 공격자 (키체인 잠금 해제 상태에서는 어떤
  앱 계층도 막지 못합니다)
- 키움 서버 측 침해
- `KIWOOM_TOKEN`을 셸 히스토리·프로세스 목록에 노출하는 사용 방식

## Reporting a Vulnerability

보안 취약점을 발견하셨다면 **공개 이슈로 등록하지 마시고** 아래 방법으로
비공개 제보해 주세요:

1. GitHub의 [Security Advisories](https://github.com/gejyn14/kiwoom-cli/security/advisories/new)를 통해 비공개 보고
2. 또는 레포지토리 관리자에게 직접 연락

### 제보 시 포함해 주세요:
- 취약점 설명
- 재현 방법
- 영향 범위
- (가능하다면) 수정 제안

### 응답 시간
- 확인: 48시간 이내
- 초기 평가: 1주일 이내
- 수정 배포: 심각도에 따라 결정

## Best Practices for Users

- 모의투자 환경에서 먼저 테스트하세요 (`kiwoom config set domain mock`).
  현재 어떤 도메인에 붙는지는 `kiwoom config show` 또는 `-f json`의
  `meta.env`로 확인할 수 있습니다.
- `KIWOOM_DOMAIN` 환경변수는 **모든 프로필의 설정을 덮습니다.** 셸에
  export해 둔 것을 잊고 실거래로 주문하는 사고가 가장 흔합니다.
- 주문 확인을 생략하는 `--confirm`은 신뢰할 수 있는 자동화 환경에서만
  사용하세요. 먼저 `--dry-run`으로 전송될 body를 확인하는 것을 권합니다.
- 재시도 가능한 자동화에는 `--client-order-id`(멱등키)를 쓰세요. 같은 키로
  같은 내용을 재실행하면 재전송 없이 이전 응답을 돌려줍니다.
- 정기적으로 최신 버전을 유지하세요. 설치 방식에 맞는 명령을 쓰면 됩니다:
  `uv tool upgrade kiwoom-cli` / `pipx upgrade kiwoom-cli` / `pip install --upgrade kiwoom-cli`
