---
name: laravel-documentation
description: Use when documenting a Laravel project, including README setup guides, OpenAPI or Swagger API docs, architecture decision records, runbooks, upgrade notes, changelogs, PHPDoc, and onboarding documentation.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel Documentation

Document what readers need and can't get from the code, verified against the running project. Wrong docs are worse than none.

## When to Use

- Writing or repairing a README or setup guide
- Documenting a REST API
- Recording an architecture decision
- Writing runbooks, upgrade notes or a changelog
- Adding PHPDoc that tools can use

Designing the API belongs to `laravel-api-development`. Deciding the architecture belongs to `laravel-project-architecture`.

## Inspect the Project First

```bash
php artisan --version
ls README* CHANGELOG* CONTRIBUTING* docs 2>/dev/null
grep -E '"php"' composer.json
sed -n '/"scripts"/,/^    }/p' composer.json
php artisan route:list --except-vendor --json
php artisan schedule:list
cat .env.example
composer show --locked | grep -E 'scramble|l5-swagger|scribe'
```

Derive facts from these outputs, and never from memory or guesswork. Note which documentation tools and locations exist. See [version-matrix.md](references/version-matrix.md) for the exact versions you may state.

## Workflow

1. **Name the reader and the task:** a new developer running it, a client integrating, an on-call engineer at 3am.
2. **Pick the document:**

   | Reader need | Document | Location |
   | --- | --- | --- |
   | Run the project | README | Root |
   | Integrate with the API | OpenAPI + guide | `docs/api/` |
   | Why it's built this way | ADR | `docs/adr/` |
   | Fix an incident | Runbook | `docs/runbooks/` |
   | What changed | Changelog | Root |
   | Understand a type | PHPDoc | Source |

3. **Use existing tooling.** If an OpenAPI generator is installed, annotate for it. Do not add a new one unless asked.
4. **Draft from the template** in [templates.md](references/templates.md).
5. **Execute it:** run every command in a clean checkout where possible, and compare every endpoint with the code.
6. **Link, don't duplicate.** A fact lives in one place.

## Core Pattern: PHPDoc That Earns Its Place

Native types say most things. Add PHPDoc only for what they can't express.

```php
<?php

namespace App\Services;

use App\Models\Order;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Support\Carbon;

class RefundService
{
    /**
     * Refund every paid order placed before the cutoff.
     *
     * Runs one database transaction per order, so a failure keeps earlier refunds.
     *
     * @param  list<int>  $orderIds
     * @return Collection<int, Order>
     *
     * @throws \App\Exceptions\RefundWindowClosed When the cutoff is older than 90 days.
     */
    public function refundBatch(array $orderIds, Carbon $cutoff): Collection
    {
        // ...
    }
}
```

A line such as `@param string $name The name` adds nothing: remove it. Comment **why**, not what.

## Core Pattern: OpenAPI From Real Behaviour

```yaml
openapi: 3.1.0
info:
  title: Acme API
  version: 1.0.0
servers:
  - url: https://api.example.com/api/v1
security:
  - bearerAuth: []
paths:
  /orders/{order}:
    get:
      summary: Get an order
      operationId: getOrder
      parameters:
        - name: order
          in: path
          required: true
          schema: { type: integer }
      responses:
        '200':
          description: The order
          content:
            application/json:
              schema:
                type: object
                required: [data]
                properties:
                  data: { $ref: '#/components/schemas/Order' }
        '401': { $ref: '#/components/responses/Unauthenticated' }
        '403': { $ref: '#/components/responses/Forbidden' }
        '404': { $ref: '#/components/responses/NotFound' }
components:
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer }
  schemas:
    Order:
      type: object
      required: [id, status, total_cents, created_at]
      properties:
        id: { type: integer }
        status: { type: string, enum: [pending, paid, shipped, cancelled] }
        total_cents: { type: integer, description: Total in minor currency units }
        created_at: { type: string, format: date-time }
  responses:
    Unauthenticated:
      description: Missing or invalid credentials
    Forbidden:
      description: Not allowed to access this resource
    NotFound:
      description: Resource not found
```

Take each field from the API resource's `toArray()`, each request field from the form request's `rules()`, and each status from the controller, policy and exception handler. See [templates.md](references/templates.md) for the mapping table.

Keep the spec honest with a contract test:

```php
it('matches the documented order shape', function () {
    $order = Order::factory()->create();

    $this->actingAs($order->user, 'sanctum')
        ->getJson("/api/v1/orders/{$order->id}")
        ->assertOk()
        ->assertJsonStructure(['data' => ['id', 'status', 'total_cents', 'created_at']]);
});
```

## Version Notes

- State the versions from `composer.lock` and `composer.json`, and never assume "latest".
- Setup commands differ: `php artisan install:api` on 11+; the default `DB_CONNECTION` is `sqlite` in the 11+ skeleton.
- On Laravel 11+, `composer run dev` may exist in `composer.json`. Document it only if present.
- Laravel Boost, where installed, exposes docs to AI tools. Project docs remain the source of project-specific facts.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Copying the Laravel default README | Tells readers nothing about this app | Rewrite for this project |
| Commands never executed | First step fails | Run them from a clean clone |
| Docs written from memory | Invented endpoints and env keys | Derive from `route:list`, `.env.example` |
| Real secrets in examples | Leak | Obvious placeholders |
| Documenting the 200 only | Clients can't handle errors | Include every error status |
| Duplicating the same fact | They drift apart | One source, then links |
| Restating code in comments | Noise that goes stale | Explain intent and constraints |
| Changelog from `git log` | Unreadable for users | Group by user impact |
| ADR rewritten after the fact | History lost | Add a new ADR that supersedes |
| Undated "temporary" notes | Permanent confusion | Link an issue, or remove |
| Marketing tone | Hides the facts | Plain, direct instructions |

## Verification

```bash
git clone . /tmp/docs-check && cd /tmp/docs-check
# Follow the README literally, step by step.
php artisan route:list --except-vendor
npx @redocly/cli lint docs/api/openapi.yaml
grep -rnE '(sk_live|AKIA|password\s*=\s*[^<])' README.md docs
```

- [ ] Every command was run
- [ ] Every env key exists in `.env.example`
- [ ] Every endpoint matches `route:list`
- [ ] OpenAPI lints, and matches resources
- [ ] Relative links resolve
- [ ] No secrets or real personal data

## Additional Resources

- [templates.md](references/templates.md): README, ADR, runbook, changelog and upgrade note templates, plus the Laravel-to-OpenAPI mapping
- [version-matrix.md](references/version-matrix.md): versions and skeleton differences
