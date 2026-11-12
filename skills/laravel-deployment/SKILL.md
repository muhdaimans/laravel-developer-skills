---
name: laravel-deployment
description: Use when writing a Dockerfile or Compose file for a Laravel app, deploying it, or preparing it for production, including Nginx and PHP-FPM servers, release scripts, zero-downtime deploys, rollbacks, OPcache, config caching, schedulers, workers, health checks, and CI/CD pipelines.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel Deployment

A deployment is a repeatable script with a known rollback. Build once, configure by environment, migrate compatibly, restart what caches code.

## When to Use

- First production deploy
- Writing a Dockerfile, Compose file or release script
- Configuring Nginx, PHP-FPM, Supervisor or cron
- Designing CI/CD or a rollback

Breaking schema changes belong to `laravel-database-management`. Queue tuning belongs to `laravel-queue-horizon`.

## Inspect the Project First

```bash
php artisan --version
grep -E '"php"' composer.json
ls Dockerfile docker-compose.yml compose.yaml .github/workflows deploy* 2>/dev/null
php artisan about
composer show --locked | grep -E 'horizon|octane|reverb|pulse'
grep -E '^(CACHE_STORE|CACHE_DRIVER|SESSION_DRIVER|QUEUE_CONNECTION|FILESYSTEM_DISK)=' .env.example
```

Establish the target (container, VPS, Forge, Cloud, Vapor), the number of app servers, and which processes must run: web, workers, scheduler, Reverb. A managed platform handles much of this, so use its release hooks. See [version-matrix.md](references/version-matrix.md) for runtime support.

## Workflow

1. **Production-readiness check:** stateless app (sessions, cache, and uploads off local disk if several servers), `APP_DEBUG=false`, HTTPS, trusted proxies, logs to `stderr` in containers.
2. **Pick a strategy:**

   | Target | Approach |
   | --- | --- |
   | One VPS | Atomic symlink releases, see [server.md](references/server.md) |
   | Several VPS | Same, with a load balancer and shared Redis and storage |
   | Containers | Immutable image, see [docker.md](references/docker.md) |
   | Forge, Cloud, Vapor | Platform deploy hooks with the same ordering |

3. **Sequence the release** as below.
4. **Add health checks and a post-deploy smoke test.**
5. **Rehearse rollback** before you need it.
6. **Monitor** error rate, queue wait and latency after release.

### Release Order

```text
Build:   composer install --no-dev, npm ci && npm run build
Prepare: link shared storage and .env
Migrate: php artisan migrate --force --isolated     (backward-compatible only)
Cache:   php artisan optimize
Switch:  point traffic to the new release
Reload:  reload PHP-FPM, restart workers
Verify:  health check, smoke test
```

Migrate before switching, so new code never meets an old schema. This requires old code to tolerate the new schema, hence expand-and-contract.

## Core Pattern: A Release Script

Atomic releases on a single server:

```bash
#!/usr/bin/env bash
set -euo pipefail

APP=/var/www/app
RELEASE="$APP/releases/$(date +%Y%m%d%H%M%S)"
REF="${1:?usage: deploy.sh <git-ref>}"

git clone --depth 1 --branch "$REF" git@github.com:acme/app.git "$RELEASE"
cd "$RELEASE"

composer install --no-dev --no-interaction --prefer-dist --optimize-autoloader
npm ci && npm run build

rm -rf storage
ln -s "$APP/shared/storage" storage
ln -s "$APP/shared/.env" .env

php artisan migrate --force --isolated
php artisan optimize

ln -sfn "$RELEASE" "$APP/current.new"
mv -T "$APP/current.new" "$APP/current"

sudo systemctl reload php8.4-fpm
php artisan horizon:terminate
curl --fail --silent --show-error --max-time 10 https://example.com/up

ls -1dt "$APP"/releases/* | tail -n +6 | xargs -r rm -rf
```

`mv -T` is atomic on Linux, whereas `ln -sfn` directly on the live link is not. Replace `horizon:terminate` with `queue:restart` for plain workers.

**Rollback:** repoint `current` to the previous release, reload PHP-FPM and restart workers. Don't roll back migrations automatically: with expand-and-contract, the old code still works.

## Health Checks

Laravel 11+ ships `/up` via `withRouting(health: '/up')`. It confirms that the app boots. Add dependency checks in the `DiagnosingHealth` event when load balancers should see them:

```php
use Illuminate\Foundation\Events\DiagnosingHealth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Redis;

Event::listen(function (DiagnosingHealth $event) {
    DB::connection()->getPdo();
    Redis::ping();
});
```

Liveness probes shouldn't depend on the database, or a DB blip restarts every container. Keep `/up` simple for liveness, and use dependency checks for readiness.

## Required Processes

| Process | Command | Run by |
| --- | --- | --- |
| Web | Nginx + PHP-FPM | systemd, or containers |
| Queue | `php artisan horizon` or `queue:work` | Supervisor, systemd, container |
| Scheduler | `php artisan schedule:run` each minute | cron, or `schedule:work` container |

Run exactly one scheduler per environment, or use `onOneServer()` with a shared cache.

## Version Notes

- `optimize` caches config, events, routes and views on current versions. Check the output on older versions.
- Laravel 12 remains on security fixes only until 2027-02-24. Laravel 13 needs PHP 8.3+, so upgrade PHP before Composer dependencies.
- `/up` is Laravel 11+. On 10, add a simple route.
- Skeleton env keys vary: `CACHE_STORE` on 11+, `CACHE_DRIVER` on 10.
- After 13, set `CACHE_PREFIX`, `REDIS_PREFIX` and `SESSION_COOKIE` explicitly if you relied on generated fallbacks.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| `php artisan config:cache` during `docker build` | Bakes build-time env, or none | Run at container start |
| `composer install` without `--no-dev` | Dev tools in production | `--no-dev --optimize-autoloader` |
| `.env` in the image | Secret in every layer | Runtime environment, secret store |
| Forgetting to reload PHP-FPM | OPcache serves old code | Reload after switching |
| Forgetting workers | Workers run old code | `horizon:terminate` or `queue:restart` |
| Migrating in each container's entrypoint | Race across replicas | One-off migration task |
| `git pull` in the live directory | Half-updated app under traffic | Build a release, then switch |
| `storage` inside each release | Uploads vanish on deploy | Shared directory |
| `file` session and cache with several servers | Random logouts | Redis or database |
| Scheduler running on all servers | Duplicate runs | One runner, or `onOneServer()` |
| `migrate:fresh` in a deploy script | Data loss | Never |
| `APP_KEY` regenerated on deploy | Sessions and encrypted data lost | Treat as persistent secret |
| `chmod -R 777` | World-writable code | Correct owner and `775` |

## Verification

```bash
curl -fsS https://example.com/up
php artisan about --only=cache,environment
php artisan migrate:status | tail -5
php artisan horizon:status
php artisan schedule:list
curl -sI https://example.com | head -5
```

- [ ] `APP_DEBUG` false, `APP_ENV` production
- [ ] Config, routes and views cached
- [ ] Health endpoint passes via the public URL
- [ ] Workers show a start time after the deploy
- [ ] A scheduled task ran
- [ ] A test error reaches your error tracker
- [ ] Rollback executed once in staging

## Additional Resources

- [docker.md](references/docker.md): multi-stage Dockerfile, Compose, entrypoint, worker and scheduler containers
- [server.md](references/server.md): Nginx, PHP-FPM, OPcache, Supervisor, cron, CI/CD
- [version-matrix.md](references/version-matrix.md): runtime support
