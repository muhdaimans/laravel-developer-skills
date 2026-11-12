# Documentation Templates

Replace every `<placeholder>`. Delete sections that don't apply.

## README

````markdown
# <Project name>

<One sentence: what it does, and for whom.>

## Stack

Laravel <x>, PHP <y>, <MySQL 8.4 / PostgreSQL 17>, Redis, Horizon.

## Requirements

- PHP <y> with extensions: <list from composer.json>
- Composer 2
- Node <version>
- <Database>, Redis

## Getting Started

```bash
git clone <repo-url>
cd <project>
composer install
cp .env.example .env
php artisan key:generate
# Create the database, then set DB_* in .env
php artisan migrate --seed
npm ci
npm run dev
php artisan serve
```

Sign in with <seeded test account, local only>.

## Common Commands

| Task | Command |
| --- | --- |
| Run tests | `php artisan test` |
| Format | `./vendor/bin/pint` |
| Static analysis | `./vendor/bin/phpstan analyse` |
| Run workers | `php artisan horizon` |

## Configuration

| Key | Purpose | Example |
| --- | --- | --- |
| `<KEY>` | <what it controls> | `<safe example>` |

## Architecture

<A paragraph, then a link to docs/adr/.>

## Deployment

<How releases happen, with a link to the runbook.>
````

## Architecture Decision Record

File: `docs/adr/0007-use-sanctum-for-mobile-tokens.md`. Number sequentially. Never rewrite an accepted ADR; add a new one that supersedes it.

```markdown
# 7. Use Sanctum for mobile API tokens

Date: 2026-10-30
Status: Accepted

## Context

The mobile app needs API authentication. No third party will act on behalf of users.

## Decision

Use Laravel Sanctum tokens, one per device, with 30-day expiry.

## Alternatives

- Passport: full OAuth2, more operational cost, no current need.
- JWT package: new dependency, harder revocation.

## Consequences

- Tokens are revocable per device.
- If third-party access is needed later, we add Passport for those clients.
```

## Runbook

```markdown
# Runbook: Queue backlog

Severity guide: wait above 5 minutes on `payments` is an incident.

## Symptoms

Horizon "long wait" alert, delayed emails, payment status stuck.

## Diagnose

1. `php artisan horizon:status`
2. Check failed jobs: `php artisan queue:failed`
3. Check Redis memory and database load in <dashboard link>.

## Mitigate

- Workers stopped: `sudo supervisorctl restart horizon`
- Paused: `php artisan horizon:continue`
- Dependency down: pause the affected supervisor, and tell <channel>.

## Verify

Wait time returns below threshold in <dashboard link>.

## Escalate

<Who to call, and when.>
```

Every command in a runbook must be tested, and destructive steps must be labelled.

## Changelog

Follow [Keep a Changelog](https://keepachangelog.com/) and semantic versioning. Write for the user of the software.

```markdown
## [2.4.0] - 2026-10-30

### Added
- Invoice PDF export.

### Changed
- `GET /orders` now returns a cursor. See the upgrade note.

### Fixed
- Duplicate receipt when a payment was retried.

### Security
- Rate limit on password reset.
```

## Upgrade Note

```markdown
# Upgrading to 3.0

Estimated effort: 30 minutes.

## Before you start

Back up the database. Requires PHP 8.3.

## Breaking changes

### `total` renamed to `total_cents`

Affects: API clients.
Action: read `total_cents`. Values are now minor units.

## Steps

1. `composer update`
2. `php artisan migrate --force`
3. `php artisan horizon:terminate`
```

## Laravel to OpenAPI Mapping

| OpenAPI | Laravel source |
| --- | --- |
| Paths and methods | `php artisan route:list --path=api --json` |
| Path parameters | Route definition; binding key from `getRouteKeyName()` |
| Request schema | `rules()` in the form request |
| `required` | `required` rule; `sometimes` is optional |
| `nullable` | `nullable` rule |
| `enum` | `Rule::enum()` / `Rule::in()` |
| `minimum`, `maxLength` | `min:`, `max:` rules (type-dependent) |
| Response schema | `toArray()` in the API resource |
| Optional response fields | `whenLoaded()`, `whenCounted()`, `when()` |
| Pagination | `paginate()` adds `links` and `meta`; `cursorPaginate()` uses `next_cursor` |
| Wrapper | `data` unless `withoutWrapping()` is called |
| 401 | `auth:*` middleware |
| 403 | Policy, ability middleware |
| 404 | Route model binding, handler |
| 422 | Form request, `{message, errors}` |
| 429 | `throttle:*` middleware |
| Security schemes | Sanctum or Passport guard |

## Environment Key Table

Generate the key list, then describe each by reading `config/`:

```bash
grep -oE '^[A-Z0-9_]+' .env.example | sort -u
grep -rhoE "env\('[A-Z0-9_]+'" config | sed "s/env('//" | sort -u
```

Keys only in the second list may be missing from `.env.example`.
