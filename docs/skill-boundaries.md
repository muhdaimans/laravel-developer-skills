# Skill Boundaries

Each topic has one owner. Other skills mention it in a sentence and name the owner, so guidance can't drift between copies.

| Topic | Owner | Others may |
| --- | --- | --- |
| Version detection and support dates | `shared/version-matrix.md` | Copy verbatim through `scripts/sync-shared.sh` |
| Naming, thin controllers, framework-first style | `laravel-best-practices` | Link |
| House Rules: service classes, form requests, never clearing the database, enums over lookup tables, Blade components | `laravel-best-practices` (`references/house-rules.md`) | State the rule in one line and name the owner |
| Layers, Actions, modules, events vs direct calls | `laravel-project-architecture` | Show Actions in examples |
| N+1, EXPLAIN, pagination cost, caching reads | `laravel-eloquent-optimization` | Flag in reviews |
| Migrations, schema, transactions, locks, engine differences | `laravel-database-management` | Link |
| Endpoints, resources, status codes, API errors, rate limits | `laravel-api-development` | Link |
| Sanctum, Passport, login, policies | `laravel-authentication` | Show `Gate::authorize()` calls |
| Job design, workers, Horizon | `laravel-queue-horizon` | Show dispatch calls |
| Test levels, fakes, flaky tests, CI test jobs | `laravel-testing` | Show focused tests in Verification sections |
| Root-cause process, error catalog | `laravel-debugging` | Link |
| Diff review and severity | `laravel-code-review` | None |
| App-wide vulnerability assessment | `laravel-security-audit` | Mention risks in Common Mistakes |
| Release order, Docker, servers, process supervision | `laravel-deployment` | Link |
| README, OpenAPI, ADRs, runbooks | `laravel-documentation` | Link |

## Accepted Repetition

- Every skill has an Inspect section and a Common Mistakes table. Items may touch the same idea from a different angle, such as `env()` usage, which is a style rule in `laravel-best-practices` and a triage entry in `laravel-debugging`.
- Sanctum's route-protection example appears in authentication and in API development because each needs it to be complete.
- The test-database check appears in `laravel-best-practices` and `laravel-testing`, because either skill may be the only one loaded when tests are about to run.
- The Timeout Rule is only in `laravel-queue-horizon`, and Supervisor config for Horizon only in its `horizon.md`.

When changing a fact in one file, search for it first:

```bash
grep -rn 'retry_after' skills
```
