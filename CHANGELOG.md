# Changelog

## [Unreleased]
### Added
- Tests that call the command line code directly (74 tests in total), so coverage can be measured
- Test coverage reporting (line and branch) in CI
- Ruff linting in CI and type hints on all public functions

## [0.1.0] - 2026-10-21
### Added
- `init`, `check`, `update` and `watch` commands
- SHA-256 hashing plus permission, owner, size, mtime and symlink tracking
- Exclude patterns, text and JSON output, `--quiet` mode and exit codes
- Summarized warnings with `--verbose` to list everything
- Automated tests (42) and MIT license
