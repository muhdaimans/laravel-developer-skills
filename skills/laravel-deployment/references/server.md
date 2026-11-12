# Server Deployment

Examples use Ubuntu, `/var/www/app/current` and PHP 8.4. Adjust to the project.

## Directory Layout

```text
/var/www/app/
├── current -> releases/20261030120000
├── releases/
└── shared/
    ├── .env
    └── storage/
```

Ownership: deploy user owns code, the web group can read it. `storage` and `bootstrap/cache` are writable by PHP.

```bash
sudo chown -R deploy:www-data /var/www/app
sudo find /var/www/app/shared/storage -type d -exec chmod 2775 {} +
sudo find /var/www/app/shared/storage -type f -exec chmod 664 {} +
```

## Nginx

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name example.com;
    root /var/www/app/current/public;
    index index.php;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    client_max_body_size 25m;
    charset utf-8;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location = /favicon.ico { access_log off; log_not_found off; }
    location = /robots.txt  { access_log off; log_not_found off; }

    location /build/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    error_page 404 /index.php;

    location ~ ^/index\.php(/|$) {
        fastcgi_pass unix:/run/php/php8.4-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
        include fastcgi_params;
        fastcgi_hide_header X-Powered-By;
        fastcgi_read_timeout 60s;
    }

    location ~ /\.(?!well-known).* {
        deny all;
    }
}
```

Key points: `root` is `public/`, only `index.php` executes, and `$realpath_root` resolves the release symlink, so a new release gets new OPcache entries.

## PHP-FPM Pool

```ini
pm = dynamic
pm.max_children = 20
pm.start_servers = 5
pm.min_spare_servers = 5
pm.max_spare_servers = 10
pm.max_requests = 1000
request_terminate_timeout = 65
```

`pm.max_children` is approximately `(RAM available to PHP) / (average worker RSS)`. Watch it with `ps -ylC php-fpm8.4 --sort=rss`. Keep `request_terminate_timeout` at least as long as the Nginx read timeout.

## OPcache and Production php.ini

```ini
opcache.enable=1
opcache.memory_consumption=256
opcache.interned_strings_buffer=16
opcache.max_accelerated_files=20000
opcache.validate_timestamps=0
expose_php=Off
display_errors=Off
log_errors=On
```

With `validate_timestamps=0`, PHP-FPM must be reloaded in every deploy.

## Worker Supervision

Horizon's Supervisor config is in `laravel-queue-horizon`. Plain workers:

```ini
[program:app-worker]
process_name=%(program_name)s_%(process_num)02d
command=php /var/www/app/current/artisan queue:work redis --sleep=3 --tries=3 --max-time=3600
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
user=www-data
numprocs=4
redirect_stderr=true
stdout_logfile=/var/www/app/shared/storage/logs/worker.log
stopwaitsecs=3600
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```

## Scheduler

Crontab for the web user:

```cron
* * * * * cd /var/www/app/current && php artisan schedule:run >> /dev/null 2>&1
```

Log task output when failures matter:

```php
use Illuminate\Support\Facades\Schedule;

Schedule::command('reports:daily')
    ->dailyAt('02:00')
    ->withoutOverlapping()
    ->onOneServer()
    ->appendOutputTo(storage_path('logs/reports.log'))
    ->onFailure(fn () => logger()->error('Daily report failed'));
```

On the legacy layout, these lines go in `app/Console/Kernel.php`.

## Trusted Proxies

Behind a load balancer, HTTPS and client IPs are wrong until configured:

```php
<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->trustProxies(
            at: ['10.0.0.0/8'],
            headers: Request::HEADER_X_FORWARDED_FOR
                | Request::HEADER_X_FORWARDED_HOST
                | Request::HEADER_X_FORWARDED_PORT
                | Request::HEADER_X_FORWARDED_PROTO,
        );
    })
    ->create();
```

Use `at: '*'` only when the app can't be reached except through the proxy.

## Maintenance Mode

Atomic releases rarely need it. For a risky migration:

```bash
php artisan down --retry=60 --secret="$BYPASS_TOKEN"
php artisan up
```

With several servers, set `APP_MAINTENANCE_DRIVER=cache` and a shared store, so all servers agree.

## CI/CD Pipeline

```yaml
name: deploy
on:
  push:
    tags: ['v*']

jobs:
  test:
    uses: ./.github/workflows/tests.yml

  deploy:
    needs: test
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Release
        uses: appleboy/ssh-action@v1
        env:
          RELEASE_REF: ${{ github.ref_name }}
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: deploy
          key: ${{ secrets.DEPLOY_KEY }}
          envs: RELEASE_REF
          script: /var/www/app/deploy.sh "$RELEASE_REF"
```

Use a protected environment for approval. Give the deploy key only this server, and let the workflow call `tests.yml` with `workflow_call`. Pass refs through `env` as shown: a tag name interpolated directly into a script can inject shell commands.

## First Deploy

```bash
php artisan key:generate --show
php artisan storage:link
php artisan migrate --force --isolated
php artisan optimize
```

Store the generated `APP_KEY` in `shared/.env`, and back it up with your secrets. Losing it makes encrypted data unreadable.

## Backups

Backups count only if restores are tested. Automate database dumps off-site, cover uploaded files, and rehearse a restore on a schedule. Dumps use your database tools, or `spatie/laravel-backup` if the project already has it.
