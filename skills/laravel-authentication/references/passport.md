# Laravel Passport

Use Passport only when you need a real OAuth2 server. Otherwise use Sanctum.

## Install

```bash
composer require laravel/passport
php artisan install:api --passport
php artisan passport:keys
```

Add `Laravel\Passport\Contracts\OAuthenticatable` and the `Laravel\Passport\HasApiTokens` trait to `User`, and an `api` guard using the `passport` driver in `config/auth.php`. Check the install guide for your Passport major version, as `install:api --passport` is Laravel 11+.

## Keys

- `storage/oauth-private.key` and `oauth-public.key` must not be committed.
- In containers and multi-server setups, share keys through secrets:

  ```bash
  PASSPORT_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."
  PASSPORT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----..."
  ```

- Rotating keys invalidates all issued tokens.
- `php artisan passport:keys` on each new server would produce different keys and break tokens. Generate once, and distribute.

## Grants

| Grant | Client type | Create with | Status |
| --- | --- | --- | --- |
| Authorization code | Confidential server app | `passport:client` | Recommended |
| Authorization code + PKCE | SPA, mobile, public client | `passport:client --public` | Recommended |
| Device authorization | TV, CLI | `passport:client --device` | When input is limited |
| Client credentials | Machine-to-machine | `passport:client --client` | Recommended |
| Personal access | User-issued tokens | `passport:client --personal` | Sanctum is often simpler |
| Password | First-party legacy | `passport:client --password` | Disabled by default, avoid |
| Implicit | Legacy browser | `passport:client --implicit` | Disabled by default, avoid |

Enabling a legacy grant is deliberate:

```php
use Laravel\Passport\Passport;

Passport::enablePasswordGrant();
```

Only do so for an existing integration, and plan a move to PKCE.

## Token Lifetimes

Access tokens default to one year, which is too long for most apps. Set them in `AppServiceProvider::boot()`:

```php
use Carbon\CarbonInterval;
use Laravel\Passport\Passport;

Passport::tokensExpireIn(CarbonInterval::minutes(30));
Passport::refreshTokensExpireIn(CarbonInterval::days(30));
Passport::personalAccessTokensExpireIn(CarbonInterval::months(6));
```

These apply only to tokens issued afterwards. Purge old rows on a schedule:

```php
use Illuminate\Support\Facades\Schedule;

Schedule::command('passport:purge')->hourly();
```

## Scopes

```php
use Laravel\Passport\Passport;

Passport::tokensCan([
    'orders:read' => 'View your orders',
    'orders:write' => 'Create and change your orders',
]);
```

Protect routes (Passport 13 names):

```php
use Illuminate\Support\Facades\Route;
use Laravel\Passport\Http\Middleware\CheckToken;
use Laravel\Passport\Http\Middleware\CheckTokenForAnyScope;

Route::get('/orders', [OrderController::class, 'index'])
    ->middleware(['auth:api', CheckTokenForAnyScope::using('orders:read', 'orders:write')]);

Route::post('/orders', [OrderController::class, 'store'])
    ->middleware(['auth:api', CheckToken::using('orders:write')]);
```

For a client credentials token there is no user, so use `Laravel\Passport\Http\Middleware\EnsureClientIsResourceOwner`, and do not call `$request->user()`.

Older versions use `CheckScopes` and `CheckForAnyScope` with the aliases `scopes` and `scope`. Confirm by listing `vendor/laravel/passport/src/Http/Middleware`.

Scopes limit what the client may do. A policy must still check what the user may do.

## Authorization Code Flow Checks

- Validate exact `redirect_uri` values; no wildcards.
- Always send and verify `state` to prevent CSRF.
- Use PKCE (`S256`) for any client that can't keep a secret.
- Keep the consent screen on: only skip it for first-party clients you own.

## Testing

```php
use Laravel\Passport\Client;
use Laravel\Passport\Passport;

Passport::actingAs($user, ['orders:read']);

Passport::actingAsClient(Client::factory()->create(), ['orders:read']);
```

## Deployment Checklist

- [ ] Keys delivered by secret manager, identical on every server
- [ ] `passport:purge` scheduled
- [ ] Lifetimes configured
- [ ] Legacy grants off unless justified
- [ ] `/oauth/token` rate limited
- [ ] Redirect URIs reviewed

## Upgrading

Major Passport versions change client storage, hashing and middleware. Read `UPGRADE.md` in `laravel/passport` for each major step. Client secret hashing means a secret is only visible at creation.
