# Laravel and PHP Version Matrix

Shared by every skill. Source of truth: `shared/version-matrix.md` in the plugin repository. Last verified 2026-10-30 against the official Laravel and PHP support pages and the Laravel 13.39 source.

## Detect before advising

```bash
php -v | head -1
php artisan --version
composer show --locked laravel/framework | grep -E '^versions'
composer show --locked --direct
grep -E '"php"' composer.json
```

If the app cannot boot, read `composer.lock` directly. The locked version is what runs; the `composer.json` constraint is only a range.

Then detect the **structure**, which does not always follow the version. Upgraded applications often keep the old layout:

```bash
ls app/Http/Kernel.php app/Exceptions/Handler.php app/Providers/RouteServiceProvider.php 2>/dev/null
grep -n 'withMiddleware\|withExceptions\|withRouting' bootstrap/app.php
```

Any of the three legacy files present means that concern is still configured the old way, even on Laravel 12 or 13. Follow what the project uses; never move it as a side effect of another task.

**If a minimum version here is uncertain, the installed source decides:**

```bash
grep -rn 'function whereAny' vendor/laravel/framework/src
```

## Support status (as of 2026-10-30)

| Laravel | PHP | Released | Bug fixes until | Security fixes until | Status |
| --- | --- | --- | --- | --- | --- |
| 10 | 8.1 – 8.3 | 2023-02-14 | 2024-08-06 | 2025-02-04 | End of life |
| 11 | 8.2 – 8.4 | 2024-03-12 | 2025-09-03 | 2026-03-12 | End of life |
| 12 | 8.2 – 8.5 | 2025-02-24 | 2026-08-13 | 2027-02-24 | Security fixes only |
| 13 | 8.3 – 8.5 | 2026-03-17 | Q3 2027 | 2028-03-17 | Active |

| PHP | Active support until | Security support until |
| --- | --- | --- |
| 8.2 | 2024-12-31 | 2026-12-31 |
| 8.3 | 2025-12-31 | 2027-12-31 |
| 8.4 | 2026-12-31 | 2028-12-31 |
| 8.5 | 2027-12-31 | 2029-12-31 |

Mention an end-of-life version as a finding once. Do not turn an unrelated task into an upgrade.

## Skeleton differences

| Concern | Legacy layout (default on 10) | Streamlined layout (default on 11+) |
| --- | --- | --- |
| Middleware | `app/Http/Kernel.php` | `withMiddleware()` in `bootstrap/app.php` |
| Exceptions | `app/Exceptions/Handler.php` | `withExceptions()` in `bootstrap/app.php` |
| Routes and rate limiters | `RouteServiceProvider` | `withRouting()`; limiters in `AppServiceProvider::boot()` |
| Scheduler | `app/Console/Kernel.php` | `routes/console.php` with the `Schedule` facade |
| API routes | Present by default | Added by `php artisan install:api` |
| Base controller | Has `AuthorizesRequests`, `ValidatesRequests` | Empty: `$this->authorize()` is unavailable unless the trait is added |
| Config files | All published | Fewer; publish with `php artisan config:publish <name>` |

## Feature gates

| Feature | Minimum |
| --- | --- |
| `whereAll()`, `whereAny()` | late 10.x |
| `toRawSql()`, `dumpRawSql()` | 10.x |
| `casts()` method on models | 11 |
| `once()`, `Context` facade, `Limit::perSecond()` | 11 |
| `defer()`, `Concurrency` facade | 11.x |
| `/up` health route via `withRouting(health:)` | 11 |
| `APP_PREVIOUS_KEYS` key rotation | 11 |
| `whereLike()` | 11 |
| `Model::automaticallyEagerLoadRelationships()` | 12.x |
| `#[Scope]` Eloquent attribute | 12 |
| `Queue::route()` | 13 |
| `#[Tries]`, `#[Backoff]`, `#[Timeout]`, `#[FailOnTimeout]` on jobs | 13 |
| `#[Middleware]`, `#[Authorize]` on controllers | 13 |
| `#[Table]`, `#[Fillable]`, `#[Hidden]` on models | 13 |
| `PreventRequestForgery` (replaces `VerifyCsrfToken`) | 13 |
| `Cache::touch()`, first-party JSON:API resources, `whereVectorSimilarTo()` | 13 |

## Changes that affect existing code

- **11:** `->change()` in a migration must restate every column modifier, or the modifier is dropped. `doctrine/dbal` is no longer needed. `ThrottlesExceptions` takes its decay in seconds, not minutes.
- **13:** `cache.serializable_classes` defaults to `false` in the skeleton, so cached PHP objects need an allow-list. New skeletons set `session.serialization` to `json`; switching an existing app logs everyone out. Framework fallback prefixes now use hyphens, so set `CACHE_PREFIX`, `REDIS_PREFIX` and `SESSION_COOKIE` explicitly if you rely on them. `upsert()` throws on empty `uniqueBy`. `JobAttempted->exceptionOccurred` became `->exception`. `QueueBusy->connection` became `->connectionName`. Prefer `Arr::first()` over the global `array_first()` introduced by the PHP 8.5 polyfill.

## Test tooling

| Laravel | PHPUnit | Pest |
| --- | --- | --- |
| 10 | 10 | 2 |
| 11 | 10 or 11 | 2 or 3 |
| 12 | 11 | 3 |
| 13 | 12 | 4 (requires PHP 8.3+) |

These are the usual pairings. The lock file is authoritative.

## PHP language features

| PHP | Useful in Laravel code | Avoid |
| --- | --- | --- |
| 8.2 | `readonly` classes for DTOs, `true`/`false`/`null` types | Dynamic properties on non-`stdClass` objects (deprecated) |
| 8.3 | Typed class constants, `#[\Override]`, `json_validate()` | |
| 8.4 | Property hooks, asymmetric visibility, `array_find()`, `new Foo()->bar()` | Implicit nullable parameters such as `Foo $x = null` (deprecated) |
| 8.5 | Pipe operator, `#[\NoDiscard]`, `clone()` with properties | Backtick shell operator and non-canonical casts such as `(integer)` (deprecated) |

Use a language feature only if the `php` constraint in `composer.json` guarantees it. Never put property hooks or `readonly` on Eloquent attributes: Eloquent stores attributes in `$attributes` and reads them through magic methods.
