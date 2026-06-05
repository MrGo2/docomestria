# Contributing

Thanks for your interest in improving Docomestria.

## Development setup

```bash
git clone https://github.com/MrGo2/docomestria.git
cd docomestria
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Running tests

```bash
pytest
```

Tests that exercise the heavy engines (LiteParse, Docling) are marked with
`@pytest.mark.integration` and skipped by default. To run them locally:

```bash
pytest -m integration
```

## Coding rules

- Python 3.10+ syntax. Use `from __future__ import annotations` in every module.
- Frozen dataclasses for all data objects. No mutation — return new copies.
- Keep files focused. 400 lines is a soft cap.
- Type hints on every public signature.
- Run `ruff check` and `ruff format` before committing (pre-commit does this).

## Pull requests

1. Open an issue first for non-trivial changes so we agree on the approach.
2. Branch from `main`. Use conventional commits (`feat:`, `fix:`, `docs:`, etc.).
3. Add or update tests. The CI runs on Python 3.10, 3.11, and 3.12.
4. Update `CHANGELOG.md` under `[Unreleased]`.
5. Keep PRs focused — one logical change per PR is easier to review.

## License

By contributing you agree that your contributions are licensed under the MIT
License (see `LICENSE`).
