---
name: laravel-authentication
description: Use when implementing or fixing login, registration, password reset, API tokens, or authorization in Laravel, including Sanctum, Passport, OAuth2, SPA cookie auth, Fortify, policies and gates, or errors such as 401 Unauthenticated and 419 CSRF token mismatch.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel Authentication

Choose the simplest mechanism that fits the client, then authorize every action. Authentication says who; authorization says what.

## When to Use

- Choosing or setting up Sanctum, Passport, Fortify or a starter kit
- Adding login, registration, password reset, email verification or 2FA
- Writing policies, gates or token abilities
- Debugging 401, 403 or 419 responses

Auditing existing auth for vulnerabilities belongs to `laravel-security-audit`. Endpoint design belongs to `laravel-api-development`.

## Inspect the Project First

```bash
php artisan --version
composer show --locked | grep -E 'sanctum|passport|fortify|breeze|jetstream|socialite|spatie/laravel-permission'
cat config/auth.php | grep -nE "driver|provider|'model'"
ls app/Policies database/migrations | grep -iE 'polic|token|oauth'
php artisan route:list --except-vendor -v
```

An existing auth stack stays unless the user asks to replace it. Switching mechanisms invalidates clients and tokens. See [version-matrix.md](references/version-matrix.md).

## Workflow

### 1. Choose the mechanism

| Client | Use | Why |
| --- | --- | --- |
| Blade, Livewire or Inertia in the same app | Session (`web` guard) with a starter kit or Fortify | Built in |
| First-party SPA on the same top-level domain | Sanctum SPA cookies | CSRF-protected, no token in JS |
| First-party mobile app | Sanctum tokens | Simple, per-device, revocable |
| User-generated personal access tokens | Sanctum tokens | No OAuth overhead |
| Third parties acting for your users | Passport authorization code + PKCE | Requires real OAuth2 |
| Machine-to-machine with OAuth clients | Passport client credentials | OAuth2 grant |
| Social login | Socialite, then your own session or token | Identity only |

If no third party needs delegated access, Passport is the wrong tool. The official docs say to use Sanctum for SPAs, mobile apps and simple API tokens.

Breeze and Jetstream no longer receive updates. For new Laravel 12+ projects, use the current starter kits or headless Fortify.

### 2. Implement

Follow [sanctum.md](references/sanctum.md) or [passport.md](references/passport.md).

### 3. Authorize

Write a policy per model. Check ownership in the policy, not in controllers.

```php
<?php

namespace App\Policies;

use App\Models\Order;
use App\Models\User;

class OrderPolicy
{
    public function before(User $user): ?bool
    {
        return $user->is_admin ? true : null; // null falls through to the method.
    }

    public function view(User $user, Order $order): bool
    {
        return $user->id === $order->user_id;
    }

    public function update(User $user, Order $order): bool
    {
        return $user->id === $order->user_id
            && $order->status->isEditable()
            && $user->tokenCan('orders:write');
    }
}
```

`tokenCan()` returns `true` for first-party SPA sessions, so the same policy works for cookie and token clients. It requires Sanctum's `HasApiTokens` on `User`.

Enforce in one of these places, and stay consistent:

```php
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Route;

Gate::authorize('update', $order);

Route::put('/orders/{order}', [OrderController::class, 'update'])->can('update', 'order');
```

Scope lists rather than filtering after fetching: `$request->user()->orders()->paginate()`.

### 4. Protect credentials

```php
<?php

namespace App\Http\Controllers\Auth;

use App\Http\Controllers\Controller;
use App\Http\Requests\LoginRequest;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;

class SessionController extends Controller
{
    public function store(LoginRequest $request): RedirectResponse
    {
        $key = Str::lower($request->input('email')).'|'.$request->ip();

        if (RateLimiter::tooManyAttempts($key, 5)) {
            throw ValidationException::withMessages([
                'email' => __('auth.throttle', ['seconds' => RateLimiter::availableIn($key)]),
            ]);
        }

        if (! Auth::attempt($request->only('email', 'password'), $request->boolean('remember'))) {
            RateLimiter::hit($key);

            throw ValidationException::withMessages(['email' => __('auth.failed')]);
        }

        RateLimiter::clear($key);
        $request->session()->regenerate(); // Prevents session fixation.

        return redirect()->intended('/dashboard');
    }

    public function destroy(Request $request): RedirectResponse
    {
        Auth::guard('web')->logout();

        $request->session()->invalidate();
        $request->session()->regenerateToken();

        return redirect('/');
    }
}
```

Set password policy once in `AppServiceProvider::boot()`:

```php
use Illuminate\Validation\Rules\Password;

Password::defaults(fn () => app()->isProduction()
    ? Password::min(12)->uncompromised()
    : Password::min(8));
```

`uncompromised()` calls the Have I Been Pwned range API, sending only a hash prefix. Confirm outbound access is acceptable.

## Version Notes

- Laravel 13 renames the CSRF middleware to `PreventRequestForgery` and adds `Sec-Fetch-Site` origin checks. `VerifyCsrfToken` remains as a deprecated alias.
- Laravel 11+ uses `php artisan install:api` for Sanctum, and base controllers have no `AuthorizesRequests`.
- Laravel 11+ rehashes passwords on login if the work factor changed.
- Policies are auto-discovered when they follow naming conventions. `#[UsePolicy]` is available on Laravel 12+; `Gate::policy()` works everywhere.
- Passport middleware names changed in v13: `CheckToken` and `CheckTokenForAnyScope` replace `CheckScopes` and `CheckForAnyScope`. Check `vendor/laravel/passport/src/Http/Middleware`.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Using API tokens in your own SPA | Token exposed to XSS | Sanctum SPA cookies |
| `currentAccessToken()->delete()` on a session request | `TransientToken` has no `delete()` | Log out the session guard instead |
| Sanctum tokens that never expire | Stolen tokens live forever (default `expiration` is `null`) | Set expiry, schedule `sanctum:prune-expired` |
| Abilities without ownership checks | A valid token reads others' data | Check both in the policy |
| Different login errors for unknown email | User enumeration | One generic message |
| Throttling by IP only | Credential stuffing across IPs | Key by email + IP, add limits on both |
| Not revoking tokens on password change | Attacker stays in | `$user->tokens()->delete()` |
| Missing `session()->regenerate()` | Session fixation | Regenerate after login |
| `Route::post('/login')` inside `api` group for SPA | No session middleware | `statefulApi()`, or put it in `web` |
| Passport password grant for new apps | Laravel no longer recommends it, and it is off by default | Auth code + PKCE |
| Committing `oauth-*.key` | Anyone can forge tokens | Ignore in git, inject on deploy |
| Hiding admin buttons only | Endpoint still open | Enforce server-side |

## Verification

```php
it('blocks access to another user\'s order', function () {
    $order = Order::factory()->create();

    $this->actingAs(User::factory()->create())
        ->get(route('orders.show', $order))
        ->assertForbidden();
});

it('rejects a token without the required ability', function () {
    Sanctum::actingAs(User::factory()->create(), ['orders:read']);

    $this->postJson('/api/v1/orders', [])->assertForbidden();
});

it('throttles repeated failed logins', function () {
    $user = User::factory()->create();

    foreach (range(1, 5) as $attempt) {
        $this->post('/login', ['email' => $user->email, 'password' => 'wrong']);
    }

    $this->post('/login', ['email' => $user->email, 'password' => 'wrong'])
        ->assertSessionHasErrors('email');

    expect(session('errors')->first('email'))->toContain('seconds');
});
```

Test the matrix for each protected route: guest, wrong user, right user, admin. Then:

```bash
php artisan test --filter=Auth
php artisan route:list --except-vendor -v
```

Read the middleware under each route: every route without an `auth` entry should be intentional.

## Additional Resources

- [sanctum.md](references/sanctum.md): SPA, token and mobile setup, plus a 401/419 checklist
- [passport.md](references/passport.md): grants, scopes, lifetimes, key handling
- [version-matrix.md](references/version-matrix.md): skeleton and middleware differences
