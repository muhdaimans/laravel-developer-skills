---
name: laravel-database-management
description: Use when designing schemas or writing Laravel migrations, seeders and factories, or changing production databases on MySQL or PostgreSQL, including indexes, foreign keys, transactions, deadlocks, data backfills, zero-downtime changes, and failed or irreversible migrations.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer, MySQL or PostgreSQL. Designed for Claude Code.
---

# Laravel Database Management

Schema changes are the riskiest routine deployment step. Know the engine, the table size and the lock each statement takes.

## When to Use

- Creating or altering tables
- Designing relationships, keys and constraints
- Backfilling data
- Migrating a large or busy production table
- Handling transactions, locks and deadlocks

Query speed belongs to `laravel-eloquent-optimization`. Release sequencing belongs to `laravel-deployment`.

## Inspect the Project First

```bash
php artisan --version
php artisan db:show
php artisan migrate:status
php artisan db:table users
ls -t database/migrations | head -5
ls database/schema 2>/dev/null
```

Also determine the engine and version (`db:show`), row counts for tables you will alter, and whether the test suite uses the same engine as production. **Never** run a migration against production to learn what it does. Use `php artisan migrate --pretend` for its SQL. See [version-matrix.md](references/version-matrix.md).

## Workflow

1. **Design the change:** types, nullability, default, key, foreign key, indexes, delete behaviour.
2. **Assess risk:**

   | Table size or traffic | Approach |
   | --- | --- |
   | Empty or small | Standard migration |
   | Busy or over about 1M rows | Follow [zero-downtime-migrations.md](references/zero-downtime-migrations.md) |
   | Destructive (drop, rename, narrow type) | Expand and contract across releases |

3. **Generate** with `php artisan make:migration`, one concern per migration.
4. **Write `up()` and `down()`.** If `down()` can't restore data, say so in a comment.
5. **Review SQL:** `php artisan migrate --pretend`.
6. **Test both directions locally:** `migrate`, `migrate:rollback --step=1`, `migrate`.
7. **Update factory and seeders** to match.
8. **Never edit a migration that has run in a shared environment.** Add a new one.

## Core Pattern: A Robust Table

```php
<?php

use App\Models\Team;
use App\Models\User;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('invoices', function (Blueprint $table) {
            $table->id();
            $table->ulid('public_id')->unique();
            $table->foreignIdFor(Team::class)->constrained()->restrictOnDelete();
            $table->foreignIdFor(User::class, 'created_by')->nullable()
                ->constrained('users')->nullOnDelete();
            $table->string('number', 32);
            $table->string('status', 20)->default('draft');
            $table->unsignedBigInteger('total_cents');
            $table->char('currency', 3);
            $table->timestamp('paid_at')->nullable();
            $table->timestamps();
            $table->softDeletes();

            $table->unique(['team_id', 'number']);
            $table->index(['team_id', 'status', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('invoices');
    }
};
```

Decisions worth making deliberately:

| Column need | Choice |
| --- | --- |
| Money | Integer minor units, or `decimal(19, 4)`. Never `float` |
| Status | `string` + PHP enum, avoids an `ALTER` per new state |
| Public identifier | `ulid` alongside `id`, time-ordered so it indexes well |
| Timestamps | Store UTC |
| Flexible attributes | `jsonb` on PostgreSQL, `json` on MySQL. Promote queried keys to real columns |
| Delete behaviour | `restrict` for financial data, `cascade` for owned children, `nullOnDelete` for history |

## Core Pattern: Safe Transactions

```php
use App\Models\Account;
use Illuminate\Support\Facades\DB;

DB::transaction(function () use ($fromId, $toId, $amount) {
    // Lock in a consistent order so two opposite transfers cannot deadlock.
    $accounts = Account::whereIn('id', [$fromId, $toId])
        ->orderBy('id')
        ->lockForUpdate()
        ->get()
        ->keyBy('id');

    $accounts[$fromId]->decrement('balance_cents', $amount);
    $accounts[$toId]->increment('balance_cents', $amount);
}, attempts: 3); // Retries on deadlock.
```

Keep transactions short. No HTTP calls, mail or file uploads inside. To dispatch a job from inside one, use `->afterCommit()`, so the worker cannot run before the row is visible.

## Core Pattern: Handling Unique Races

Do "check then insert" in the database:

```php
use App\Models\Subscription;

$subscription = Subscription::createOrFirst(
    ['team_id' => $team->id, 'plan' => $plan],
    ['started_at' => now()],
);
```

This requires a unique index on those columns. `firstOrCreate()` alone can raise a duplicate-key error under concurrency.

## Version Notes

- Since Laravel 11, `->change()` must restate every modifier you want to keep:

  ```php
  // Without nullable() and default(), both are dropped on Laravel 11+.
  $table->string('name', 100)->nullable()->default('')->change();
  ```

- Laravel 11+ no longer needs `doctrine/dbal` for column changes.
- `make:queue-batches-table` and similar `make:*-table` names are Laravel 11+; on 10 use `queue:batches-table`.
- Laravel 13 throws on `upsert()` with empty `uniqueBy`, and now fails a MySQL `DELETE ... JOIN` with `ORDER BY`/`LIMIT` instead of silently ignoring those clauses.
- Vector columns and indexes on Laravel 13 need PostgreSQL with `pgvector`.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Editing a run migration | Environments diverge silently | New migration |
| Using models in migrations | Model changes break old migrations | `DB::table()`, or inline logic |
| `migrate:fresh` near production | Drops everything | Refuse. Local only |
| Adding `NOT NULL` without default to a populated table | Fails or locks | Add nullable, backfill, then constrain |
| Backfill in one statement on a huge table | Long lock, replica lag | Batched job |
| No index on Postgres foreign keys | Slow joins and cascades | Add explicitly; MySQL does it for you |
| `cascadeOnDelete` on financial records | One delete removes history | `restrictOnDelete` |
| Migration in a test-only engine | SQLite passes, MySQL fails | Test on the production engine |
| `Schema::hasColumn` guards everywhere | Hides drift | Fix the drift |
| Catching a duplicate key inside a Postgres transaction | The transaction is aborted | Nested `DB::transaction()` savepoint, or `insertOrIgnore` |
| Default `seed` in production | Test users in production | Guard, or a separate reference-data seeder |

## Verification

```bash
php artisan migrate --pretend
php artisan migrate
php artisan migrate:rollback --step=1
php artisan migrate
php artisan db:table invoices
php artisan test
```

- [ ] `down()` works, or irreversibility is documented
- [ ] SQL reviewed for the production engine
- [ ] Indexes exist for each new foreign key and query
- [ ] Factory creates valid rows: `Invoice::factory()->create()`
- [ ] Backup confirmed before a destructive change
- [ ] Rollback plan stated for production

## Additional Resources

- [zero-downtime-migrations.md](references/zero-downtime-migrations.md): rename, add `NOT NULL`, big-table indexes, batched backfills
- [mysql-vs-postgres.md](references/mysql-vs-postgres.md): behaviour differences that break portable code
- [version-matrix.md](references/version-matrix.md): version gates
