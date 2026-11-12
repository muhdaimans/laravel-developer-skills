---
name: laravel-best-practices
description: Use when writing or refactoring everyday Laravel code such as controllers, form requests, models, config, helpers and service providers, or when asked what the idiomatic Laravel way is, including naming, validation placement, fat controllers, env() usage and PSR-12 or Pint style.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel Best Practices

Write code that looks like the code already in the project, using framework features before custom abstractions.

**Rule of precedence:** project convention > this skill > personal preference. An established pattern is changed only when the user asks.

## When to Use

- Adding or changing a controller, form request, model, enum, helper or provider
- "What's the Laravel way to do X?"
- Cleaning up code that works but fights the framework

Hand off these topics:

| Topic | Skill |
| --- | --- |
| Folder structure, Actions vs services, modules | `laravel-project-architecture` |
| Slow queries, N+1 | `laravel-eloquent-optimization` |
| Reviewing a diff or PR | `laravel-code-review` |
| Writing tests | `laravel-testing` |

## Inspect the Project First

```bash
php artisan --version
composer show --locked --direct
ls app app/Http/Controllers app/Models
cat pint.json 2>/dev/null
ls phpstan.neon* 2>/dev/null
```

Then read two or three existing files of the kind you are about to write. Record:

1. Controllers: resourceful, invokable, or action classes?
2. Validation: form requests or inline?
3. Authorization: policies, `Gate::authorize()`, or `$this->authorize()`?
4. Style: `declare(strict_types=1)`, `final`, return types?

See [version-matrix.md](references/version-matrix.md) for version gates and how to tell old from new skeletons.

## Workflow

1. **Generate with Artisan** (`make:model -mfc`, `make:request`, `make:policy`, `make:resource`) so namespaces and stubs match the project.
2. **Put each concern where Laravel expects it:**

   | Concern | Location |
   | --- | --- |
   | Input validation | Form request `rules()` |
   | "May this user do this?" | Policy |
   | Reusable query constraints | Eloquent scope |
   | Multi-step business operation | Action or service, as the project does it |
   | Side effects after an event | Queued listener or job |
   | Response shape | API resource or view |
   | Environment values | `config/*.php`, read with `config()` |

3. **Keep controllers to four jobs:** authorize, validate, delegate, respond.
4. **Type everything public:** parameters, return types, enums instead of string constants.
5. **Format and analyze:** run Pint, then Larastan or PHPStan if the project already has them.
6. **Add or update a test** with the change, using `laravel-testing`.

## Core Pattern: A Thin Controller

Before, with validation, authorization, business logic and side effects in one method:

```php
public function store(Request $request)
{
    $data = $request->validate(['total' => 'required|numeric']);
    $order = Order::create($data + ['user_id' => auth()->id()]);
    Mail::to($request->user())->send(new OrderPlaced($order));

    return response()->json($order, 201);
}
```

After, where each piece can be tested and reused:

```php
<?php

namespace App\Http\Controllers;

use App\Actions\PlaceOrder;
use App\Http\Requests\StoreOrderRequest;
use App\Http\Resources\OrderResource;
use App\Models\Order;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Gate;

class OrderController extends Controller
{
    public function store(StoreOrderRequest $request, PlaceOrder $placeOrder): JsonResponse
    {
        Gate::authorize('create', Order::class);

        $order = $placeOrder->handle($request->user(), $request->validated());

        return OrderResource::make($order)->response()->setStatusCode(201);
    }
}
```

```php
<?php

namespace App\Http\Requests;

use App\Enums\ShippingMethod;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class StoreOrderRequest extends FormRequest
{
    public function rules(): array
    {
        return [
            'items' => ['required', 'array', 'min:1'],
            'items.*.sku' => ['required', 'string', Rule::exists('products', 'sku')],
            'items.*.quantity' => ['required', 'integer', 'min:1', 'max:100'],
            'shipping_method' => ['required', Rule::enum(ShippingMethod::class)],
        ];
    }
}
```

## Model Conventions

```php
<?php

namespace App\Models;

use App\Enums\OrderStatus;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Order extends Model
{
    use HasFactory;

    protected $fillable = ['user_id', 'status', 'total_cents'];

    protected function casts(): array // Laravel 11+. Use the $casts property on 10.
    {
        return [
            'status' => OrderStatus::class,
            'placed_at' => 'immutable_datetime',
        ];
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function scopeOpen(Builder $query): void
    {
        $query->whereIn('status', OrderStatus::openStatuses());
    }
}
```

Enable strict mode outside production in `AppServiceProvider::boot()`:

```php
use Illuminate\Database\Eloquent\Model;

Model::shouldBeStrict(! app()->isProduction());
```

This surfaces lazy loading, silently discarded attributes, and access to attributes that were not selected. On an existing project it may break pages, so enable it in its own change.

## Version Notes

- `casts()` as a method needs Laravel 11; `$casts` works everywhere.
- On Laravel 11+ skeletons the base `Controller` has no traits, so `$this->authorize()` fails. Use `Gate::authorize()`, or add `AuthorizesRequests` where the project already relies on it.
- `readonly` DTOs need PHP 8.2. Typed constants need 8.3. Check the `php` constraint in `composer.json`, not the local runtime.
- Laravel 13 offers attributes such as `#[Fillable]` and `#[Middleware]`. They are optional: match the surrounding code.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| `env('X')` outside `config/` | Returns `null` after `config:cache` | Add a config key, read with `config()` |
| `$request->all()` into `create()` | Mass assignment of unvalidated keys | `$request->validated()` |
| `$guarded = []` | One forgotten filter exposes every column | Explicit `$fillable` |
| Logic in Blade or resources | Untestable, causes N+1 | Compute earlier, eager load |
| Money as float | Rounding errors | Integer cents, or `decimal` with a cast |
| `Model::all()` for display | Unbounded memory use | Paginate or scope |
| Catching `\Exception` to return `false` | Hides failures from reporting | Let it propagate, or `report($e)` |
| Facade-free "purity" rewrites | Churn with no benefit | Follow the project's choice |
| A repository wrapping every model | Duplicates Eloquent's API | Add one only for a real second implementation |
| Adding a package for one helper | Permanent dependency cost | Check `Str`, `Arr`, `Collection` first |

See [conventions.md](references/conventions.md) for the naming table and framework-first replacements.

## Verification

```bash
./vendor/bin/pint --dirty
php artisan route:list --except-vendor
php artisan test --filter=Order
./vendor/bin/phpstan analyse --memory-limit=1G
```

Run `phpstan` only if configured. Finally confirm the diff touches no unrelated files.

## Additional Resources

- [conventions.md](references/conventions.md): naming, framework-first replacements, modern PHP usage
- [version-matrix.md](references/version-matrix.md): support dates, skeleton differences, feature gates
