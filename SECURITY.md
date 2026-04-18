# Security Policy

## Supported Versions

| Version | Supported |
|---------|:---------:|
| 1.x     | ✓         |
| < 1.0   | ✗         |

## Security Architecture

- **appkey/secretkey**: SecureStore(Fernet AES-128-CBC + HMAC-SHA256)로 암호화 → `keyring` 라이브러리를 통해 OS 키체인(macOS Keychain, Windows Credential Locker, Linux SecretService)에 저장. 파일에 평문 없음
- **토큰**: `keyring`에 평문 저장 (만료되는 값이므로 별도 암호화 불필요). 키 형식: `{profile}:token`
- **비밀번호**: SecureStore 잠금 해제용. PBKDF2로 키 유도 후 Fernet 복호화에 사용. 저장되지 않음
- **config.toml**: 도메인, 계좌번호, 프로필 설정 등 비민감 정보만 저장
- **주문**: 시스템 인증 필수 (macOS: Touch ID, Windows: LogonUser, Linux: PAM). `dangerous-mode on` 시 비활성화

## Reporting a Vulnerability

보안 취약점을 발견하셨다면 **공개 이슈로 등록하지 마시고** 아래 방법으로 비공개 제보해 주세요:

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

- 모의투자 환경에서 먼저 테스트하세요 (`kiwoom config set domain mock`)
- `dangerous-mode`는 신뢰할 수 있는 환경에서만 활성화하세요
- 정기적으로 `pip install --upgrade kiwoom-cli`로 최신 버전을 유지하세요
