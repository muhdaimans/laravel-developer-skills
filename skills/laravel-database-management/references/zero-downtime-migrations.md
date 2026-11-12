# Zero-Downtime Migrations

During a rolling deploy, old and new code run against the same schema. Each migration must work with both.

## Expand and Contract

1. **Expand:** add the new structure. Old code ignores it.
2. **Migrate:** new code writes to both, a job backfills.
3. **Switch:** new code reads the new structure.
4. **Contract:** a later release removes the old structure.

## Recipes

### Rename a column

Never use `renameColumn` on a live table: old code breaks immediately.

| Release | Change |
| --- | --- |
| 1 | Add `full_name` as nullable. Write to both. Backfill |
| 2 | Read `full_name`. Keep writing both |
| 3 | Stop writing `name` |
| 4 | Drop `name` |

### Add a required column

| Release | Change |
| --- | --- |
| 1 | Add nullable, or with a constant default. Code always writes it |
| 2 | Backfill rows in batches |
| 3 | Add `NOT NULL` |

PostgreSQL 11+ adds a column with a constant default without rewriting the table. MySQL 8.0 can add it with `ALGORITHM=INSTANT` in most cases. Both still need a brief metadata lock.

On PostgreSQL, avoid the full scan of `SET NOT NULL`:

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public $withinTransaction = false;

    public function up(): void
    {
        DB::statement('ALTER TABLE orders ADD CONSTRAINT orders_region_nn CHECK (region IS NOT NULL) NOT VALID');
        DB::statement('ALTER TABLE orders VALIDATE CONSTRAINT orders_region_nn');
        DB::statement('ALTER TABLE orders ALTER COLUMN region SET NOT NULL');
        DB::statement('ALTER TABLE orders DROP CONSTRAINT orders_region_nn');
    }

    public function down(): void
    {
        DB::statement('ALTER TABLE orders ALTER COLUMN region DROP NOT NULL');
    }
};
```

### Drop a column

1. Remove all code references and deploy.
2. If the model uses `$fillable` or explicit columns, confirm nothing selects it.
3. Drop in a later release.

### Add an index on a large table

PostgreSQL. `CONCURRENTLY` can't run in a transaction:

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public $withinTransaction = false;

    public function up(): void
    {
        DB::statement('CREATE INDEX CONCURRENTLY IF NOT EXISTS orders_status_idx ON orders (status)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX CONCURRENTLY IF EXISTS orders_status_idx');
    }
};
```

A failed concurrent build leaves an `INVALID` index. Drop it and retry.

MySQL 8 InnoDB:

```php
use Illuminate\Support\Facades\DB;

DB::statement('ALTER TABLE orders ADD INDEX orders_status_idx (status), ALGORITHM=INPLACE, LOCK=NONE');
```

Specifying `ALGORITHM` and `LOCK` makes MySQL fail fast instead of quietly taking a stronger lock. Very large tables, or changes MySQL cannot do online, call for `gh-ost` or `pt-online-schema-change`.

### Add a foreign key on a large table

PostgreSQL. Add unvalidated, then validate separately:

```php
use Illuminate\Support\Facades\DB;

DB::statement('ALTER TABLE orders ADD CONSTRAINT orders_team_fk FOREIGN KEY (team_id) REFERENCES teams (id) NOT VALID');
DB::statement('ALTER TABLE orders VALIDATE CONSTRAINT orders_team_fk');
```

### Change a column type

Treat as a rename: add a new column, dual-write, backfill, switch, drop. Widening `varchar` is generally cheap. Changing `int` to `bigint` rewrites the table.

## Batched Backfill

Run from a queued job or command, not a migration. Migrations block the deploy, and can time out.

```php
<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class BackfillOrderRegion extends Command
{
    protected $signature = 'orders:backfill-region {--batch=1000} {--sleep=100}';

    protected $description = 'Backfill orders.region in small batches';

    public function handle(): int
    {
        DB::table('orders')
            ->whereNull('region')
            ->chunkById((int) $this->option('batch'), function ($orders) {
                foreach ($orders as $order) {
                    DB::table('orders')
                        ->where('id', $order->id)
                        ->update(['region' => $this->regionFor($order)]);
                }

                usleep((int) $this->option('sleep') * 1000); // Lets replicas keep up.
            });

        $this->info('Remaining: '.DB::table('orders')->whereNull('region')->count());

        return self::SUCCESS;
    }

    private function regionFor(object $order): string
    {
        return strtoupper(substr($order->country, 0, 2));
    }
}
```

Make it resumable and idempotent. Watch replica lag while it runs. Use a single set-based `UPDATE` per chunk where the value is computable in SQL.

## Lock Timeouts

A blocked `ALTER` queues all later queries on that table behind it. Fail fast rather than cause an outage.

```php
use Illuminate\Support\Facades\DB;

// PostgreSQL
DB::statement("SET lock_timeout = '3s'");

// MySQL
DB::statement('SET SESSION lock_wait_timeout = 3');
```

Check for long-running transactions before you start, and retry off-peak on timeout.

## Pre-flight Checklist

- [ ] SQL reviewed with `migrate --pretend`
- [ ] Tested on a production-sized copy
- [ ] Old code works after this migration
- [ ] New code works before this migration, if deploying code first
- [ ] Recent verified backup
- [ ] Lock timeout set for busy tables
- [ ] Replica lag monitored
- [ ] `php artisan migrate --force --isolated` used, so concurrent deploys can't race
- [ ] Rollback is defined: code rollback must not need the schema rollback
