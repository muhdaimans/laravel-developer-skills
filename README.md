# Laravel Developer Skills

A Claude Code plugin that teaches Claude how to work on Laravel projects the way a careful senior Laravel developer would.

It adds 13 skills. Each skill is a set of instructions that Claude loads by itself when your request matches, for example when you ask it to fix a slow page, write a migration or review a branch.

**In short:** you keep typing normal requests. The plugin changes *how* Claude answers them.

## What Changes When You Install It

The right-hand column is what the skills instruct Claude to do. The left-hand column is what commonly happens when Claude has no project-specific guidance.

| Situation | Without the plugin | With the plugin |
| --- | --- | --- |
| Starting any task | May answer from general Laravel knowledge | Reads `composer.lock`, config and nearby files first, then follows your project's version and conventions |
| A form that saves data | Often validates inline with `$request->validate()` | Creates a form request and passes only `$request->validated()` |
| Logic needed in two places | May copy the code into the second controller | Moves it to a service class in `app/Services` and injects it |
| A fixed list such as gender or status | May add a lookup table, model, seeder and foreign key | Uses a backed enum, a string column and `Rule::enum()` |
| The same button or table markup again | May paste the HTML again | Makes a Blade component and uses `<x-...>` |
| A migration that needs fixing | May suggest `migrate:fresh` | Writes a new migration. Never clears the database unless you ask for that exact command |
| Running tests | May run `php artisan test` straight away | Checks first that tests use a separate database, so `RefreshDatabase` cannot wipe your development data |
| A slow page | May guess at a fix | Measures the queries, fixes the worst one, measures again |
| A bug or 500 error | May patch the symptom with `try/catch` or `?->` | Reproduces it, finds the cause, fixes it at the source, adds a regression test |
| Jobs running twice | May only raise the retry count | Checks the timeout chain (`$timeout` < worker timeout < `retry_after`) and makes the job safe to run twice |
| Changing a big production table | A single migration that may lock the table | A zero-downtime plan in steps across releases |
| Reviewing a branch | A general list of comments | A verdict first, then findings ranked by severity, each with a location, a consequence and a fix |
| Laravel version differences | May suggest a feature your version does not have | Checks the version matrix, for example `casts()` needs Laravel 11 and `$casts` works on 10 |

### One Example

You ask: *"Add a gender field to the applicant form."*

Without the plugin, a common result looks like this:

```php
// A new genders table, a Gender model, a seeder and a gender_id foreign key

public function store(Request $request)
{
    $data = $request->validate(['gender_id' => 'required|exists:genders,id']);
    Applicant::create($data);

    return back();
}
```

```blade
<label>Gender</label>
<select name="gender_id">
    @foreach ($genders as $gender)
        <option value="{{ $gender->id }}">{{ $gender->name }}</option>
    @endforeach
</select>
```

With the plugin, Claude follows the House Rules:

```php
enum Gender: string
{
    use HasOptions;

    case Male = 'male';
    case Female = 'female';
}
```

```php
// StoreApplicantRequest
'gender' => ['required', Rule::enum(Gender::class)],
```

```php
public function store(StoreApplicantRequest $request, ApplicantService $applicants): RedirectResponse
{
    $applicant = $applicants->register($request->validated());

    return to_route('applicants.show', $applicant);
}
```

```blade
<x-form.select name="gender" label="Gender" :options="Gender::options()" />
```

No extra table, no seeder, no join. The validation can be reused and tested, and the dropdown markup is written once. The full version of this example is in [house-rules.md](skills/laravel-best-practices/references/house-rules.md).

## Install

From your terminal:

```bash
claude plugin marketplace add muhdaimans/laravel-developer-skills
```

```bash
claude plugin install laravel-developer-skills@laravel-developer-skills
```

Or inside a Claude Code session:

```text
/plugin marketplace add muhdaimans/laravel-developer-skills
/plugin install laravel-developer-skills@laravel-developer-skills
```

Then restart your session.

<details>
<summary>Try it without installing, or update it</summary>

Try it without installing:

```bash
git clone https://github.com/muhdaimans/laravel-developer-skills.git
```

```bash
claude --plugin-dir ./laravel-developer-skills
```

Update to the newest version, then restart your session:

```bash
claude plugin update laravel-developer-skills@laravel-developer-skills
```

</details>

## How to Use It

There is nothing new to learn. Open your Laravel project in Claude Code and ask for what you need. Claude picks the matching skill.

| You say | Skill that loads |
| --- | --- |
| "Add a registration form for applicants." | `laravel-best-practices` |
| "Where should this logic live?" | `laravel-project-architecture` |
| "This endpoint takes 4 seconds. Find out why and fix it." | `laravel-eloquent-optimization` |
| "Add a paginated orders API with tests." | `laravel-api-development` |
| "Set up Sanctum tokens." or "I get 419 Page Expired." | `laravel-authentication` |
| "Rename `customers.name` on production without downtime." | `laravel-database-management` |
| "Jobs are running twice in Horizon." | `laravel-queue-horizon` |
| "Write tests for the order flow." | `laravel-testing` |
| "I get a 500 error on this page." | `laravel-debugging` |
| "Review this branch before I merge it." | `laravel-code-review` |
| "Audit this app for security issues before launch." | `laravel-security-audit` |
| "Write a production Dockerfile for this project." | `laravel-deployment` |
| "Write the README and API docs." | `laravel-documentation` |

You can also call a skill directly:

```text
/laravel-developer-skills:laravel-code-review
```

## House Rules

Five rules apply to every piece of new code. They rank above your project's existing conventions for new code, and existing code is left alone unless the task touches it.

| # | Rule | In practice |
| --- | --- | --- |
| 1 | Repeated logic goes in a service class | `app/Services/ApplicantService.php`, injected where it is used |
| 2 | Every form has a form request | `StoreApplicantRequest`, then `$request->validated()` |
| 3 | Never clear the database | No `migrate:fresh`, `migrate:refresh`, `migrate:reset`, `db:wipe` or `truncate()` unless you ask for that exact command |
| 4 | Fixed option lists are enums, not tables | `enum Gender: string`, string column, enum cast |
| 5 | Repeated markup is a Blade component | `resources/views/components/`, used as `<x-button>` |

Details and full examples: [house-rules.md](skills/laravel-best-practices/references/house-rules.md).

## All 13 Skills

| Skill | What it covers |
| --- | --- |
| `laravel-best-practices` | Idiomatic controllers, requests, services, enums, Blade components, naming, Pint, and the House Rules |
| `laravel-project-architecture` | Where code lives, Actions, DTOs, modules, safe refactoring |
| `laravel-eloquent-optimization` | N+1, EXPLAIN, indexes, memory, pagination, caching reads |
| `laravel-api-development` | REST endpoints, resources, errors, versioning, rate limits, idempotency |
| `laravel-authentication` | Sanctum, Passport, login flows, policies, 401 and 419 problems |
| `laravel-database-management` | Migrations, zero-downtime changes, transactions, MySQL vs PostgreSQL |
| `laravel-queue-horizon` | Reliable jobs, timeouts, batches, Horizon, queue incidents |
| `laravel-testing` | Pest and PHPUnit, fakes, flaky tests, speed, CI |
| `laravel-debugging` | Root-cause workflow and an error catalog |
| `laravel-code-review` | Severity-ranked PR review with evidence |
| `laravel-security-audit` | Application audit, OWASP mapping, hardening |
| `laravel-deployment` | Docker, servers, release scripts, rollback |
| `laravel-documentation` | README, OpenAPI, ADRs, runbooks, PHPDoc |

## What It Supports

| Area | Versions and tools |
| --- | --- |
| Laravel | 10, 11, 12, 13 |
| PHP | 8.2, 8.3, 8.4, 8.5 |
| Databases | MySQL, MariaDB notes, PostgreSQL |
| Queues | Redis, Horizon |
| Auth | Sanctum, Passport, Fortify, policies |
| Tests | Pest, PHPUnit |
| Delivery | Docker, Nginx, PHP-FPM, Supervisor |

## How It Works

- **Inspect first.** Skills read `composer.lock`, config and neighbouring code before recommending anything.
- **Version-aware.** Each skill includes [the same version matrix](shared/version-matrix.md). When in doubt, the instructions tell Claude to check your installed `vendor/` source.
- **Structure-aware.** An app upgraded to Laravel 12 may still have `app/Http/Kernel.php`. Skills check for the file, not only the version.
- **No forced dependencies.** Examples use the framework. A package is suggested only with a reason, and installation is your decision.
- **Progressive loading.** `SKILL.md` holds the workflow, and `references/` loads only when needed, so the plugin does not fill Claude's context.

## Limits

Skills guide Claude; they do not replace your review. Check migrations, security fixes and deployment changes before running them in production. The version matrix reflects support dates as of 2026-10-30.

## Contributing

Repository layout:

```text
.claude-plugin/    Plugin and marketplace manifests
skills/            One folder per skill: SKILL.md plus references/
shared/            Source of truth for files copied into each skill
scripts/           Validator and sync script
docs/              Maintainer notes, including topic ownership
```

1. Read [skill boundaries](docs/skill-boundaries.md) so that each topic stays in one skill.
2. Edit `shared/version-matrix.md`, never a copy, then run `bash scripts/sync-shared.sh`.
3. Validate:

   ```bash
   python3 scripts/validate-repo.py --lint-php
   ```

   ```bash
   claude plugin validate . --strict
   ```

4. Add a `CHANGELOG.md` entry and bump `version` in `.claude-plugin/plugin.json`. Users only receive an update when that version changes.

Keep claims verifiable. If a statement depends on a Laravel version, confirm it in the official docs or framework source.

## License

[MIT](LICENSE)
