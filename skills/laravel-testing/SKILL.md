---
name: laravel-testing
description: Use when writing, fixing or speeding up Laravel tests with Pest or PHPUnit, including feature and unit tests, fakes, factories, database traits, flaky tests, coverage gaps, slow suites, and CI test setup.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer, Pest or PHPUnit. Designed for Claude Code.
---

# Laravel Testing

Test behaviour through the framework's real entry points, and fake only what crosses the application boundary.

## When to Use

- Adding tests for new or existing code
- Choosing what to test, or which fake to use
- Flaky, order-dependent or slow tests
- Setting up test databases and CI

Choosing what to assert for a query-count regression belongs to `laravel-eloquent-optimization`.

## Inspect the Project First

```bash
php artisan --version
composer show --locked | grep -E 'pestphp/pest|phpunit/phpunit|paratest|mockery'
cat phpunit.xml
ls tests tests/Feature tests/Unit
ls tests/Pest.php 2>/dev/null
php artisan test --compact 2>/dev/null | tail -5
```

**Write tests in the project's framework.** Pest if `tests/Pest.php` exists and tests use `it()`/`test()`; otherwise PHPUnit. Do not convert existing tests. Read a neighbouring test for setup style.

**Check the test database before running anything.** `RefreshDatabase`, `DatabaseMigrations` and `DatabaseTruncation` wipe the connection the tests use:

```bash
grep -E 'DB_(CONNECTION|DATABASE)' .env phpunit.xml .env.testing 2>/dev/null
```

Run the suite only if `phpunit.xml` or `.env.testing` has an active, uncommented `DB_DATABASE` that differs from `.env`, such as `:memory:` or `app_testing`. If not, stop and tell the user: running the tests would clear their development data. See [version-matrix.md](references/version-matrix.md) for version pairings.

## Workflow

1. **Pick the test level:**

   | Code | Level | Example |
   | --- | --- | --- |
   | HTTP endpoint | Feature | `postJson()` plus DB and status assertions |
   | Artisan command | Feature | `artisan()->assertSuccessful()` |
   | Job handler, listener, Action | Feature with DB | Call `handle()` directly |
   | Pure calculation, value object | Unit | No framework |
   | Enum transition rules | Unit, with datasets | Table of cases |
   | Layer rules | Arch (Pest) | `arch()->expect(...)` |
   | Critical user journey | Browser | Dusk, or Pest 4 browser |

2. **List behaviours,** including failure paths: success, validation, unauthenticated, unauthorized, not found, conflict.
3. **Arrange with factories,** in named states rather than long attribute lists.
4. **Act once,** through the public entry point.
5. **Assert outcomes:** response, database state, dispatched effects. Avoid asserting internals.
6. **Watch it fail** by breaking the code briefly. A test that can't fail proves nothing.
7. **Run only the affected tests,** then the full suite.

## Core Pattern: A Feature Test

Pest:

```php
<?php

use App\Jobs\ChargeInvoice;
use App\Models\Invoice;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Queue;

uses(RefreshDatabase::class);

beforeEach(function () {
    Queue::fake();
});

it('queues a charge when the owner pays an invoice', function () {
    $invoice = Invoice::factory()->unpaid()->create();

    $this->actingAs($invoice->user)
        ->postJson("/api/v1/invoices/{$invoice->id}/pay")
        ->assertAccepted();

    Queue::assertPushed(ChargeInvoice::class, fn ($job) => $job->invoice->is($invoice));
});

it('refuses an invoice owned by someone else', function () {
    $invoice = Invoice::factory()->unpaid()->create();

    $this->actingAs(User::factory()->create())
        ->postJson("/api/v1/invoices/{$invoice->id}/pay")
        ->assertForbidden();

    Queue::assertNothingPushed();
});

it('rejects an already paid invoice', function () {
    $invoice = Invoice::factory()->paid()->create();

    $this->actingAs($invoice->user)
        ->postJson("/api/v1/invoices/{$invoice->id}/pay")
        ->assertConflict();
});
```

PHPUnit:

```php
<?php

namespace Tests\Feature;

use App\Models\Invoice;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class PayInvoiceTest extends TestCase
{
    use RefreshDatabase;

    public function test_already_paid_invoice_is_rejected(): void
    {
        $invoice = Invoice::factory()->paid()->create();

        $this->actingAs($invoice->user)
            ->postJson("/api/v1/invoices/{$invoice->id}/pay")
            ->assertConflict();
    }
}
```

## Core Pattern: Test the Handler Too

`Queue::fake()` means the job never ran. Cover the handler separately:

```php
it('charges an invoice only once', function () {
    $gateway = Mockery::spy(PaymentGateway::class);
    $gateway->allows('charge')->andReturn(new Charge('ch_1'));
    $this->app->instance(PaymentGateway::class, $gateway);

    $invoice = Invoice::factory()->unpaid()->create();

    dispatch_sync(new ChargeInvoice($invoice));
    dispatch_sync(new ChargeInvoice($invoice));

    $gateway->shouldHaveReceived('charge')->once();
    expect($invoice->fresh()->paid_at)->not->toBeNull();
});
```

Which boundary to fake:

| Boundary | Tool |
| --- | --- |
| Outbound HTTP | `Http::fake()` with `Http::preventStrayRequests()` |
| Queue | `Queue::fake()`, or `Bus::fake()` for chains and batches |
| Events | `Event::fake([OrderShipped::class])`, naming events so others still run |
| Mail, notifications | `Mail::fake()`, `Notification::fake()` |
| Files | `Storage::fake('s3')` |
| Time | `$this->travelTo()`, `$this->freezeTime()` |
| Reported exceptions | `Exceptions::fake()` on Laravel 11+ |
| Your own code | Prefer the real implementation |

## Version Notes

- Laravel 13 uses PHPUnit 12 and Pest 4. Pest 4 needs PHP 8.3+. PHPUnit 12 removed doc-comment metadata, so use attributes such as `#[Test]` and `#[DataProvider]`.
- Pest 4 browser tests need `pestphp/pest-plugin-browser` and Playwright. It's a new dependency, so ask first.
- `Exceptions::fake()` needs Laravel 11.
- Laravel 13 resets custom `Str` factories between tests, so set them per test.
- `$this->withoutMiddleware(PreventRequestForgery::class)` replaces `VerifyCsrfToken::class` on 13. Laravel disables CSRF checks in tests by default, so this is rarely needed.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Running tests on the `.env` database | `RefreshDatabase` runs `migrate:fresh` on it | Separate test database, checked first |
| Testing only the happy path | Auth and validation bugs ship | Cover the failure matrix |
| `get()` for a JSON API | Exceptions render as HTML or redirects | `getJson()` |
| `withoutExceptionHandling()` left in | Masks real status codes | Debug only |
| Asserting mock calls instead of outcomes | Breaks on refactor, proves little | Assert DB and response |
| Mocking Eloquent | Tests the mock | Use factories and the test DB |
| Unnamed `Event::fake()` | Disables model observers and listeners | Pass specific events |
| SQLite-only testing | Misses engine differences | CI on production engine |
| `sleep()` | Slow and flaky | `travel()`, `freezeTime()` |
| Hard-coded IDs | Order-dependent failures | Use created models |
| Real network calls | Flaky, can hit production | `Http::preventStrayRequests()` |
| Weak assertion, such as `assertOk()` alone | A wrong body passes | Assert content and effects |
| Shared state in static properties | Order-dependent failures | Reset in `setUp`/`beforeEach` |

See [patterns.md](references/patterns.md) for database traits, flakiness diagnosis, speed-ups and CI.

## Verification

```bash
php artisan test --filter=PayInvoice
php artisan test --parallel
php artisan test --coverage --min=80
./vendor/bin/pest --mutate
```

Coverage needs Xdebug or PCOV. `--mutate` is Pest 3+, and is run on chosen code, not the whole app.

- [ ] Each new test failed once, for the right reason
- [ ] Full suite passes, and still passes with `--parallel`
- [ ] Failure paths are covered
- [ ] No stray HTTP or real services
- [ ] The suite ran on the test database, never the development one

## Additional Resources

- [patterns.md](references/patterns.md): factories, database traits, datasets, arch tests, flaky test diagnosis, speed, CI workflow
- [version-matrix.md](references/version-matrix.md): PHPUnit and Pest pairings
