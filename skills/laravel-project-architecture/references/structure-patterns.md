# Structure Patterns

## Three Levels

Move up a level only when the pain table in `SKILL.md` calls for it.

### Level 1: Default Laravel

Fits CRUD apps, small teams and most projects under about 50 models.

```text
app/
├── Http/{Controllers,Requests,Resources,Middleware}
├── Models/
├── Policies/
├── Jobs/
├── Listeners/
└── Providers/
```

### Level 2: Default Laravel plus Use Cases

Fits apps with real business rules and several entry points (web, API, CLI, jobs).

```text
app/
├── Actions/Orders/{PlaceOrder,CancelOrder}.php
├── Data/{OrderData,Money}.php
├── Enums/
├── Models/
├── Models/Builders/OrderBuilder.php
├── Services/Payments/{PaymentGateway,StripeGateway}.php
└── Http/...
```

### Level 3: Domain Folders

Fits large apps with distinct business areas or several teams.

```text
app/
├── Domain/
│   ├── Billing/{Actions,Models,Events,Enums,Policies}/
│   └── Catalog/{Actions,Models,Events}/
├── Http/Api/V1/{Controllers,Requests,Resources}/
└── Providers/
```

Rules that keep Level 3 honest:

- Domains expose Actions and events. They do not reach into each other's models.
- Cross-domain foreign keys are allowed, but cross-domain Eloquent relationships are a deliberate decision.
- The HTTP layer stays outside `Domain` so domains remain usable from jobs and commands.
- Models outside `app/Models` need `Factory::guessFactoryNamesUsing()` or a `newFactory()` override, and policies may need `Gate::guessPolicyNamesUsing()`.

Enforce the boundary with an arch test:

```php
<?php

arch('catalog does not touch billing internals')
    ->expect('App\Domain\Catalog')
    ->not->toUse('App\Domain\Billing\Models');

arch('domains are independent of HTTP')
    ->expect('App\Domain')
    ->not->toUse('Illuminate\Http\Request');
```

## Custom Eloquent Builders

Better than a repository for query reuse, because chaining keeps working.

```php
<?php

namespace App\Models\Builders;

use App\Models\User;
use Illuminate\Database\Eloquent\Builder;

/** @extends Builder<\App\Models\Order> */
class OrderBuilder extends Builder
{
    public function open(): self
    {
        return $this->whereIn('status', ['pending', 'paid']);
    }

    public function forCustomer(User $user): self
    {
        return $this->whereBelongsTo($user);
    }
}
```

```php
public function newEloquentBuilder($query): OrderBuilder
{
    return new OrderBuilder($query);
}
```

## DTOs

```php
<?php

namespace App\Data;

use App\Http\Requests\StoreOrderRequest;

final readonly class OrderData
{
    /** @param list<array{sku: string, quantity: int}> $items */
    public function __construct(
        public array $items,
        public string $shippingMethod,
    ) {
    }

    public static function fromRequest(StoreOrderRequest $request): self
    {
        return new self(
            items: $request->validated('items'),
            shippingMethod: $request->validated('shipping_method'),
        );
    }
}
```

Use a DTO when a payload crosses several layers. For a small, internal, validated array it is optional. Prefer plain classes over adding a data package unless the project already has one.

## Refactoring a God Controller Safely

1. Add feature tests for current behaviour, including error paths. Do this first.
2. Move validation to form requests. Run tests.
3. Move authorization to a policy. Run tests.
4. Extract one use case into an Action, leaving the controller delegating. Run tests.
5. Repeat one use case per commit.
6. Split non-resource methods into their own controllers (`CancelOrderController`).
7. Remove dead code last.

## Splitting a God Model

Keep relations, casts, scopes and small attribute logic on the model.

| Move | To |
| --- | --- |
| Multi-model operations | Actions |
| Complex query chains | Custom builder |
| Reporting | Dedicated query classes |
| Formatting | API resources |
| Lifecycle side effects | Observers or events, used sparingly |

Traits only relocate lines without reducing coupling. Use them for genuinely shared behaviour, not to shrink a file.

## Service or Package Extraction

Before extracting into a separate service, confirm all of these:

- The boundary has been stable for a while inside the monolith.
- Its data can be owned exclusively, without cross-service joins.
- A team can own its on-call and deployment.
- There is a concrete scaling, compliance or isolation requirement.

If any answer is no, a module inside the monolith is the better choice.
