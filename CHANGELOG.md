# Changelog

All notable changes to this project will be documented in this file.

## [1.6.0] - 2026-04-05

### Added
- Added playbook node-name focus keywords for extracting key execution results in the admin UI.
- Added `query_playbook_execution_overview_by_activity_id` and `query_playbook_execution_key_results_by_activity_id`.
- Added `migrate_db.py` for explicit, idempotent SQLite schema migration before service startup.
- Added server version display in the admin header, footer, and stats page.

### Changed
- Split execution result queries into overview and key-results semantics.
- Added automatic migration for `playbooks.result_focus_keywords` during database initialization.
- Refined playbook detail modal layout and tightened spacing for denser information display.

## [1.5.2] - 2026-03-28

### Added
- Added first-run onboarding for SOAR platform initialization in the admin console.
- Added admin password rotation with current-password verification, strength checks, and session invalidation.
- Added a dedicated top-level "密码管理" page in the admin UI.

### Changed
- Moved SOAR runtime configuration fully into database-backed admin settings.
- Clarified sample configuration and documentation to avoid treating `.env` as live SOAR runtime config.
- Updated the admin configuration page to include SSL verification control and improved onboarding guidance.

### Fixed
- Fixed shared SOAR HTTP client recreation when timeout or SSL verification settings change.
- Fixed the password management view nesting bug in the admin template so it behaves as an independent page.
- Fixed the admin connection test flow to use the actual submitted configuration payload.

## [1.5.0] - 2025-09-26

### Added
- Added HTTP Bearer Token authentication alongside URL query token compatibility.
- Added token management improvements and expanded authentication test coverage.

### Notes
- Historical release write-up: `docs/pr/release-v1.5.0.md`
