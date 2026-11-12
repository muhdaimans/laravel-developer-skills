---
name: laravel-code-review
description: Use when reviewing a Laravel pull request, branch, diff or recently written code before merge, or when asked to check Laravel code for bugs, regressions, maintainability or readiness to ship.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer. Designed for Claude Code.
---

# Laravel Code Review

Report defects a merge would actually cause, each with a location, a consequence and a fix. Style is the formatter's job.

## When to Use

- Reviewing a PR, branch or uncommitted diff
- "Is this ready to merge?"
- Self-review after finishing a feature

A whole-application security assessment belongs to `laravel-security-audit`. Implementing fixes belongs to the domain skills.

## Inspect the Project First

```bash
php artisan --version
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
git diff origin/main...HEAD
```

Substitute the real base branch. Also read project rules (`CONTRIBUTING.md`, `CLAUDE.md`, `pint.json`, `phpstan.neon`) and the PR description, so you know the intent. Read [version-matrix.md](references/version-matrix.md) to avoid suggesting features the project can't use.

## Workflow

1. **Understand the intent,** then state it in one sentence. If the diff doesn't match it, that's the first finding.
2. **Run the mechanical checks first,** and don't report what they would catch:

   ```bash
   ./vendor/bin/pint --test
   ./vendor/bin/phpstan analyse
   php artisan test --parallel
   ```

3. **Read the risk first:** migrations, auth, payments, queues, then the rest. Use the table below.
4. **Read surrounding code, not only the diff.** A changed method's callers, and any code that should have changed but didn't, are where bugs hide.

   ```bash
   grep -rn 'calculateTotal' app tests
   ```

5. **Verify each finding** by tracing the code path. Only report what you can demonstrate.
6. **Check the tests:** do they fail without the change? Do they cover failure paths?
7. **Report** using the format below. Lead with the verdict.

### Where to Look by File Type

| Changed file | Ask |
| --- | --- |
| `database/migrations/*` | Reversible? Lock on a large table? Compatible with old code during deploy? Indexes for new foreign keys? |
| `routes/*` | Auth middleware? Throttling? Route order? Named? |
| Controllers | Authorized? Uses `validated()`? Business logic leaking in? |
| Form requests | `authorize()` meaningful? Unique rules ignore the current record? Arrays validated with `.*`? |
| Models | New `$fillable` entries safe? `$hidden` for secrets? Casts? Events on bulk updates? |
| Policies | Every method checks ownership? `before()` too broad? |
| Resources | Leaks fields? `whenLoaded()`? |
| Jobs and listeners | Idempotent? Timeouts? `afterCommit`? Serialized payload size? |
| Queries | N+1? Unbounded `get()`? Raw SQL bindings? Missing tenant scope? |
| `config/*`, `.env.example` | New key documented? `env()` only in config? |
| `composer.json` | New dependency justified? Lock file updated? Abandoned package? |
| Tests | Asserts outcomes? Would it fail if the code broke? |
| Blade | `{!! !!}` with user data? `@csrf`? Queries in loops? |

### Laravel Defects That Pass Tests

- A policy method exists but is never called.
- `update()` on a query skips observers that the feature relies on.
- `$request->validated()` omits a field that a later line reads with `$request->input()`, bypassing validation.
- `firstOrCreate()` without a unique index races under load.
- A job dispatched in a transaction runs before commit.
- `Cache::remember()` key lacks the tenant or user, so one customer sees another's data.
- Scheduled task without `onOneServer()` on several servers.
- `sometimes` plus `required` allows `null` on update.
- `whereHas()` inside `orWhere` without grouping escapes a tenant filter:

  ```php
  // Bug: the orWhere escapes team_id, returning other teams' rows.
  Order::where('team_id', $teamId)
      ->where('status', 'open')
      ->orWhere('status', 'pending')
      ->get();

  // Fix: group the alternatives.
  Order::where('team_id', $teamId)
      ->where(fn ($q) => $q->where('status', 'open')->orWhere('status', 'pending'))
      ->get();
  ```

## Severity

| Level | Meaning | Merge? |
| --- | --- | --- |
| **Blocker** | Data loss, security hole, broken production, failed deploy | No |
| **Major** | Bug in a realistic path, serious performance regression, missing authorization test | Fix first |
| **Minor** | Edge case, or maintainability cost, with a clear fix | Author's call |
| **Nit** | Preference | Omit unless asked |

## Report Format

```markdown
## Verdict: Changes requested

Adds invoice payment. The flow is right, but one blocker lets users pay others' invoices.

### Blocker
**`app/Http/Controllers/InvoiceController.php:42` — No ownership check on `pay()`**
Any authenticated user can pay any invoice by ID, because `Gate::authorize()` is missing.
Fix: add `Gate::authorize('pay', $invoice);` and a test for the 403.

### Major
...

### Checked
Migrations reversible, Pint and tests pass (214 tests), no new dependencies.
```

Include a **Checked** section so the reader knows what was covered. If nothing is wrong, say so plainly, and do not invent findings to fill space.

## Version Notes

- Flag only what the locked versions support. Do not suggest `casts()` on Laravel 10, or attributes before 13.
- On 13, flag new references to `VerifyCsrfToken` in favour of `PreventRequestForgery`.
- On 11+ skeletons, flag `$this->authorize()` if the base controller lacks the trait.
- PHP syntax must suit the lowest version allowed by `composer.json`, not the developer's runtime.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Reviewing only the diff | Misses broken callers | Search for usages |
| Commenting on formatting | Noise that hides real issues | Leave to Pint |
| "Consider refactoring" | Not actionable | State the defect and fix |
| Speculative findings | Wastes the author's time | Trace it, or drop it |
| Rewriting in your preferred pattern | Scope creep | Respect project conventions |
| Skipping tests | Untested paths look fine | Read them and run them |
| Reporting 30 items, unranked | The blocker gets lost | Rank by severity |
| Approving because CI passed | CI doesn't check authorization logic | Read risk areas by hand |

Use the longer lists in [review-checklist.md](references/review-checklist.md) for large or high-risk changes.

## Verification

- [ ] Every finding has `file:line`, consequence and fix
- [ ] Every finding was traced in code
- [ ] Tests were run, or you said they weren't
- [ ] Verdict matches the highest severity
- [ ] Coverage is stated in **Checked**

## Additional Resources

- [review-checklist.md](references/review-checklist.md): detailed checklist by concern
- [version-matrix.md](references/version-matrix.md): what the project's versions allow
