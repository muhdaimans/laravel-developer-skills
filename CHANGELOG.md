# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-11-12

### Added

- House Rules in `laravel-best-practices`, with a new `references/house-rules.md`: service classes for repeated logic, a form request for every form, never clearing the database, enums instead of lookup tables for fixed option lists, and Blade components for repeated markup.
- Test-database check in `laravel-testing`, so `RefreshDatabase` cannot wipe a development database.
- House Rules section in the code review checklist.

### Changed

- `laravel-best-practices` precedence: House Rules now rank above project convention for new code.
- The thin controller example delegates to `OrderService` instead of an Action.
- `laravel-database-management` forbids `migrate:fresh`, `migrate:refresh`, `migrate:reset`, `db:wipe` and `truncate()` on every environment unless the user asks, and prefers enums over lookup tables for fixed lists.
- `laravel-project-architecture` defaults to service classes where a project has no Actions.

## [1.0.0] - 2026-10-30

### Added

- Thirteen Laravel skills: best practices, project architecture, Eloquent optimization, API development, authentication, database management, queues and Horizon, testing, debugging, code review, security audit, deployment, and documentation.
- Shared version matrix covering Laravel 10–13 and PHP 8.2–8.5.
- Plugin and marketplace manifests for Claude Code.
- Repository validator with PHP example linting, and a sync script for shared files.
