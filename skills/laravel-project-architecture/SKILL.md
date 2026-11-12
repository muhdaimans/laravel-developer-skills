---
name: laravel-project-architecture
description: Use when deciding where Laravel code should live, structuring a new application, or reorganizing a growing codebase, including Actions vs services, repositories, DTOs, domain modules, modular monoliths, events vs direct calls, and fat models or god services.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel Project Architecture

Choose the smallest structure that solves a pain the project actually has. Default Laravel scales further than most teams expect.

**Decide by evidence:** each added layer must name the concrete problem it removes.

## When to Use

- Starting a new app and choosing a structure
- "Where should this logic go?"
- Controllers, models or a service have grown unmanageable
- Considering repositories, DDD, modules or microservices

Line-level style belongs to `laravel-best-practices`. Schema design belongs to `laravel-database-management`.

## Inspect the Project First

```bash
php artisan --version
find app -maxdepth 2 -type d | sort
find app -name '*.php' | xargs wc -l | sort -n | tail -15
php artisan route:list --except-vendor --json | grep -c '"uri"'
git log --since='6 months ago' --name-only --format= -- app | sort | uniq -c | sort -rn | head -15
```

The last command finds hotspots: large files that also change often are the real candidates. A large file nobody touches can wait.

Read `composer.json` for the `autoload` map and any module packages. Note whether `app/Actions`, `app/Services` or `app/Domain` already exist; an in-progress pattern outranks a theoretically better one. See [version-matrix.md](references/version-matrix.md) for skeleton differences.

## Workflow

1. **State the pain** in one sentence. "Checkout logic is duplicated between the API and a console command" is a pain. "It isn't clean" is not.
2. **Match it to the lightest fix:**

   | Pain | Fix |
   | --- | --- |
   | Same logic in controller and command | Extract one Action |
   | Controller over about 150 lines | Split resources, then extract Actions |
   | Same query conditions repeated | Scope or custom Eloquent builder |
   | Model over about 500 lines | Move queries to a builder, behaviour to Actions, keep relations and casts |
   | Service with unrelated public methods | Split by use case |
   | Arrays with undocumented keys crossing layers | `readonly` DTO |
   | Non-essential side effects tangled into the flow | Event with queued listeners |
   | Third-party API called everywhere | One gateway class behind an interface |
   | Two teams colliding in one domain | Domain folders or modules |
   | Different scaling or deployment needs | Consider a separate service only now |

3. **Check dependency direction.** Controllers, commands and jobs call Actions. Actions call models and gateways. Models never call controllers, and domains talk through public Actions or events.
4. **Move incrementally:** one vertical slice in one PR, with tests passing before and after.
5. **Record the decision** with an ADR if it sets a new pattern, using `laravel-documentation`.

## Core Pattern: The Action

One use case, one public method, callable from anywhere.

```php
<?php

namespace App\Actions;

use App\Events\OrderPlaced;
use App\Models\Order;
use App\Models\User;
use App\Services\Payments\PaymentGateway;
use Illuminate\Support\Facades\DB;

class PlaceOrder
{
    public function __construct(
        private PaymentGateway $payments,
    ) {
    }

    public function handle(User $user, array $data): Order
    {
        $order = DB::transaction(function () use ($user, $data) {
            $order = $user->orders()->create(['status' => 'pending', 'total_cents' => 0]);
            $order->items()->createMany($data['items']);
            $order->update(['total_cents' => $order->items()->sum('line_total_cents')]);

            return $order;
        });

        // The network call stays outside the transaction so it cannot hold row locks.
        $this->payments->charge($order);

        OrderPlaced::dispatch($order);

        return $order;
    }
}
```

The transaction boundary lives in the Action, and external calls sit outside it.

## Core Pattern: The Gateway

```php
<?php

namespace App\Services\Payments;

use App\Models\Order;

interface PaymentGateway
{
    public function charge(Order $order): PaymentResult;
}
```

```php
<?php

namespace App\Providers;

use App\Services\Payments\PaymentGateway;
use App\Services\Payments\StripeGateway;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->bind(PaymentGateway::class, StripeGateway::class);
    }
}
```

An interface earns its place at a boundary you do not own, or that has two real implementations. Tests can swap this one for a fake.

## Direct Call or Event?

| Use a direct call when | Use an event when |
| --- | --- |
| The step must succeed for the operation to succeed | The step is a side effect the operation does not depend on |
| The caller needs the result | Listeners may be added without changing the caller |
| You need to read the flow in one place | Several independent reactions exist |

An event with exactly one synchronous listener is an indirect function call: replace it with a direct call.

## Version Notes

- Laravel 11+ auto-discovers listeners in `app/Listeners`, and removed the default `EventServiceProvider`. On 10, check `shouldDiscoverEvents()`.
- Laravel 11+ provider registration lives in `bootstrap/providers.php`; on 10 it is `config/app.php`.
- `Concurrency::run()` and `defer()` exist on 11.x and can replace some ad hoc queue usage for short parallel work.
- Laravel 13 adds `#[Middleware]`, `#[Authorize]` and queue attributes, which reduce some scaffolding but do not change layering.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Repository per model | Re-exports Eloquent, leaks builders anyway | Scopes and custom builders |
| Interface for every class | Double the files, one implementation | Interfaces at external boundaries |
| `Helper` or `Manager` catch-all classes | Becomes the next god object | Name by use case |
| Starting with DDD on a CRUD app | Ceremony without a domain to model | Grow into it |
| Big-bang restructure | Long-lived branch, conflicts | Strangler moves, one slice at a time |
| Actions that call Actions ten levels deep | Hidden flow | Keep orchestration shallow |
| HTTP concerns in Actions | Unusable from jobs and commands | Pass plain values and models, never `Request` |
| API calls inside `DB::transaction` | Locks held during network I/O | Do the I/O after commit |
| Microservices for code organization | Distributed transactions for an internal problem | Modular monolith |
| Mixing two patterns forever | Nobody knows the rule | Finish the migration or abandon it |

See [structure-patterns.md](references/structure-patterns.md) for folder layouts and migration steps.

## Verification

```bash
php artisan test
composer dump-autoload --strict-psr
./vendor/bin/pest --filter=arch
```

- [ ] Stated pain is gone, not relocated
- [ ] No class depends on a higher layer
- [ ] The same behaviour is covered by tests before and after a move
- [ ] Pest arch tests, if used, enforce the new boundary
- [ ] The next developer can tell where new code goes

## Additional Resources

- [structure-patterns.md](references/structure-patterns.md): layouts by project size, module rules, custom builders, refactoring steps
- [version-matrix.md](references/version-matrix.md): skeleton and provider differences
