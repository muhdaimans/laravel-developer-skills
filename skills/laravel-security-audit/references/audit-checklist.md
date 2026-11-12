# Security Audit Checklist

## OWASP Top 10 Mapping

| Risk | Laravel focus |
| --- | --- |
| Broken access control | Policies, scoped queries, route binding, signed URLs |
| Security misconfiguration | `APP_DEBUG`, exposed tools, CORS, headers |
| Supply chain failures | `composer audit`, `npm audit`, abandoned packages |
| Cryptographic failures | `APP_KEY`, HTTPS, password hashing, `encrypted` casts |
| Injection | Raw SQL, Blade `{!! !!}`, shell commands |
| Insecure design | Rate limits, business logic abuse, state transitions |
| Authentication failures | Throttling, token lifetime, session rotation |
| Data integrity failures | `unserialize`, webhook signatures, unsigned updates |
| Logging and alerting failures | Missing audit trail, secrets in logs |
| Mishandled exceptions | Fail-open error paths, leaked stack traces |

## Access Control

- [ ] Every route is either authenticated or deliberately public
- [ ] Every model action has a policy or scoped query
- [ ] Nested resources use `scopeBindings()`, or check the parent
- [ ] Admin routes have server-side role checks
- [ ] Bulk endpoints authorize each ID, not only the first
- [ ] Exports and report endpoints apply tenant filters
- [ ] File downloads authorize the record
- [ ] Signed URLs use the `signed` middleware, and expire
- [ ] Status transitions are validated on the server

For each route, test with: guest, a different normal user, the right user.

## Injection and Output

- [ ] Raw query methods use bindings
- [ ] `orderBy`, `groupBy` and column names from input are allow-listed
- [ ] `{!! !!}` output is sanitized by an allow-list HTML purifier, or removed
- [ ] User URLs in `href` are limited to `http`/`https`, blocking `javascript:`
- [ ] Blade variables inside `<script>` use `@js()`
- [ ] Shell calls use the `Process` facade with an argument array, never interpolation
- [ ] `Storage` paths don't accept `../` from input
- [ ] `view($request->input(...))` and dynamic includes are absent
- [ ] Mail headers don't accept raw user input

## Mass Assignment and Validation

- [ ] `$fillable` excludes `is_admin`, `role`, `team_id`, `balance`
- [ ] Writes use `validated()`
- [ ] `forceFill()` and `forceCreate()` never receive request data
- [ ] Nested arrays have rules
- [ ] Authorization fields are set by the server

## Secrets and Configuration

```bash
git ls-files | grep -E '(^|/)\.env$|\.pem$|oauth-.*\.key$'
git log -p --all -S 'APP_KEY=base64' --oneline | head
php artisan config:show app | grep -E 'debug|env|url'
```

- [ ] `.env` isn't tracked, and is outside the web root
- [ ] `APP_DEBUG=false`, `APP_ENV=production`
- [ ] Web root is `public/`, so `/.env`, `/.git/` and `/storage/logs/` return 404
- [ ] `APP_KEY` is unique per environment, and never shared
- [ ] Database user has least privilege
- [ ] `phpinfo()` and debug routes are absent
- [ ] Laravel's `APP_DEBUG` page or Ignition can't render in production
- [ ] Telescope, Horizon, Pulse and log viewers are gated, or not installed in production
- [ ] Debugbar is a `require-dev` package, and off in production

## Sessions and CSRF

- [ ] `SESSION_SECURE_COOKIE=true`
- [ ] `http_only` is `true`, `same_site` is `lax` or `strict`
- [ ] Session regenerates at login; invalidated at logout
- [ ] CSRF exclusions are limited to signed webhooks
- [ ] Trusted proxies are set to known addresses, not `*` on a host reachable directly

## CORS

- [ ] `allowed_origins` is explicit where credentials are on
- [ ] `supports_credentials` is on only if needed
- [ ] `allowed_origins_patterns` regexes are anchored

## Files

- [ ] Type verified by content (`mimes`, `mimetypes`), plus size limits
- [ ] SVG and HTML uploads aren't served inline from the app domain
- [ ] Generated filenames
- [ ] Private disk by default
- [ ] PHP execution disabled in upload directories
- [ ] Archive extraction checks paths (Zip Slip)
- [ ] Image processing limits dimensions

## Outbound Requests (SSRF)

When a user supplies a URL to fetch, block internal targets. This resolves the host first; a resolver that re-resolves later can still be rebound, so route such fetches through an egress proxy for high-risk features.

```php
<?php

namespace App\Support;

use InvalidArgumentException;

class SafeUrl
{
    public static function assertPublic(string $url): void
    {
        $parts = parse_url($url);

        if (! in_array($parts['scheme'] ?? '', ['http', 'https'], true)) {
            throw new InvalidArgumentException('Unsupported scheme.');
        }

        $ip = gethostbyname($parts['host'] ?? '');

        $public = filter_var(
            $ip,
            FILTER_VALIDATE_IP,
            FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE,
        );

        if ($public === false) {
            throw new InvalidArgumentException('Target is not allowed.');
        }
    }
}
```

- [ ] Redirects are disabled, or each hop is revalidated
- [ ] Timeouts are set
- [ ] Cloud metadata (`169.254.169.254`) is unreachable

## Abuse Controls

- [ ] Login, password reset, verification, token, and OTP routes are throttled
- [ ] Expensive endpoints have limits
- [ ] Enumeration: same response for known and unknown accounts
- [ ] Pagination size is capped
- [ ] `max:` on strings and arrays

## Cryptography and Data

- [ ] `encrypted` cast for sensitive columns where justified
- [ ] Passwords use `Hash`, and never reversible storage
- [ ] Token comparison uses `hash_equals`
- [ ] Random values use `Str::random()` or `random_bytes()`, not `rand()` or `mt_rand()`
- [ ] Webhook signatures are verified over the raw body
- [ ] `unserialize()` isn't called on user data
- [ ] Laravel 13 options reviewed: `cache.serializable_classes`, `session.serialization`

## Logging

- [ ] Passwords, tokens and card data are excluded from logs and context
- [ ] `#[\SensitiveParameter]` is used on secret arguments
- [ ] `dontFlash` covers password inputs
- [ ] Security events are recorded: login failures, role changes, exports
- [ ] Logs are not web accessible

## Security Headers Middleware

Add only if the proxy doesn't already send them. Register it globally with `$middleware->append()`: middleware in a route group is skipped when something earlier in the group fails, so a 404 from route-model binding would go out without these headers.

```php
<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class SecurityHeaders
{
    public function handle(Request $request, Closure $next): Response
    {
        $response = $next($request);

        $response->headers->add([
            'X-Content-Type-Options' => 'nosniff',
            'X-Frame-Options' => 'DENY',
            'Referrer-Policy' => 'strict-origin-when-cross-origin',
            'Permissions-Policy' => 'geolocation=(), camera=(), microphone=()',
        ]);

        if ($request->isSecure()) {
            $response->headers->set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
        }

        return $response;
    }
}
```

Roll out a `Content-Security-Policy` in report-only mode first; inline scripts and Vite need planning.

## Dependencies

- [ ] `composer audit` and `npm audit` clean, or risks accepted in writing
- [ ] CI runs `composer audit`
- [ ] Abandoned packages have a replacement plan
- [ ] `composer.lock` is committed
- [ ] Framework and PHP versions are supported
