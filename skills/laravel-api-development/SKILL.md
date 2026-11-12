---
name: laravel-api-development
description: Use when building or changing a Laravel REST API, including endpoints, API resources, JSON error responses, pagination, filtering, versioning, rate limiting, idempotency, CORS, and problems such as HTML or redirects returned instead of JSON.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel API Development

A public API is a contract. Keep its shape stable, its errors predictable, and its internals out of responses.

## When to Use

- Adding or changing JSON endpoints
- Standardizing responses, errors, pagination or filtering
- Versioning or rate limiting an API
- Clients get HTML, a redirect to `/login`, or inconsistent errors

Token and session setup belongs to `laravel-authentication`. OpenAPI writing belongs to `laravel-documentation`. Query tuning belongs to `laravel-eloquent-optimization`.

## Inspect the Project First

```bash
php artisan --version
php artisan route:list --path=api --except-vendor
ls routes app/Http/Resources app/Http/Controllers/Api 2>/dev/null
grep -n 'api\|throttleApi\|statefulApi\|shouldRenderJsonWhen' bootstrap/app.php
composer show --locked | grep -E 'sanctum|passport|query-builder|scramble|l5-swagger'
```

Read one existing endpoint from route to response, then copy its envelope, error shape and pagination style. **Match existing clients' expectations**; a "better" format is a breaking change. See [version-matrix.md](references/version-matrix.md).

## Workflow

1. **Define the contract first:** method, URI, request fields, success status, response shape, error cases, auth, ability.
2. **Register routes.** On a Laravel 11+ skeleton, `routes/api.php` needs `php artisan install:api`.
3. **Add authorization and validation** in a policy and a form request.
4. **Build the response** with an API resource, never a raw model.
5. **Eager load** everything the resource reads.
6. **Paginate every list**, and cap `per_page`.
7. **Apply a rate limiter.** On a Laravel 11+ skeleton the `api` group has no throttle until you add one.
8. **Unify errors** in the exception handler.
9. **Write feature tests** for success, validation failure, unauthenticated, forbidden and not found.
10. **Document the endpoint** with `laravel-documentation`.

### Status code contract

| Situation | Status |
| --- | --- |
| Read or update success | 200 |
| Created (add a `Location` header) | 201 |
| Accepted for async processing | 202 |
| Delete success | 204 |
| Malformed request | 400 |
| Missing or invalid credentials | 401 |
| Authenticated but not allowed | 403 |
| Not found, or hidden from this user | 404 |
| Conflict with current state | 409 |
| Validation failure | 422 |
| Rate limited (with `Retry-After`) | 429 |

## Core Pattern: A Complete Endpoint

```php
<?php

use App\Http\Controllers\Api\V1\OrderController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')
    ->middleware(['auth:sanctum', 'throttle:api'])
    ->group(function () {
        Route::apiResource('orders', OrderController::class);
    });
```

```php
<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreOrderRequest;
use App\Http\Resources\OrderResource;
use App\Models\Order;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Support\Facades\Gate;

class OrderController extends Controller
{
    public function index(Request $request): AnonymousResourceCollection
    {
        $orders = $request->user()->orders()
            ->with('items.product:id,sku,name')
            ->withCount('items')
            ->latest('id')
            ->cursorPaginate(min($request->integer('per_page', 25), 100));

        return OrderResource::collection($orders);
    }

    public function store(StoreOrderRequest $request): JsonResponse
    {
        Gate::authorize('create', Order::class);

        $order = $request->user()->orders()->create($request->validated());

        return OrderResource::make($order)
            ->response()
            ->setStatusCode(201)
            ->header('Location', route('orders.show', $order));
    }

    public function show(Order $order): OrderResource
    {
        Gate::authorize('view', $order);

        return OrderResource::make($order->load('items.product'));
    }
}
```

```php
<?php

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

class OrderResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'status' => $this->status,
            'total_cents' => $this->total_cents,
            'items_count' => $this->whenCounted('items'),
            'items' => OrderItemResource::collection($this->whenLoaded('items')),
            'created_at' => $this->created_at->toIso8601String(),
        ];
    }
}
```

Resources make the response an explicit allow-list. A column added to the table will not leak.

## Core Pattern: Rate Limiting

Define limiters in `AppServiceProvider::boot()` (on the legacy layout, `RouteServiceProvider`):

```php
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;

RateLimiter::for('api', function (Request $request) {
    return $request->user()
        ? Limit::perMinute(120)->by($request->user()->id)
        : Limit::perMinute(30)->by($request->ip());
});
```

Use the `redis` cache store for limiters when running several app servers. Behind a proxy, `$request->ip()` is only correct once trusted proxies are configured.

## Core Pattern: JSON Errors

```php
<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

return Application::configure(basePath: dirname(__DIR__))
    ->withMiddleware(function (Middleware $middleware): void {
        // Without this, an API guest with no Accept header fails with
        // "Route [login] not defined" before the exception handler runs.
        $middleware->redirectGuestsTo(
            fn (Request $request) => $request->is('api/*') ? null : route('login')
        );
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson()
        );

        $exceptions->render(function (NotFoundHttpException $e, Request $request) {
            if ($request->is('api/*')) {
                return response()->json(['message' => 'Resource not found.'], 404);
            }
        });
    })
    ->create();
```

`redirectGuestsTo` and `shouldRenderJsonWhen` do different jobs: the first stops `auth` from building a login redirect, and the second makes the handler render JSON. An API needs both. On the legacy layout, return `null` from `redirectTo()` in `app/Http/Middleware/Authenticate.php`.

The render closure hides model names from the default message `No query results for model [App\Models\Order]`. See [api-recipes.md](references/api-recipes.md) for the legacy `Handler.php` form, error catalogue, filtering, idempotency and versioning.

## Version Notes

- Laravel 13 includes first-party JSON:API resources. Use them only if clients expect JSON:API. See the `eloquent-resources` docs.
- Laravel 11+ `withRouting(apiPrefix: 'api/admin')` changes the prefix; legacy apps set it in `RouteServiceProvider`.
- `config/cors.php` must be published with `php artisan config:publish cors` on Laravel 11+.
- `Limit::perSecond()` needs Laravel 11.
- Before 11, `$this->authorize()` works on the base controller, and is common in older code.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| `return Order::find($id)` | Exposes every column, hides `$hidden` mistakes | API resource |
| `Order::findOrFail($id)` without an owner check | IDOR: any user reads any order | Policy, or scope through the user |
| Trusting `per_page` | `?per_page=1000000` | `min($input, 100)` |
| Sorting by raw input | Column disclosure, index abuse | Allow-list sort fields |
| Returning 200 with `{"error": ...}` | Clients and monitoring miss failures | Real status codes |
| Redirect to `route('login')`, or `Route [login] not defined` | `auth` builds the redirect before exceptions render | `redirectGuestsTo()` plus `shouldRenderJsonWhen()` |
| Breaking changes in `v1` | Silent client failures | New version, or additive change |
| Dates in app timezone without offset | Client-side misinterpretation | ISO 8601 with offset, UTC storage |
| Resources reading unloaded relations | N+1 | `whenLoaded()` |
| Sequential IDs when enumeration matters | Reveals volume, enables scraping | `public_id` ULID, plus authorization |
| Long work in the request | Timeouts | Queue it, return 202 with a status URL |
| Credentials or stack traces in errors | Information leak | `APP_DEBUG=false`, generic 500 |

## Verification

```php
it('creates an order', function () {
    $user = User::factory()->create();

    $this->actingAs($user, 'sanctum')
        ->postJson('/api/v1/orders', ['items' => [['sku' => 'A1', 'quantity' => 2]]])
        ->assertCreated()
        ->assertHeader('Location')
        ->assertJsonStructure(['data' => ['id', 'status', 'total_cents']]);
});

it('hides another user\'s order', function () {
    $order = Order::factory()->create();

    $this->actingAs(User::factory()->create(), 'sanctum')
        ->getJson("/api/v1/orders/{$order->id}")
        ->assertForbidden();
});

it('rejects invalid input', function () {
    $this->actingAs(User::factory()->create(), 'sanctum')
        ->postJson('/api/v1/orders', [])
        ->assertUnprocessable()
        ->assertJsonValidationErrors(['items']);
});
```

Then exercise it for real:

```bash
php artisan route:list --path=api/v1
curl -si -H 'Accept: application/json' -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/orders
```

Confirm headers include `X-RateLimit-Limit`, and a 404 and 500 both return JSON.

## Additional Resources

- [api-recipes.md](references/api-recipes.md): error catalogue, filtering, versioning, idempotency keys, webhooks, ETags
- [version-matrix.md](references/version-matrix.md): skeleton differences
