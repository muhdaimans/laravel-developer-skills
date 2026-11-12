# Laravel Horizon

Horizon requires Redis queues, and is **not compatible with Redis Cluster**. It needs the `pcntl` and `posix` PHP extensions.

## Install

```bash
composer require laravel/horizon
php artisan horizon:install
```

Set `QUEUE_CONNECTION=redis`. The Redis connection name `horizon` is reserved, so do not assign it in `config/database.php`, or as `use` in `config/horizon.php`.

## Supervisor Design

Use separate supervisors when workloads differ in priority, runtime, or resource use.

```php
<?php

return [
    'defaults' => [
        'supervisor-default' => [
            'connection' => 'redis',
            'balance' => 'auto',
            'autoScalingStrategy' => 'time',
            'memory' => 128,
            'tries' => 3,
            'timeout' => 60,
            'maxTime' => 3600,
            'maxJobs' => 1000,
        ],
    ],

    'environments' => [
        'production' => [
            'supervisor-default' => [
                'queue' => ['default', 'notifications'],
                'minProcesses' => 2,
                'maxProcesses' => 20,
                'balanceMaxShift' => 2,
                'balanceCooldown' => 3,
            ],
            'supervisor-payments' => [
                'queue' => ['payments'],
                'minProcesses' => 2,
                'maxProcesses' => 6,
                'timeout' => 45,
            ],
            'supervisor-reports' => [
                'connection' => 'redis-long',
                'queue' => ['reports'],
                'balance' => 'simple',
                'processes' => 2,
                'timeout' => 900,
                'memory' => 512,
            ],
        ],

        'local' => [
            'supervisor-default' => [
                'queue' => ['default', 'notifications', 'payments', 'reports'],
                'maxProcesses' => 3,
            ],
        ],
    ],
];
```

`redis-long` is a second connection in `config/queue.php` with `retry_after` above 900. Every environment you run must appear here, or use a `*` wildcard environment.

Size `maxProcesses` from available memory: `(RAM for workers) / (typical worker RSS)`. Also keep total processes below the database connection limit.

## Balancing

| `balance` | Behaviour | Use for |
| --- | --- | --- |
| `auto` (default) | Moves workers by load. `autoScalingStrategy`: `time`, `size` or `log` | Variable traffic |
| `simple` | Fixed `processes` split evenly across queues | Predictable load, expensive jobs |
| `false` | Queues processed strictly in listed order, total scales | Strict priority |

With `auto`, queue order does **not** set priority. For priority, use `balance => false`, or separate supervisors. Set `minProcesses` per queue so an idle queue reacts quickly.

## Timeouts

- Horizon `timeout` must be greater than any job-level `$timeout`. During `auto` scale-down, Horizon treats in-progress workers as hanging and kills them after this timeout.
- Horizon `timeout` must be a few seconds lower than the connection's `retry_after`.
- If you don't set `tries`, Horizon defaults to one attempt unless the job defines `$tries`. The job value wins.

## Dashboard Security

```php
use App\Models\User;
use Illuminate\Support\Facades\Gate;

Gate::define('viewHorizon', function (User $user) {
    return $user->hasRole('operations');
});
```

Define this in `HorizonServiceProvider::gate()`. Non-local environments are denied until the gate passes. The dashboard shows job payloads, so hide sensitive values in `config/horizon.php`, or mark properties on the job as encrypted with `ShouldBeEncrypted`.

## Metrics, Pruning and Tags

```php
use Illuminate\Support\Facades\Schedule;

Schedule::command('horizon:snapshot')->everyFiveMinutes();
```

Without this, the metrics page stays empty. Retention is controlled by `trim` and `metrics.trim_snapshots`, which count snapshots rather than age.

Tag jobs for search. Models are tagged automatically, for example `App\Models\Invoice:42`. Custom tags:

```php
public function tags(): array
{
    return ['billing', 'invoice:'.$this->invoice->id];
}
```

## Notifications

```php
use Laravel\Horizon\Horizon;

Horizon::routeSlackNotificationsTo(config('services.slack.ops_webhook'), '#ops');
Horizon::routeMailNotificationsTo('ops@example.com');
```

Thresholds in `config/horizon.php`:

```php
<?php

return [
    'waits' => [
        'redis:payments' => 15,
        'redis:default' => 60,
        'redis-long:reports' => 600,
    ],
];
```

## Process Supervision

`/etc/supervisor/conf.d/horizon.conf`:

```ini
[program:horizon]
process_name=%(program_name)s
command=php /var/www/app/current/artisan horizon
autostart=true
autorestart=true
user=www-data
redirect_stderr=true
stdout_logfile=/var/www/app/shared/storage/logs/horizon.log
stopwaitsecs=3600
```

`stopwaitsecs` must exceed your longest job. In Docker, set the container stop grace period the same way, and run `php artisan horizon` as the foreground process.

Deploy:

```bash
php artisan horizon:terminate
```

Horizon finishes running jobs and exits, then the process monitor restarts it on new code.

## Commands

```bash
php artisan horizon:status
php artisan horizon:supervisor-status supervisor-payments
php artisan horizon:pause
php artisan horizon:continue
php artisan horizon:pause-supervisor supervisor-reports
php artisan horizon:forget <id>
php artisan horizon:clear --queue=reports
```

`horizon:clear` deletes queued jobs. Confirm with the user before running it in production.

## Maintenance Mode

Workers stop processing during `php artisan down` unless the supervisor sets `'force' => true`.
