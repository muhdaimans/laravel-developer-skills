# Laravel Developer Skills

A Claude Code plugin with 13 skills for building, reviewing, securing, debugging, testing and deploying Laravel applications.

Every skill starts by inspecting your project, then adapts to the Laravel and PHP versions and the directory layout it finds.

| Coverage | Versions and tools |
| --- | --- |
| Laravel | 10, 11, 12, 13 |
| PHP | 8.2, 8.3, 8.4, 8.5 |
| Databases | MySQL, MariaDB notes, PostgreSQL |
| Queues | Redis, Horizon |
| Auth | Sanctum, Passport, Fortify, policies |
| Tests | Pest, PHPUnit |
| Delivery | Docker, Nginx, PHP-FPM, Supervisor |

## Installation

Replace `YOUR-GITHUB-USER` with the account that hosts this repository.

From your terminal:

```bash
claude plugin marketplace add YOUR-GITHUB-USER/laravel-developer-skills
```

```bash
claude plugin install laravel-developer-skills@laravel-developer-skills
```

Or inside a Claude Code session:

```text
/plugin marketplace add YOUR-GITHUB-USER/laravel-developer-skills
/plugin install laravel-developer-skills@laravel-developer-skills
```

To try it without installing:

```bash
git clone https://github.com/YOUR-GITHUB-USER/laravel-developer-skills.git
```

```bash
claude --plugin-dir ./laravel-developer-skills
```

To update, run `claude plugin update laravel-developer-skills@laravel-developer-skills`, and then restart your session.

## Skills

Skills activate automatically from your request. You can also call one directly, for example `/laravel-developer-skills:laravel-code-review`.

| Skill | Use it for |
| --- | --- |
| `laravel-best-practices` | Idiomatic controllers, requests, models, config, naming, Pint |
| `laravel-project-architecture` | Where code lives, Actions, DTOs, modules, safe refactoring |
| `laravel-eloquent-optimization` | N+1, EXPLAIN, indexes, memory, pagination, caching reads |
| `laravel-api-development` | REST endpoints, resources, errors, versioning, rate limits, idempotency |
| `laravel-authentication` | Sanctum, Passport, login flows, policies, 401 and 419 problems |
| `laravel-database-management` | Migrations, zero-downtime changes, transactions, MySQL vs PostgreSQL |
| `laravel-queue-horizon` | Reliable jobs, timeouts, batches, Horizon, queue incidents |
| `laravel-testing` | Pest and PHPUnit, fakes, flaky tests, speed, CI |
| `laravel-debugging` | Root-cause workflow and an error catalog |
| `laravel-code-review` | Severity-ranked PR review with evidence |
| `laravel-security-audit` | Application audit, OWASP mapping, hardening |
| `laravel-deployment` | Docker, servers, release scripts, rollback |
| `laravel-documentation` | README, OpenAPI, ADRs, runbooks, PHPDoc |

## Example Prompts

```text
This endpoint takes 4 seconds. Find out why and fix it.
Add a paginated orders API with Sanctum tokens and tests.
Rename the customers.name column on our production MySQL table without downtime.
Jobs are running twice in Horizon. Diagnose it.
Review this branch before I merge it.
Audit this app for security issues before launch.
Write a production Dockerfile for this project.
```

## How It Works

- **Inspect first.** Skills read `composer.lock`, config and neighbouring code before recommending anything. Project conventions outrank generic advice.
- **Version-aware.** Each skill includes [the same version matrix](shared/version-matrix.md). When in doubt, the instructions tell Claude to check your installed `vendor/` source.
- **Structure-aware.** An app upgraded to Laravel 12 may still have `app/Http/Kernel.php`. Skills check for the file, not only the version.
- **No forced dependencies.** Examples use the framework. A package is suggested only with a reason, and installation is your decision.
- **Progressive loading.** `SKILL.md` holds the workflow, and `references/` loads only when needed.

## Repository Layout

```text
.claude-plugin/    Plugin and marketplace manifests
skills/            One folder per skill: SKILL.md plus references/
shared/            Source of truth for files copied into each skill
scripts/           Validator and sync script
docs/              Maintainer notes, including topic ownership
```

## Contributing

1. Read [skill boundaries](docs/skill-boundaries.md) so that each topic stays in one skill.
2. Edit `shared/version-matrix.md`, never a copy, then run `bash scripts/sync-shared.sh`.
3. Validate:

   ```bash
   python3 scripts/validate-repo.py --lint-php
   ```

   ```bash
   claude plugin validate . --strict
   ```

4. Add a `CHANGELOG.md` entry and bump `version` in `.claude-plugin/plugin.json`. Users only receive an update when that version changes.

Keep claims verifiable. If a statement depends on a Laravel version, confirm it in the official docs or framework source.

## Limits

Skills guide Claude; they do not replace your review. Check migrations, security fixes and deployment changes before running them in production. The version matrix reflects support dates as of 2026-10-30.

## License

[MIT](LICENSE)
