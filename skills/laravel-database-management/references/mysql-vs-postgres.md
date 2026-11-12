# MySQL vs PostgreSQL in Laravel

Differences that make portable-looking code fail in one engine.

| Topic | MySQL (InnoDB) | PostgreSQL |
| --- | --- | --- |
| String comparison | Case-insensitive under default collations | Case-sensitive |
| `LIKE` | Follows collation | Case-sensitive; `ILIKE` for insensitive |
| Foreign key index | Created automatically | **Not** created, add it |
| Error inside a transaction | Statement fails, transaction continues | Transaction aborted until rollback or savepoint |
| `GROUP BY` | Strict with `ONLY_FULL_GROUP_BY` (Laravel `strict => true`) | Always strict |
| Boolean | `tinyint(1)` | Real `boolean`; `where('active', 1)` can fail |
| JSON | `json` | `json`, and `jsonb` (indexable with GIN) |
| Identifier quoting | Backticks | Double quotes; unquoted names fold to lowercase |
| Sequences | `AUTO_INCREMENT` tracks inserts | Explicit-ID inserts leave the sequence behind |
| `upsert` conflict target | Ignores `uniqueBy`, uses all unique indexes | Uses the given columns, which need a unique index |
| Index on expressions | Functional indexes (8.0.13+) | Expression and partial indexes |
| Concurrent index | `ALGORITHM=INPLACE, LOCK=NONE` | `CREATE INDEX CONCURRENTLY` |
| Empty-string coercion | Strict mode rejects bad values | Always rejects |
| Random order | `RAND()` | `RANDOM()`; use `inRandomOrder()` |

## Portable Case-Insensitive Search

```php
<?php

use App\Models\User;

$users = User::query()
    ->whereRaw('LOWER(email) = ?', [mb_strtolower($email)])
    ->first();
```

On Laravel 11+, `whereLike('name', "%{$term}%", caseSensitive: false)` hides the difference.

For fast lookups on PostgreSQL, use an expression index or `citext`:

```php
use Illuminate\Support\Facades\DB;

DB::statement('CREATE UNIQUE INDEX users_email_lower_idx ON users (LOWER(email))');
```

## PostgreSQL: Aborted Transactions

```php
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\DB;

DB::transaction(function () use ($team, $data) {
    try {
        // A nested transaction becomes a savepoint, so the outer one survives.
        DB::transaction(fn () => $team->invoices()->create($data));
    } catch (UniqueConstraintViolationException) {
        // Handle the duplicate; the outer transaction remains usable.
    }

    $team->touch();
});
```

Without the nested transaction, the next query fails with `current transaction is aborted`.

## PostgreSQL: Resetting a Sequence

After importing rows with explicit IDs:

```php
use Illuminate\Support\Facades\DB;

DB::statement("SELECT setval(pg_get_serial_sequence('orders', 'id'), (SELECT MAX(id) FROM orders))");
```

The symptom is `duplicate key value violates unique constraint "orders_pkey"` on normal inserts.

## JSON Columns

```php
use App\Models\Product;

Product::where('attributes->color', 'red')->get();
Product::whereJsonContains('attributes->tags', 'sale')->get();
```

Index a queried key:

```php
use Illuminate\Database\Schema\Blueprint;

// MySQL: index a stored generated column.
$table->string('color')->storedAs("attributes->>'$.color'")->index();
```

```php
use Illuminate\Support\Facades\DB;

// PostgreSQL: GIN index on jsonb.
DB::statement('CREATE INDEX products_attributes_gin ON products USING GIN (attributes)');
```

## MySQL Specifics

- Use `utf8mb4` so emoji and all of Unicode store correctly. Laravel defaults to this.
- `Specified key was too long` on old MySQL or MariaDB: set `Schema::defaultStringLength(191)` in `AppServiceProvider::boot()`, or upgrade.
- MariaDB is not MySQL: JSON is an alias of `LONGTEXT`, and optimizer behaviour differs. Laravel has a separate `mariadb` driver since 11.

## Tests

SQLite in memory is fast, but does not catch any of the above. Run at least CI against the production engine. See `laravel-testing`.
