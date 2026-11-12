---
name: laravel-best-practices
description: Use when writing or refactoring everyday Laravel code such as controllers, form requests, service classes, models, enums, Blade components, config, helpers and service providers, or when asked what the idiomatic Laravel way is, including naming, validation placement, fat controllers, duplicated logic or markup, fixed option lists such as gender or status, env() usage and PSR-12 or Pint style.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel Best Practices

Write code that looks like the code already in the project, using framework features before custom abstractions.

**Rule of precedence:** House Rules > project convention > the rest of this skill > personal preference. An established pattern is changed only when the user asks.

## House Rules

These five rules apply to every piece of new code. Full examples are in [house-rules.md](references/house-rules.md); read it before writing a service, form request, enum or Blade component.

| # | Rule | Trigger | What to write |
| --- | --- | --- | --- |
| 1 | Repeated logic goes in a service class | The same task or method is needed a second time, in any controller, command, job or Livewire component | `app/Services/{Domain}Service.php`, injected where it is used |
| 2 | Every form has a form request | Any `store` or `update` that accepts user input | `php artisan make:request Store{Model}Request`, then `$request->validated()` |
| 3 | Never clear the database | Any command or code that drops, truncates, resets or reseeds existing data | A new forward migration or a targeted update. See below |
| 4 | Fixed option lists are enums, not tables | A column with a small set of values known at code time: NRIC type, gender, religion, marital status, status | Backed enum in `app/Enums`, `string` column, enum cast, `Rule::enum()` |
| 5 | Repeated markup is a Blade component | The same block of `<div>`, button, table, form field, card, modal or alert markup appears a second time | `resources/views/components/*.blade.php`, used as `<x-...>` |

Before creating any of these, look for one that already exists (`app/Services`, `app/Enums`, `resources/views/components`) and extend it. Existing code that breaks a rule is left alone unless the task touches it or the user asks.

### Rule 3: Database Safety

Development databases hold data the user needs. Do not run these, on any environment, unless the user asks for that exact command in the current conversation:

| Forbidden | Why |
| --- | --- |
| `migrate:fresh`, `migrate:refresh`, `migrate:reset`, `db:wipe` | Drops every table |
| `migrate:rollback` without `--step=1` | Rolls back a whole batch, dropping tables and columns with their data |
| `truncate()`, `DROP TABLE`, `delete()` without a `where` | Removes rows that cannot be restored |
| `db:seed` with a seeder that truncates or is not idempotent | Wipes or duplicates rows |
| `php artisan test` when tests use `RefreshDatabase` on the `.env` database | The trait runs `migrate:fresh` on whatever connection the tests use |

Do this instead:

- Change schema with a new migration and `php artisan migrate`. Never edit an old migration and rebuild.
- Roll back only a migration created in this session, with `migrate:rollback --step=1`, and only if the table or column it drops holds no data yet.
- Write seeders with `updateOrCreate()` or `firstOrCreate()` so running them twice changes nothing.
- Before running tests, confirm `phpunit.xml` or `.env.testing` sets a separate database (`:memory:` or a `*_testing` name). If it does not, stop and tell the user.
- If a reset looks like the only fix, stop and ask. State what would be lost and offer a backup first.

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
ls app/Services app/Actions app/Enums app/Http/Requests resources/views/components 2>/dev/null
grep -E 'DB_(CONNECTION|DATABASE)' .env phpunit.xml .env.testing 2>/dev/null
cat pint.json 2>/dev/null
ls phpstan.neon* 2>/dev/null
```

Then read two or three existing files of the kind you are about to write. Record:

1. Controllers: resourceful, invokable, or action classes?
2. Validation: form requests or inline?
3. Authorization: policies, `Gate::authorize()`, or `$this->authorize()`?
4. Style: `declare(strict_types=1)`, `final`, return types?
5. Reuse: which services, enums and Blade components already exist, and which CSS framework the views use?
6. Database: do tests run on a separate database from `.env`?

See [version-matrix.md](references/version-matrix.md) for version gates and how to tell old from new skeletons.

## Workflow

1. **Generate with Artisan** (`make:model -mfc`, `make:request`, `make:enum`, `make:class`, `make:component --view`, `make:policy`, `make:resource`) so namespaces and stubs match the project.
2. **Put each concern where Laravel expects it:**

   | Concern | Location |
   | --- | --- |
   | Input validation | Form request `rules()` |
   | "May this user do this?" | Policy |
   | Reusable query constraints | Eloquent scope |
   | Multi-step or repeated business logic | Service class in `app/Services` |
   | Fixed list of options | Backed enum in `app/Enums` |
   | Repeated markup | Blade component |
   | Side effects after an event | Queued listener or job |
   | Response shape | API resource or view |
   | Environment values | `config/*.php`, read with `config()` |

3. **Keep controllers to four jobs:** authorize, validate, delegate, respond.
4. **Type everything public:** parameters, return types, enums instead of string constants or lookup tables.
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

use App\Http\Requests\StoreOrderRequest;
use App\Http\Resources\OrderResource;
use App\Models\Order;
use App\Services\OrderService;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Gate;

class OrderController extends Controller
{
    public function store(StoreOrderRequest $request, OrderService $orders): JsonResponse
    {
        Gate::authorize('create', Order::class);

        $order = $orders->place($request->user(), $request->validated());

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
- `make:enum` and `make:class` need Laravel 11. On 10, create the file by hand.
- `Rule::enum()` needs Laravel 10.x or newer; its `only()` and `except()` need 11.
- Laravel 11+ ships `phpunit.xml` with SQLite `:memory:` active. Older skeletons have those lines commented out, so tests use the `.env` database.
- On Laravel 11+ skeletons the base `Controller` has no traits, so `$this->authorize()` fails. Use `Gate::authorize()`, or add `AuthorizesRequests` where the project already relies on it.
- `readonly` DTOs need PHP 8.2. Typed constants need 8.3. Check the `php` constraint in `composer.json`, not the local runtime.
- Laravel 13 offers attributes such as `#[Fillable]` and `#[Middleware]`. They are optional: match the surrounding code.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Same logic pasted into a second controller | Fixes land in one copy only | Move it to a service class |
| `$request->validate()` inline for a form | Rules cannot be reused or tested alone | Form request |
| `migrate:fresh` to "fix" a migration | Destroys the user's data | New migration, or ask first |
| `genders` or `religions` lookup table | Joins, seeders and foreign keys for five constants | Backed enum with `label()` |
| Copy-pasted button, table or field markup | One design change means editing every page | Blade component |
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

Run `phpstan` only if configured. Run tests only after the database check in Rule 3. Then confirm:

- [ ] No logic or markup block was duplicated; a service or component holds it
- [ ] Each form action type-hints a form request
- [ ] No destructive database command was run, and seeders are idempotent
- [ ] New option lists are enums, with no new lookup table
- [ ] The diff touches no unrelated files

## Additional Resources

- [house-rules.md](references/house-rules.md): service class, form request, enum and Blade component examples, and when each rule does not apply
- [conventions.md](references/conventions.md): naming, framework-first replacements, modern PHP usage
- [version-matrix.md](references/version-matrix.md): support dates, skeleton differences, feature gates
