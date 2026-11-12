# Queue Playbook

## Diagnose by Symptom

| Symptom | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| Jobs never run | Worker down, wrong queue name, wrong connection | `horizon:status`, process manager, `config:show queue` | Start worker, include the queue |
| Job runs twice | `retry_after` < runtime, non-idempotent retry | Compare runtime and `retry_after` | Timeout Rule, idempotency |
| `MaxAttemptsExceededException` | Timed out and requeued, or released repeatedly | `failed_jobs.exception`, middleware use | Raise tries or `retryUntil()`, fix runtime |
| `TimeoutExceededException` | Job slower than `$timeout` | Horizon runtime metrics | Split into a batch, raise limits on a dedicated queue |
| Job failed without a stack trace | Worker killed: OOM or SIGKILL | `dmesg`, Supervisor logs, container limits | Raise `memory`, process in chunks |
| `ModelNotFoundException` | Deleted before run, or dispatched before commit | Timing, `afterCommit` | `afterCommit()`, or `$deleteWhenMissingModels = true` |
| Old behaviour after deploy | Workers kept old code | Worker start time | Terminate workers on deploy |
| Backlog grows | Throughput below arrival rate | Wait time, runtime, DB load | Add workers, or fix the slow dependency |
| High memory growth | Long-lived state | Worker memory over time | `maxJobs`, `maxTime`, drop static caches |
| `Serialization of 'Closure'` | Closure inside job properties | Constructor arguments | Pass plain data |
| Payload contains stale data | Model snapshot in constructor arrays | Job properties | Re-fetch in `handle()` |
| Redis memory climbing | Large payloads or retention | `redis-cli info memory`, `MEMORY USAGE` | Smaller payloads, tune `trim` |
| Chain stops midway | One job failed | `failed_jobs` | Retry that job; add `->catch()` |

## Inspect Without Disturbing

```bash
php artisan queue:failed
php artisan queue:monitor redis:default,redis:payments --max=100
php artisan tinker --execute="dump(Illuminate\Support\Facades\Queue::size('payments'));"
```

To see a failed job's payload and exception, read `failed_jobs` by `uuid`.

## Retrying Safely

Find the cause and deploy the fix first. Retrying into the same bug only moves jobs back to failed.

```bash
php artisan queue:retry <uuid>
php artisan queue:retry --queue=payments
php artisan queue:retry all
php artisan queue:forget <uuid>
```

Before a mass retry of side-effecting jobs, confirm they are idempotent, and try one first. `queue:flush` deletes every failed job permanently, and `queue:clear` deletes pending jobs. Confirm with the user before running either in production.

## Scheduled Maintenance

```php
use Illuminate\Support\Facades\Schedule;

Schedule::command('queue:prune-failed --hours=168')->daily();
Schedule::command('queue:prune-batches --hours=48 --unfinished=72')->daily();
```

## Batches

Create the table first: `php artisan make:queue-batches-table` (Laravel 11+), or `queue:batches-table` (10), then `migrate`.

```php
<?php

namespace App\Jobs;

use App\Models\Customer;
use Illuminate\Bus\Batchable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;

class ExportCustomerChunk implements ShouldQueue
{
    use Batchable;
    use Queueable;

    /** @param list<int> $customerIds */
    public function __construct(public array $customerIds)
    {
    }

    public function handle(): void
    {
        if ($this->batch()?->cancelled()) {
            return;
        }

        Customer::whereKey($this->customerIds)->each(function (Customer $customer) {
            // Append the row to the export.
        });
    }
}
```

```php
use App\Jobs\ExportCustomerChunk;
use App\Models\Customer;
use Illuminate\Bus\Batch;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\Log;
use Throwable;

$jobs = [];

Customer::select('id')->chunkById(1000, function ($customers) use (&$jobs) {
    $jobs[] = new ExportCustomerChunk($customers->modelKeys());
});

$batch = Bus::batch($jobs)
    ->name('customer-export')
    ->onQueue('reports')
    ->allowFailures()
    ->then(fn (Batch $batch) => Log::info('Export finished', ['id' => $batch->id]))
    ->catch(fn (Batch $batch, Throwable $e) => report($e))
    ->dispatch();
```

Batch callbacks are serialized closures: don't capture `$this`. Without `allowFailures()`, the first failure cancels the batch.

## Rate Limiting External APIs

```php
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Support\Facades\RateLimiter;

RateLimiter::for('mailchimp', fn () => Limit::perMinute(600));
```

```php
use Illuminate\Queue\Middleware\RateLimited;

public function middleware(): array
{
    return [new RateLimited('mailchimp')];
}
```

Use `RateLimitedWithRedis` on Redis for accuracy across workers. Throttled jobs are released and consume attempts, so pair with `retryUntil()`.

## Worker Commands Without Horizon

```bash
php artisan queue:work redis --queue=payments,default --tries=3 --timeout=60 --sleep=3 --max-jobs=1000 --max-time=3600
```

With plain workers, `--queue=a,b` means strict priority. Use `queue:listen` only in development; it boots the framework for each job. Use several Supervisor `numprocs` for concurrency.

## Monitoring Checklist

- [ ] Failed job alert via `Queue::failing()`, your error tracker, or Horizon notifications
- [ ] Wait-time alert per critical queue
- [ ] Oldest pending job age tracked
- [ ] Worker liveness checked by process manager
- [ ] Schedule heartbeat for cron-dependent jobs
