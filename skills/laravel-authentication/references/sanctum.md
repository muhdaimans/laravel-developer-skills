# Laravel Sanctum

## Install

```bash
php artisan install:api
```

On Laravel 10, Sanctum is part of the skeleton. Run `php artisan migrate` if `personal_access_tokens` is missing. Add `Laravel\Sanctum\HasApiTokens` to `User`.

## SPA Cookie Authentication

Requires the SPA and API to share a top-level domain (subdomains are fine).

1. Enable stateful middleware in `bootstrap/app.php`:

   ```php
   <?php

   use Illuminate\Foundation\Application;
   use Illuminate\Foundation\Configuration\Middleware;

   return Application::configure(basePath: dirname(__DIR__))
       ->withMiddleware(function (Middleware $middleware): void {
           $middleware->statefulApi();
       })
       ->create();
   ```

   On the legacy layout, uncomment `EnsureFrontendRequestsAreStateful` in the `api` group of `app/Http/Kernel.php`.

2. Set environment values:

   ```bash
   SANCTUM_STATEFUL_DOMAINS=app.example.com,localhost:5173
   SESSION_DOMAIN=.example.com
   SESSION_SECURE_COOKIE=true
   ```

   Include the port if the SPA uses one in development.

3. Publish and edit CORS with `php artisan config:publish cors`:

   ```php
   <?php

   return [
       'paths' => ['api/*', 'sanctum/csrf-cookie', 'login', 'logout'],
       'allowed_origins' => [env('FRONTEND_URL')],
       'allowed_methods' => ['*'],
       'allowed_headers' => ['*'],
       'supports_credentials' => true,
   ];
   ```

   `supports_credentials` cannot be combined with a wildcard origin.

4. Configure the client, then fetch the CSRF cookie before logging in:

   ```js
   axios.defaults.withCredentials = true;
   axios.defaults.withXSRFToken = true;

   await axios.get('/sanctum/csrf-cookie');
   await axios.post('/login', { email, password });
   ```

5. Protect routes with `auth:sanctum`.

## API Tokens

```php
<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Validation\ValidationException;

class TokenController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'email' => ['required', 'email'],
            'password' => ['required', 'string'],
            'device_name' => ['required', 'string', 'max:255'],
        ]);

        $user = User::where('email', $data['email'])->first();

        if (! $user || ! Hash::check($data['password'], $user->password)) {
            throw ValidationException::withMessages([
                'email' => [__('auth.failed')],
            ]);
        }

        $token = $user->createToken(
            $data['device_name'],
            ['orders:read', 'orders:write'],
            now()->addDays(30),
        );

        return response()->json(['token' => $token->plainTextToken], 201);
    }

    public function destroy(Request $request): JsonResponse
    {
        $request->user()->currentAccessToken()->delete();

        return response()->json(null, 204);
    }
}
```

Throttle this route. Tokens are stored as SHA-256 hashes, and the plain text is available only at creation.

### Abilities

Register aliases in `bootstrap/app.php`:

```php
<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Middleware;
use Laravel\Sanctum\Http\Middleware\CheckAbilities;
use Laravel\Sanctum\Http\Middleware\CheckForAnyAbility;

return Application::configure(basePath: dirname(__DIR__))
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->alias([
            'abilities' => CheckAbilities::class,
            'ability' => CheckForAnyAbility::class,
        ]);
    })
    ->create();
```

```php
use Illuminate\Support\Facades\Route;

Route::post('/orders', [OrderController::class, 'store'])
    ->middleware(['auth:sanctum', 'abilities:orders:write']);
```

`abilities:a,b` needs all; `ability:a,b` needs any.

### Expiry and Pruning

`config/sanctum.php` `expiration` is in minutes and defaults to `null` (never). Prune on a schedule:

```php
use Illuminate\Support\Facades\Schedule;

Schedule::command('sanctum:prune-expired --hours=24')->daily();
```

`SANCTUM_TOKEN_PREFIX` sets a prefix so secret scanners can recognize leaked tokens.

## Testing

```php
use Laravel\Sanctum\Sanctum;

Sanctum::actingAs($user, ['orders:read']);
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| 419 on login | `/sanctum/csrf-cookie` called first; `X-XSRF-TOKEN` sent; `SESSION_DOMAIN` correct |
| 401 after successful login | Domain missing from `SANCTUM_STATEFUL_DOMAINS` (with port); request has no `Referer`/`Origin`; `statefulApi()` absent |
| Cookie not set in browser | `SESSION_SECURE_COOKIE=true` over HTTP; `SameSite` too strict across sites; SPA on a different top-level domain |
| CORS error | Origin not allowed; `supports_credentials` false; `config/cors.php` paths omit `sanctum/csrf-cookie` |
| Works locally, fails in production | `php artisan config:clear` then re-cache; proxy not trusted, so `https` is not detected |
| `TransientToken::delete()` error | Session request calling a token-only API |
| Bearer token rejected | Token expired; `Authorization` header stripped by the proxy; guard not `sanctum` |

Inspect the actual values:

```bash
php artisan config:show sanctum
php artisan config:show session
curl -si -H 'Origin: https://app.example.com' https://api.example.com/sanctum/csrf-cookie
```
