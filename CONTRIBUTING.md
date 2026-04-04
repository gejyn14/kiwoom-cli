# Contributing to kiwoom-cli

감사합니다! kiwoom-cli에 기여해 주셔서 감사합니다.

## Getting Started

```bash
git clone https://github.com/gejyn14/kiwoom-cli.git
cd kiwoom-cli
pip install -e ".[dev]"
```

## Development Workflow

1. `main` 브랜치에서 새 브랜치 생성: `git checkout -b feature/my-feature`
2. 코드 작성
3. 테스트 실행: `pytest tests/ -v`
4. 린트 확인: `ruff check kiwoom_cli/`
5. 커밋 후 PR 생성

## Code Style

- Python 3.10+ 타입 힌트 사용 (`X | None`, `list[str]`)
- `ruff`로 린트 — PR 전에 `ruff check kiwoom_cli/` 통과 필수
- 한국어 docstring, 영어 코드
- Click 기반 CLI 패턴 준수 (CLAUDE.md 참고)

## Adding a New Command

1. 해당 `commands/*.py` 파일에 커맨드 추가
2. `api_spec.py`에 API ID 등록
3. 옵션 값은 human-readable (`kospi`, `KRX` 등), `_constants.py`의 공유 맵 사용
4. `print_api_response()` 또는 `print_generic_table()`로 출력
5. 테스트 추가

## Testing

```bash
pytest tests/ -v          # 전체 테스트
pytest tests/test_cli.py  # CLI 테스트만
ruff check kiwoom_cli/    # 린트
```

## Commit Messages

```
feat: add new feature
fix: fix bug description
refactor: refactor code
docs: update documentation
```

## Reporting Issues

버그 리포트 시 포함해 주세요:
- 실행한 명령어
- 에러 메시지 전문
- `kiwoom --version` 출력
- OS 및 Python 버전
