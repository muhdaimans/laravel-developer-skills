# Laravel Error Catalog

## Environment Difference Method

When something works in one place only, compare, then explain each difference.

```bash
php -v
php -m
php artisan about
php artisan config:show app
php artisan migrate:status
composer show --locked | grep -E 'laravel/framework'
git rev-parse HEAD
```

Check in this order: deployed commit, `composer.lock` installed, PHP version and extensions, cached config, env values, migrations, data, file permissions, proxy and HTTPS, OS case sensitivity.

Do not paste production secrets into chat or logs. Compare names and shapes.

## HTTP and Routing

| Error | Cause | Fix |
| --- | --- | --- |
| 404 on an existing route | Stale route cache, wrong method, earlier wildcard route | `php artisan route:clear`, `route:list`, reorder |
| 404 from implicit binding | Missing or soft-deleted model, or scoped child mismatch | `->withTrashed()`, check the key |
| 405 Method Not Allowed | Form method mismatch; redirect turned POST into GET (often HTTP to HTTPS) | `@method`, fix URL scheme |
| 413 | Upload over a limit | Nginx `client_max_body_size`, PHP `upload_max_filesize`, `post_max_size` |
| 419 | CSRF or session lost | Details below |
| 500 blank page | Error before Laravel can render, unwritable storage | Web server and PHP-FPM logs |
| 502 / 504 | PHP-FPM crash or timeout | FPM log, `request_terminate_timeout` |
| Redirect loop or `http://` links | Proxy not trusted | `trustProxies()`, `APP_URL` |
| Wrong client IP | Proxy not trusted | Configure trusted proxies with care |

### 419 Checklist

1. Form includes `@csrf`, or SPA sends `X-XSRF-TOKEN`.
2. `SESSION_DOMAIN` matches the host.
3. `SESSION_SECURE_COOKIE=true` is only used over HTTPS.
4. Session store is shared across servers (`redis` or `database`, not `file`).
5. The page wasn't open past `SESSION_LIFETIME`.
6. Trusted proxies are configured so HTTPS is detected.
7. Laravel 13 only: `Sec-Fetch-Site` origin check, for cross-site or unusual clients.

## Boot and Autoload

| Error | Cause | Fix |
| --- | --- | --- |
| `Class "App\X" not found` works on macOS, fails on Linux | Case-insensitive local filesystem | Match file and class case exactly |
| `Target [Interface] is not instantiable` | No binding | Bind in a provider |
| `Unable to resolve dependency [Parameter #0 ...]` | Scalar constructor argument | Contextual binding, or a config value |
| `Please provide a valid cache path` | Missing `storage/framework/*` | Create the folders |
| `bootstrap/cache directory must be present and writable` | Permissions | Fix owner and mode |
| Composer `platform_check` error | PHP version below requirement | Match web and CLI PHP versions |
| `Cannot redeclare` | Helpers loaded twice, or polyfill conflict | Check `composer.json` `files` |

## Database

| Error | Cause | Fix |
| --- | --- | --- |
| `[2002] Connection refused` | Wrong host or service down | Port, service name, `127.0.0.1` vs `localhost` |
| `[1045] Access denied` | Credentials, or a `#` in an unquoted env value | Quote the value |
| `[1040] Too many connections` | Worker and FPM count exceed the limit | Reduce workers, add a pooler |
| `Specified key was too long` | Old MySQL index limit | `Schema::defaultStringLength(191)`, or upgrade |
| `[23000]` Integrity constraint | Duplicate or a foreign key failure | Validate, handle the race |
| `Deadlock found` / `40P01` | Lock ordering | Retry via `DB::transaction($fn, 3)`, order locks |
| `Lock wait timeout exceeded` | Long transaction holding rows | Find the blocker, shorten transactions |
| `current transaction is aborted` | PostgreSQL error inside a transaction | Find the first error, use a savepoint |
| `MySQL server has gone away` | Idle timeout, or packet too large | Reconnect for long jobs, `max_allowed_packet` |
| `No such table` in tests | Trait missing | Add `RefreshDatabase` |
| `Column not found` after deploy | Migration not run | `migrate:status` |
| `LazyLoadingViolationException` | Strict mode found an N+1 | Eager load |
| `MassAssignmentException` | Attribute not in `$fillable` | Add deliberately |
| `MissingAttributeException` | Attribute not selected | Add to `select()` |

## Config and Cache

| Error | Cause | Fix |
| --- | --- | --- |
| Env change has no effect | Config cached, or the service not restarted | `config:cache`, restart workers |
| `env()` returns `null` | Used outside `config/` with cached config | Move into config |
| `config:cache` throws `Unable to prepare route` or a serialize error | Closure in config | Replace with a class or scalar |
| `route:cache` fails on duplicate name | Two routes share a name | Rename |
| Cache `__PHP_Incomplete_Class` | Class renamed, or Laravel 13 `serializable_classes` | Flush the key, allow-list, or cache arrays |
| `This cache store does not support tagging` | `file` or `database` driver | Use `redis` |

## Laravel 13 Session and Cache Changes

After syncing config files with the skeleton, sessions may be invalidated if `session.serialization` moved from `php` to `json`. Set it back to `php` to keep existing sessions. Cached PHP objects fail to restore with `serializable_classes => false`; list the classes, or cache arrays.

## Files and Storage

| Error | Cause | Fix |
| --- | --- | --- |
| `Permission denied` on `laravel.log` | Log created by root via CLI | Run CLI as the web user, fix ownership |
| 404 for `/storage/*` | No symlink | `php artisan storage:link` |
| `Disk [x] does not have a configured driver` | Missing filesystem config | `config/filesystems.php` |
| `League\Flysystem\UnableToWriteFile` | Disk full, or bad credentials | `df -h`, bucket policy |

## Front End

| Error | Cause | Fix |
| --- | --- | --- |
| `Vite manifest not found` | Build not run | `npm ci && npm run build` |
| Assets return 404 | `ASSET_URL` or `APP_URL` wrong | Fix config |
| Mixed-content warnings | Proxy HTTPS not detected | Trust proxy, `URL::forceScheme('https')` as a last resort |

## Mail and External Services

| Error | Cause | Fix |
| --- | --- | --- |
| `cURL error 28` | Timeout | Set `Http::timeout()`, inspect the provider |
| `cURL error 60` | CA bundle | Update CA certificates. Never disable verification |
| Mail "sent" but never arrives | `log` mailer, or queued without a worker | `MAIL_MAILER`, `queue:failed` |

## PHP

| Error | Cause | Fix |
| --- | --- | --- |
| `Attempt to read property on null` | Missing relation or record | Find why, use `findOrFail` or a guard |
| `Maximum execution time exceeded` | Slow request | Queue the work |
| `Too few arguments to function` | Route parameter or DI mismatch | Compare the signature and route |
| `Cannot assign ... to property of type` | Typed property with wrong value | Validate or cast earlier |
| `Typed property must not be accessed before initialization` | Unset property | Initialize |
| `Implicitly nullable parameter is deprecated` | PHP 8.4 | Change `Foo $x = null` to `?Foo $x = null` |
