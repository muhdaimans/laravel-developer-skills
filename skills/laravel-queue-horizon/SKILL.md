---
name: laravel-queue-horizon
description: Use when Laravel or Horizon jobs run twice, send duplicates, fail, time out, get stuck or back up, or when writing jobs, listeners or batches, or configuring Redis queues and Laravel Horizon, including MaxAttemptsExceededException and workers not picking up new code.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer, Redis for Horizon. Designed for Claude Code.
---

# Laravel Queues and Horizon

Assume every job can run twice, run late, and fail halfway. Design for that first; configure workers second.

## When to Use

- Creating jobs, queued listeners, batches or chains
- Tuning `retry_after`, timeouts, retries or concurrency
- Setting up Horizon
- Jobs stuck, duplicated, failing or backing up

Process supervision during releases belongs to `laravel-deployment`. Testing jobs belongs to `laravel-testing`.

## Inspect the Project First

```bash
php artisan --version
php artisan config:show queue
composer show --locked | grep -E 'horizon|predis|phpredis'
php -m | grep -E 'redis|pcntl|posix'
ls app/Jobs config/horizon.php 2>/dev/null
php artisan queue:failed
php artisan horizon:status 2>/dev/null
```

Also find how workers run (Supervisor, systemd, container) and how long the slowest job takes. Note that `config/horizon.php` overrides worker options, and `config/queue.php` still owns `retry_after`. See [version-matrix.md](references/version-matrix.md).

## Workflow

1. **Decide if it belongs on a queue:** slow, retryable, or failure-tolerant work. Use `defer()` for trivial post-response work on Laravel 11+ if losing it is acceptable.
2. **Design for idempotency:** a second run must not double-charge or double-send. See the pattern below.
3. **Pass identifiers or small models,** not large payloads or closures.
4. **Set failure policy on each job:** attempts, backoff, timeout and `failed()`.
5. **Align the timeouts** using the rule below.
6. **Separate workloads by queue:** fast user-facing work must not wait behind slow reports.
7. **Dispatch after commit** whenever a job reads rows you just wrote.
8. **Add monitoring:** failed job alerts, wait-time thresholds, `queue:monitor`.
9. **Test** dispatch, handler behaviour and the failure path.

### The Timeout Rule

```text
job $timeout  <  worker or Horizon timeout  <  retry_after  <  Supervisor stopwaitsecs
```

| Setting | Location | Meaning |
| --- | --- | --- |
| `$timeout` | Job class | Kill this job after N seconds |
| `timeout` | `queue:work --timeout` or Horizon supervisor | Worker-level limit |
| `retry_after` | `config/queue.php` | Requeue a job with no result after N seconds |
| `stopwaitsecs` | Supervisor program | Grace period before SIGKILL |

If `retry_after` is shorter than the runtime, **a second worker starts the same job while the first is still running**. This is the most common cause of duplicated work. The default `retry_after` is 90 seconds.

A job's `$timeout` needs the `pcntl` extension. If a slow job needs far more time than other work, give it its own connection with a larger `retry_after`, and its own Horizon supervisor.

## Core Pattern: A Production Job

```php
<?php

namespace App\Jobs;

use App\Models\Invoice;
use App\Services\Payments\PaymentGateway;
use App\Services\Payments\TemporaryGatewayException;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Queue\Middleware\ThrottlesExceptions;
use Illuminate\Queue\Middleware\WithoutOverlapping;
use Illuminate\Support\Facades\Log;
use Throwable;

class ChargeInvoice implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $tries = 5;

    public int $maxExceptions = 3;

    public int $timeout = 30;

    public int $uniqueFor = 3600;

    public function __construct(public Invoice $invoice)
    {
        $this->onQueue('payments');
    }

    public function uniqueId(): string
    {
        return (string) $this->invoice->id;
    }

    /** @return list<int> */
    public function backoff(): array
    {
        return [10, 60, 300];
    }

    /** @return list<object> */
    public function middleware(): array
    {
        return [
            (new WithoutOverlapping("invoice:{$this->invoice->id}"))->releaseAfter(30)->expireAfter(120),
            (new ThrottlesExceptions(10, 300))->by('gateway')->when(
                fn (Throwable $e) => $e instanceof TemporaryGatewayException
            ),
        ];
    }

    public function handle(PaymentGateway $gateway): void
    {
        if ($this->invoice->fresh()->paid_at !== null) {
            return; // Already done: a retry or duplicate is a no-op.
        }

        $charge = $gateway->charge(
            $this->invoice,
            idempotencyKey: "invoice-{$this->invoice->id}",
        );

        $this->invoice->update(['paid_at' => now(), 'charge_id' => $charge->id]);
    }

    public function failed(?Throwable $exception): void
    {
        Log::error('Invoice charge failed', [
            'invoice_id' => $this->invoice->id,
            'error' => $exception?->getMessage(),
        ]);
    }
}
```

Idempotency here comes from two layers: a local state check, and an idempotency key passed to the provider. `ShouldBeUnique` only prevents duplicate *queueing*, and is not a substitute. On Laravel 10, use the four traditional traits (`Dispatchable`, `InteractsWithQueue`, `Queueable`, `SerializesModels`) in place of the Foundation `Queueable` trait.

`WithoutOverlapping` and `RateLimited` releases consume attempts. Use `retryUntil()` rather than `$tries` when a job may be released often:

```php
use DateTime;

public function retryUntil(): DateTime
{
    return now()->addHour();
}
```

## Dispatching

```php
use App\Jobs\ChargeInvoice;
use App\Jobs\SendReceipt;
use Illuminate\Support\Facades\Bus;

ChargeInvoice::dispatch($invoice)->afterCommit();

Bus::chain([
    new ChargeInvoice($invoice),
    new SendReceipt($invoice),
])->dispatch();
```

Set `'after_commit' => true` on the connection in `config/queue.php` to make this the default.

## Version Notes

- Laravel 13 can declare limits with attributes, and route jobs centrally:

  ```php
  use App\Jobs\ChargeInvoice;
  use Illuminate\Support\Facades\Queue;

  Queue::route(ChargeInvoice::class, connection: 'redis', queue: 'payments');
  ```

  `#[Tries(5)]`, `#[Timeout(30)]` and `#[Backoff(10, 60, 300)]` live in `Illuminate\Queue\Attributes`. Confirm the constructor against the vendor source. Keep properties if the project also targets Laravel 12.

- Laravel 13 renamed `JobAttempted->exceptionOccurred` to `->exception`, and `QueueBusy->connection` to `->connectionName`.
- Since Laravel 11, `ThrottlesExceptions` takes seconds. On 10, the second argument is minutes.
- Since Laravel 11 the default queue connection is `database`. Check `QUEUE_CONNECTION`.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| `retry_after` below job runtime | Job runs in parallel with itself | Apply the Timeout Rule |
| Dispatch inside a transaction | Worker sees no row, model missing | `afterCommit()` |
| Workers not restarted on deploy | Old code keeps running | `queue:restart` or `horizon:terminate` |
| `queue:restart` with `array` cache | Signal is never seen | Use a shared cache |
| Serializing a huge relation | Oversized payload, stale data | `withoutRelations()`, or IDs |
| Closures on queues | Serialization fragility | Job classes |
| `sleep()` for retries | Occupies a worker | `release($seconds)` or backoff |
| `$tries = 0` without limits | Infinite retry | `retryUntil()` or `maxExceptions` |
| `Queue::fake()` only | Handler never tested | Also test `handle()` directly |
| One queue for everything | Reports starve password resets | Named queues per latency need |
| Reading `auth()` in a job | No authenticated user | Pass the user |
| `failed_jobs` never pruned | Table grows forever | Schedule `queue:prune-failed` |

## Verification

```bash
php artisan queue:work --once --queue=payments -v
php artisan queue:failed
php artisan horizon:status
php artisan test --filter=ChargeInvoice
```

- [ ] Run the job twice in a test: the side effect happens once
- [ ] Throw inside `handle()`: retry timing and `failed()` behave as intended
- [ ] Timeout Rule holds in real configuration, checked with `config:show queue`
- [ ] Workers restart in the deployment script
- [ ] Failed job alerting exists

## Additional Resources

- [horizon.md](references/horizon.md): install, supervisors, balancing, dashboard security, notifications, Supervisor config
- [queue-playbook.md](references/queue-playbook.md): symptom-based diagnosis, batches, safe retries, monitoring
- [version-matrix.md](references/version-matrix.md): version gates
