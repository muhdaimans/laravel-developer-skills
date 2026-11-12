---
name: laravel-security-audit
description: Use when assessing a Laravel application's security, hardening it before launch, or checking for vulnerabilities such as SQL injection, XSS, IDOR, mass assignment, exposed debug tools, leaked secrets, insecure uploads, SSRF, and vulnerable Composer dependencies.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code. For applications you own or are authorized to test.
---

# Laravel Security Audit

Trace untrusted input to dangerous sinks, and verify every protected action is really protected. Report only what you can evidence.

## When to Use

- Pre-launch or periodic security review
- After an incident or a dependency advisory
- Hardening configuration and headers
- Answering "is this app secure?" with evidence

This is a defensive review of code you are authorized to assess. Routine PR review belongs to `laravel-code-review`. Fixing auth flows belongs to `laravel-authentication`.

## Inspect the Project First

```bash
php artisan --version
composer audit
composer outdated --direct
npm audit --omit=dev 2>/dev/null
php artisan route:list --except-vendor --json > /tmp/routes.json
php artisan about --only=environment
git log --all --oneline -- .env '*.pem' '*.key' 2>/dev/null | head
```

Record framework support status from [version-matrix.md](references/version-matrix.md). An end-of-life Laravel or PHP version is itself a finding. Never print secret values in your report.

## Workflow

Work through in order. Details and grep patterns are in [audit-checklist.md](references/audit-checklist.md).

1. **Map the attack surface:** routes, guards, unauthenticated endpoints, webhooks, uploads, admin tools.
2. **Authorization (highest yield):** for each state-changing or data-returning route, find the check that stops another user.
3. **Injection:** follow request data into raw SQL, Blade, shell, paths and URLs.
4. **Mass assignment and validation.**
5. **Secrets and configuration.**
6. **Dependencies.**
7. **Session, CSRF, CORS, headers.**
8. **Files and outbound requests.**
9. **Logging and data exposure.**
10. **Confirm exploitability** in a local or test environment, by reading the code path or with a test. Do not attack production.
11. **Report** using the format below, ranked by real risk.

### Quick Sink Search

```bash
grep -rnE 'whereRaw|orderByRaw|havingRaw|selectRaw|DB::(raw|statement|unprepared|select)\(' app
grep -rnE '\{!!' resources/views
grep -rnE '\$guarded\s*=\s*\[\s*\]|forceFill|forceCreate|Model::unguard' app
grep -rnE '\$request->(all|input|get)\(\)' app/Http
grep -rnE 'unserialize\(|shell_exec|exec\(|system\(|passthru|eval\(|Process::' app
grep -rnE 'withoutVerifying|verify.*false' app
grep -rnE 'redirect\(\$|redirect\(\)->to\(\$request' app
grep -rnE 'env\(' app routes
```

A hit is a lead, not a finding. Trace whether the value is user-controlled.

## Core Patterns: Vulnerable vs Safe

SQL injection, including identifiers that bindings can't protect:

```php
// Vulnerable: string interpolation, and a user-chosen column.
User::whereRaw("email = '{$request->email}'")->get();
User::orderBy($request->input('sort'))->get();

// Safe: bindings, and an allow-list.
User::whereRaw('email = ?', [$request->email])->get();

$sort = in_array($request->input('sort'), ['name', 'created_at'], true)
    ? $request->input('sort')
    : 'created_at';

User::orderBy($sort)->get();
```

Insecure direct object reference:

```php
// Vulnerable: any authenticated user can read any invoice.
$invoice = Invoice::findOrFail($id);

// Safe: scoped through the owner.
$invoice = $request->user()->invoices()->findOrFail($id);
```

Unsafe upload:

```php
// Vulnerable: client-chosen name, public disk, type by extension only.
$request->file('doc')->storeAs('public', $request->file('doc')->getClientOriginalName());

// Safe: validated, private disk, generated name.
$request->validate([
    'doc' => ['required', 'file', 'mimes:pdf,png,jpg', 'extensions:pdf,png,jpg', 'max:10240'],
]);

$path = $request->file('doc')->store('documents', 'private');
```

Serve private files through an authorized route.

## Severity

| Level | Criteria | Examples |
| --- | --- | --- |
| **Critical** | Unauthenticated compromise or mass data exposure | SQLi, leaked `APP_KEY`, debug page in production, RCE |
| **High** | Authenticated user reaches others' data or privileges | IDOR, privilege escalation, stored XSS |
| **Medium** | Needs conditions, or has limited impact | Missing rate limits, weak token lifetime, CORS too broad |
| **Low** | Defence in depth | Missing headers, verbose non-sensitive errors |

## Report Format

```markdown
# Security Audit: <app> (<date>)
Scope: <commit, code areas, what wasn't covered>
Stack: Laravel <x>, PHP <y>, <database>

## Summary
1 critical, 2 high, 3 medium. Fix the critical before release.

## Findings
### [CRITICAL] SQL injection in order search
Location: app/Http/Controllers/OrderController.php:58
Evidence: `q` flows unbound into `whereRaw()`.
Impact: Read of any table.
Fix: Use a binding, code below.
Verify: Test that a quote in `q` returns normal results.

## Checked, no issues
...

## Not covered
Infrastructure, third-party SaaS, live penetration test.
```

Redact secrets. If a real secret is found, its **rotation** is the fix: deleting from git is not enough.

## Version Notes

- Laravel 13 hardens defaults: `cache.serializable_classes => false`, `session.serialization => 'json'`, origin-aware `PreventRequestForgery`. Upgraded apps keep old config unless changed, so check them.
- `APP_PREVIOUS_KEYS` allows graceful `APP_KEY` rotation on 11+.
- Laravel 10 and 11 no longer receive security fixes. PHP 8.2 security support ends 2026-12-31.
- `extensions:` validation needs Laravel 11; on 10 rely on `mimes:` and `mimetypes:`.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Reporting grep hits as vulnerabilities | False alarms destroy trust | Trace to a user-controlled source |
| Stopping at scanners | They can't see authorization logic | Review routes and policies by hand |
| Testing only with admin | Hides access-control bugs | Test as another normal user |
| Treating Eloquent as injection-proof | Identifiers and raw methods aren't bound | Allow-list |
| Trusting `Rule::in` from the client | Hidden-field values can be forged | Derive server-side |
| Assuming `$hidden` secures output | Only affects serialization | Explicit resources |
| Deleting a leaked secret from git | It's still compromised | Rotate |
| Probing production | Harm and legal risk | Local or staging, with authorization |
| Pasting real secrets into the report | Report becomes a leak | Redact |

## Verification

Write a regression test for each fix:

```php
it('does not expose another team\'s invoice', function () {
    $invoice = Invoice::factory()->create();

    $this->actingAs(User::factory()->create())
        ->getJson("/api/v1/invoices/{$invoice->id}")
        ->assertNotFound();
});
```

```bash
composer audit
php artisan test
curl -sI https://staging.example.com | grep -iE 'strict-transport|x-content-type|x-frame|content-security'
curl -s -o /dev/null -w '%{http_code}\n' https://staging.example.com/.env
curl -s -o /dev/null -w '%{http_code}\n' https://staging.example.com/telescope
```

- [ ] Every finding has location, evidence and fix
- [ ] Every fix has a test
- [ ] Exposed secrets rotated
- [ ] "Not covered" is stated honestly

## Additional Resources

- [audit-checklist.md](references/audit-checklist.md): full checklist, OWASP mapping, secure headers middleware, production config
- [version-matrix.md](references/version-matrix.md): support status and default changes
