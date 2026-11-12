# API Recipes

## Error Envelope

Laravel's default validation shape is widely understood, so keep it and align other errors to it:

```json
{
  "message": "The items field is required.",
  "errors": { "items": ["The items field is required."] }
}
```

For domain errors, add a stable machine code. Clients must not parse messages.

```php
<?php

namespace App\Exceptions;

use Exception;
use Illuminate\Http\JsonResponse;

class InsufficientStockException extends Exception
{
    public function render(): JsonResponse
    {
        return response()->json([
            'message' => 'Not enough stock to complete this order.',
            'code' => 'insufficient_stock',
        ], 409);
    }
}
```

## Legacy Exception Handler (`app/Exceptions/Handler.php`)

```php
use Illuminate\Http\Request;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

public function register(): void
{
    $this->renderable(function (NotFoundHttpException $e, Request $request) {
        if ($request->is('api/*')) {
            return response()->json(['message' => 'Resource not found.'], 404);
        }
    });
}

protected function shouldReturnJson($request, \Throwable $e): bool
{
    return $request->is('api/*') || parent::shouldReturnJson($request, $e);
}
```

## Allow-Listed Filtering and Sorting

No dependency needed. If `spatie/laravel-query-builder` is already installed, use that instead.

```php
<?php

namespace App\Http\Requests;

use App\Enums\OrderStatus;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class ListOrdersRequest extends FormRequest
{
    public function rules(): array
    {
        return [
            'status' => ['nullable', Rule::enum(OrderStatus::class)],
            'from' => ['nullable', 'date'],
            'sort' => ['nullable', Rule::in(['created_at', '-created_at', 'total_cents', '-total_cents'])],
            'per_page' => ['nullable', 'integer', 'between:1,100'],
        ];
    }
}
```

```php
$sort = $request->validated('sort', '-created_at');

$orders = Order::query()
    ->whereBelongsTo($request->user())
    ->when($request->validated('status'), fn ($q, $status) => $q->where('status', $status))
    ->when($request->validated('from'), fn ($q, $from) => $q->where('created_at', '>=', $from))
    ->orderBy(ltrim($sort, '-'), str_starts_with($sort, '-') ? 'desc' : 'asc')
    ->orderBy('id')
    ->paginate($request->integer('per_page', 25));
```

The `id` tiebreaker gives stable ordering across pages.

## Versioning

| Strategy | Use when |
| --- | --- |
| URI prefix (`/api/v1`) | Default choice: visible, cacheable, simple routing |
| Header or media type | Clients are tightly managed and need clean URIs |

Additive changes do not need a new version: new optional fields, new endpoints, new enum values if clients were told to tolerate unknowns. Breaking changes include removing or renaming a field, changing a type, tightening validation, or changing a default.

Keep `V1` and `V2` as separate controller and resource namespaces that share Actions. Announce retirement with the `Deprecation` and `Sunset` response headers:

```php
<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class DeprecatedApiVersion
{
    public function handle(Request $request, Closure $next, string $sunset): Response
    {
        $response = $next($request);
        $response->headers->set('Deprecation', 'true');
        $response->headers->set('Sunset', $sunset);

        return $response;
    }
}
```

## Idempotency Keys

Protect payment-like `POST`s from client retries.

```php
<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Symfony\Component\HttpFoundation\Response;

class EnsureIdempotency
{
    public function handle(Request $request, Closure $next): Response
    {
        $key = $request->header('Idempotency-Key');

        if ($key === null) {
            return $next($request);
        }

        $fingerprint = hash('sha256', $request->user()->id.'|'.$request->path().'|'.$key);
        $cacheKey = "idempotency:{$fingerprint}";

        if ($stored = Cache::get($cacheKey)) {
            return response($stored['body'], $stored['status'], [
                'Content-Type' => 'application/json',
                'Idempotent-Replay' => 'true',
            ]);
        }

        $lock = Cache::lock("{$cacheKey}:lock", 30);

        if (! $lock->get()) {
            return response()->json(['message' => 'A request with this key is in progress.'], 409);
        }

        try {
            $response = $next($request);

            if ($response->getStatusCode() < 500) {
                Cache::put($cacheKey, [
                    'status' => $response->getStatusCode(),
                    'body' => $response->getContent(),
                ], now()->addDay());
            }

            return $response;
        } finally {
            $lock->release();
        }
    }
}
```

Scope the key to the user, as shown, so one client can't replay another's response. For money, also put a unique constraint in the database: the cache is an optimization, the constraint is the guarantee.

## Long-Running Work

```php
public function store(StoreExportRequest $request): JsonResponse
{
    $export = $request->user()->exports()->create(['status' => 'queued']);

    GenerateExport::dispatch($export);

    return response()->json([
        'data' => ['id' => $export->id, 'status' => $export->status],
    ], 202)->header('Location', route('exports.show', $export));
}
```

## Conditional Requests

```php
use Illuminate\Support\Facades\Route;

Route::get('/catalog', CatalogController::class)
    ->middleware('cache.headers:public;max_age=300;etag');
```

Use only on responses that do not vary by user.

## Receiving Webhooks

```php
<?php

namespace App\Http\Controllers;

use App\Jobs\ProcessStripeEvent;
use App\Models\WebhookEvent;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

class StripeWebhookController extends Controller
{
    public function __invoke(Request $request): Response
    {
        $signature = hash_hmac('sha256', $request->getContent(), config('services.stripe.webhook_secret'));

        abort_unless(hash_equals($signature, (string) $request->header('X-Signature')), 401);

        $event = WebhookEvent::firstOrCreate(
            ['provider_id' => $request->json('id')],
            ['payload' => $request->json()->all()],
        );

        if ($event->wasRecentlyCreated) {
            ProcessStripeEvent::dispatch($event);
        }

        return response()->noContent();
    }
}
```

Rules: verify the signature over the raw body, compare in constant time, deduplicate by provider event ID, queue the work and return fast. Real providers have their own signature scheme and timestamp check, so use their SDK verifier when it is available. Exempt the route from CSRF if it is in the `web` group.
