---
name: laravel-debugging
description: Use when a Laravel application errors, misbehaves, or differs between environments, including 500 errors, stack traces, 419 Page Expired, class not found, target class does not exist, SQLSTATE errors, config cache issues, permission errors, and works-locally-but-not-in-production problems.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel Debugging

Find the cause before changing code. Each fix must explain the symptom, or it is a guess.

## When to Use

- An exception, a blank page, or a wrong result
- It works locally but not on staging or production
- A previously working feature broke after a deploy or upgrade

For queue-specific symptoms, go to `laravel-queue-horizon`. For slowness, go to `laravel-eloquent-optimization`. For 401 and 419 in depth, see `laravel-authentication`.

## Inspect the Project First

```bash
php artisan --version
php artisan about
git log --oneline -10
git status --short
tail -n 80 storage/logs/laravel.log
```

`about` shows environment, debug state, cached config/routes/events, and drivers. On production, read only: do not enable `APP_DEBUG`, do not run `optimize:clear` during an incident without saying why, and do not run migrations or data changes without approval. Use [version-matrix.md](references/version-matrix.md) when behaviour changed after an upgrade.

## Workflow

1. **Capture the exact error:** message, exception class, the first stack frame in `app/`, the URL or command, the user and the time.
2. **Reproduce it** with the smallest request, command or test. Write a failing test when you can.
3. **Classify the layer** to narrow the search:

   | Symptom | Layer |
   | --- | --- |
   | No Laravel error page, web server 502/504 | Nginx, PHP-FPM, or a crash |
   | Error appears before routing | Bootstrap, config, autoload |
   | 404 for a route that exists | Route cache, method, binding, order |
   | 500 inside an app frame | Application code |
   | `SQLSTATE` | Schema, data or connection |
   | Works in one environment only | Config, env, versions, data, permissions |

4. **Find what changed:** recent commits, `composer.lock`, env, data, infrastructure.
5. **Form one hypothesis,** then test it by inspecting state, not by editing and hoping:

   ```bash
   php artisan config:show database
   php artisan route:list --path=orders
   php artisan model:show Order
   php artisan tinker
   php artisan pail --filter="order"
   ```

6. **Fix the cause,** at the source. Do not wrap in `try/catch` or add `?->` to silence it.
7. **Add a regression test,** then remove all temporary instrumentation.

## Core Pattern: Instrument with Context

Temporary logs beat `dd()` for requests, jobs and anything concurrent:

```php
use Illuminate\Support\Facades\Log;

Log::debug('Applying discount', [
    'order_id' => $order->id,
    'coupon' => $coupon?->code,
    'subtotal' => $subtotal,
]);
```

Attach a correlation ID to every log line in a request:

```php
<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Context;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Response;

class AssignRequestId
{
    public function handle(Request $request, Closure $next): Response
    {
        $id = (string) Str::uuid();

        Context::add('request_id', $id); // Laravel 11+. Also propagates to queued jobs.

        return tap($next($request), fn ($response) => $response->headers->set('X-Request-Id', $id));
    }
}
```

On Laravel 10, use `Log::shareContext()`.

## Core Pattern: Inspect SQL

```php
Order::query()->where('status', 'paid')->dumpRawSql();

DB::enableQueryLog();
$service->run();
dump(DB::getQueryLog());
```

## Fast Triage

| Message | Usual cause | First check |
| --- | --- | --- |
| `No application encryption key` | Missing `APP_KEY` | `.env`, cached config |
| `The MAC is invalid` | `APP_KEY` changed | Key history; `APP_PREVIOUS_KEYS` on 11+ |
| `419 Page Expired` | Session or CSRF | Token in form, cookie domain, HTTPS, session driver |
| `Route [login] not defined` | Guest hit an `auth` route with no `Accept: application/json`, in an app with no `login` route | Send the header; for APIs, `redirectGuestsTo()` (see `laravel-api-development`) |
| `Target class [X] does not exist` | Wrong namespace, or unbound interface | `composer dump-autoload`, binding |
| `Class "X" not found` | Case mismatch on Linux, or stale autoload | Filename vs class case |
| `env()` returns `null` | Config cached | Read through `config()` |
| `Vite manifest not found` | Assets not built | `npm run build` |
| `Permission denied` in `storage` | Ownership | `ls -la storage bootstrap/cache` |
| `SQLSTATE[HY000] [2002]` | DB unreachable | Host, port, network; `127.0.0.1` vs service name |
| `SQLSTATE[42S02]` / `42P01` | Table missing | `migrate:status` |
| `Allowed memory size exhausted` | Unbounded data | Chunk or paginate |

See [error-catalog.md](references/error-catalog.md) for more errors and an environment comparison method.

## Version Notes

- `php artisan config:show <file>` and `pail` need Laravel 10.x and `laravel/pail`, respectively. Otherwise use `tinker` and `tail -f`.
- The exception handler lives in `bootstrap/app.php` on the streamlined layout, or `app/Exceptions/Handler.php` on the legacy one.
- After upgrading to 13, check `serializable_classes` for cache errors on cached objects, and `session.serialization` for session errors. Both are explained in the matrix.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Changing several things at once | You can't tell what worked | One change per test |
| `php artisan optimize:clear` as a ritual | Hides a real config cause | Find out why it helped |
| `APP_DEBUG=true` on production | Leaks secrets and env | Read logs, use an error tracker |
| Adding `?->` to stop the error | Moves the bug downstream | Find out why it's null |
| Empty `catch` | Silent failure | `report($e)` or let it bubble |
| `chmod -R 777 storage` | Anyone can write executable content | Correct owner, `775` |
| `dd()` in a job or API test | Output disappears | `Log::debug()` |
| Trusting the first stack frame | Often framework or vendor | First frame in `app/` |
| Debugging from the error message alone | Previous exception holds the cause | Read the `previous` chain |
| Leaving debug code | Leaks data | `git diff`, grep for `dd(` |

## Verification

```bash
php artisan test --filter=RegressionTestName
php artisan test
git diff | grep -nE '^\+.*\b(dd|dump|ray|var_dump)\('
tail -n 20 storage/logs/laravel.log
```

- [ ] Root cause can be stated in one sentence
- [ ] A new test fails without the fix and passes with it
- [ ] The original reproduction now succeeds
- [ ] No debug code or temporary logging remains

## Additional Resources

- [error-catalog.md](references/error-catalog.md): error reference and environment diff method
- [version-matrix.md](references/version-matrix.md): behaviour changes between versions
