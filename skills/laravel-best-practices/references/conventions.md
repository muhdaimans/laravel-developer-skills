# Laravel Conventions Reference

## Naming

| Item | Convention | Example |
| --- | --- | --- |
| Model | Singular PascalCase | `OrderItem` |
| Table | Plural snake_case | `order_items` |
| Pivot table | Singular models, alphabetical | `product_tag` |
| Foreign key | Singular model + `_id` | `order_id` |
| Polymorphic | `-able` suffix | `commentable_id`, `commentable_type` |
| Relationship | Singular or plural by cardinality | `author()`, `comments()` |
| Controller | Singular resource + `Controller` | `OrderController` |
| Invokable controller | Verb phrase | `CancelOrderController` |
| Form request | Verb + resource + `Request` | `StoreOrderRequest` |
| Resource | Resource + `Resource` | `OrderResource` |
| Job | Imperative verb | `SendInvoice` |
| Event | Past tense | `OrderShipped` |
| Listener | Imperative | `NotifyWarehouse` |
| Policy | Model + `Policy` | `OrderPolicy` |
| Enum | Singular | `OrderStatus` |
| Route name | Dot notation | `orders.items.store` |
| Route URI | Plural kebab-case | `/order-items` |
| Config key | snake_case | `services.stripe.webhook_secret` |
| Artisan command | `namespace:verb` | `orders:prune-abandoned` |

Boolean columns read as facts (`is_active`, `has_paid`). Timestamps read as events (`published_at`). A nullable timestamp is usually better than a boolean plus a separate date.

## Framework-First Replacements

| Instead of | Use |
| --- | --- |
| `isset($a['x']) ? $a['x'] : null` | `data_get($a, 'x')` or `$a['x'] ?? null` |
| `array_filter` + `array_map` chains | `collect($items)->filter()->map()` |
| `date('Y-m-d')` | `now()->toDateString()` |
| Custom retry loop | `retry(3, fn () => ..., 100)` |
| `curl_*` | `Http::timeout(5)->retry(2, 200)->get($url)` |
| `file_put_contents(storage_path(...))` | `Storage::disk('s3')->put(...)` |
| Manual slug generation | `Str::slug()` |
| Manual `try/catch` + rollback | `DB::transaction(fn () => ...)` |
| Cron per task | Scheduler |
| Manual password check | `Hash::check()` |
| Custom "cache or compute" | `Cache::remember()` |
| Custom per-request memo | `once()` on Laravel 11+ |

## Dependency Injection vs Facades vs Helpers

All three are legitimate. Pick what the project uses.

- Constructor injection suits classes with several collaborators, and makes dependencies visible.
- Facades are fully fakeable (`Mail::fake()`), so "facades can't be tested" is false.
- `auth()->user()` inside a domain class hides its dependency on the HTTP request. Pass the user in as an argument.
- Never resolve services in a constructor of a long-lived object if the project runs Octane: an injected request or config repository goes stale between requests.

## Enums

```php
<?php

namespace App\Enums;

enum OrderStatus: string
{
    case Pending = 'pending';
    case Paid = 'paid';
    case Shipped = 'shipped';
    case Cancelled = 'cancelled';

    /** @return list<self> */
    public static function openStatuses(): array
    {
        return [self::Pending, self::Paid];
    }

    public function canTransitionTo(self $next): bool
    {
        return match ($this) {
            self::Pending => in_array($next, [self::Paid, self::Cancelled], true),
            self::Paid => in_array($next, [self::Shipped, self::Cancelled], true),
            self::Shipped, self::Cancelled => false,
        };
    }
}
```

Store the backed value in a `string` column rather than a database `ENUM`. Adding a case then needs no schema change.

## Modern PHP in Laravel Code

Good fit:

```php
<?php

namespace App\Data;

final readonly class Money
{
    public function __construct(
        public int $amount,
        public string $currency,
    ) {
    }

    public function add(self $other): self
    {
        return new self($this->amount + $other->amount, $this->currency);
    }
}
```

Not a fit: `readonly`, property hooks, or typed public properties for Eloquent columns. Eloquent attributes are not real properties, and a declared property shadows the magic accessor.

## Formatting

- Pint with the `laravel` preset is the framework default. Its rules build on PSR-12. Use `"preset": "psr12"` in `pint.json` only if the team requires strict PSR-12.
- Never reformat files you did not otherwise change. `pint --dirty` limits the blast radius.
- Do not add `declare(strict_types=1)` to one file in a project without it: behaviour differs for scalar coercion, including calls into that file's dependencies.
