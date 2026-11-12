# Query Recipes

## Reading EXPLAIN

### MySQL

| Column | Good | Warning |
| --- | --- | --- |
| `type` | `const`, `eq_ref`, `ref`, `range` | `index` (full index scan), `ALL` (full table scan) |
| `key` | An index name | `NULL` |
| `rows` | Close to the expected result size | Far larger than rows returned |
| `filtered` | Near 100 | Low: many rows read and discarded |
| `Extra` | `Using index` (covering) | `Using filesort`, `Using temporary` on large sets |

### PostgreSQL

| Node | Meaning |
| --- | --- |
| `Index Scan`, `Index Only Scan` | Using an index |
| `Bitmap Heap Scan` | Index gathers many rows, then reads the heap. Normal for medium selectivity |
| `Seq Scan` | Whole table. Fine on small tables or when most rows match |
| `Sort` with `external merge` | Spilled to disk |
| `Nested Loop` with a large outer side | Often a missing inner index |

In `EXPLAIN (ANALYZE, BUFFERS)`, a large gap between estimated and actual rows means stale statistics: run `ANALYZE table_name`. On Postgres, a high `Rows Removed by Filter` means the index is not selective enough.

## Composite Indexes

For one query, order columns as equality first, then range, then sort.

```php
// WHERE team_id = ? AND status = ? AND created_at > ? ORDER BY created_at DESC
$table->index(['team_id', 'status', 'created_at']);
```

- An index on `(a, b, c)` serves `a`, `a, b` and `a, b, c`. It does not serve `b` alone.
- Once a range column appears, later columns help less for filtering.
- A column that matches most rows, such as a boolean, is poor as a lone index, but can be useful inside a composite.
- Sort direction: MySQL 8+ and PostgreSQL support descending indexes, which matter for mixed-direction sorts.
- Foreign keys: MySQL (InnoDB) indexes them automatically. PostgreSQL does not, so add the index yourself.

Partial index on PostgreSQL, ideal for queues of rare states:

```php
use Illuminate\Support\Facades\DB;

DB::statement(
    "CREATE INDEX orders_pending_idx ON orders (created_at) WHERE status = 'pending'"
);
```

## Latest Row per Group

Avoid loading all children to pick one.

```php
use Illuminate\Database\Eloquent\Relations\HasOne;

public function latestOrder(): HasOne
{
    return $this->hasOne(Order::class)->latestOfMany();
}
```

```php
$customers = Customer::with('latestOrder')->paginate();
```

## Sort by a Related Column

```php
use App\Models\Customer;
use App\Models\Order;

Customer::query()
    ->orderByDesc(
        Order::select('created_at')
            ->whereColumn('orders.customer_id', 'customers.id')
            ->latest()
            ->limit(1)
    )
    ->paginate();
```

## Atomic Counters

Read-modify-write loses updates under concurrency.

```php
// Bad: two requests read 10, both write 11.
$product->stock = $product->stock - 1;
$product->save();

// Good: the database applies the change, guarded against overselling.
$updated = Product::whereKey($id)
    ->where('stock', '>', 0)
    ->decrement('stock');

if ($updated === 0) {
    throw new OutOfStockException();
}
```

## Bulk Writes

```php
Product::upsert(
    $rows,
    uniqueBy: ['sku'],
    update: ['price_cents', 'stock'],
);
```

`upsert()` bypasses model events and needs a real unique index. MySQL and MariaDB ignore the `uniqueBy` value, using all of the table's unique indexes, but Laravel 13 still requires it to be non-empty. Named arguments shown here are not covered by Laravel's backward-compatibility promise, so use positional arguments if the project avoids them.

Batch inserts in chunks to respect packet size and placeholder limits:

```php
collect($rows)->chunk(1000)->each(
    fn ($chunk) => Product::insert($chunk->all())
);
```

## Relationship Existence

```php
Post::whereHas('comments', fn ($q) => $q->where('approved', true))->get();
Post::whereRelation('comments', 'approved', true)->get();
Post::withWhereHas('comments', fn ($q) => $q->where('approved', true))->get();
```

The third form also eager-loads only the matching comments, so the condition is not written twice.

## Full-Text Search

```php
$table->fullText(['title', 'body']);
```

```php
Post::whereFullText(['title', 'body'], $term)->paginate();
```

Works on MySQL and PostgreSQL. For typo tolerance or facets, Laravel Scout with a search engine is the next step.

## Slow-Query Alerts

```php
use Illuminate\Database\Connection;
use Illuminate\Database\Events\QueryExecuted;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

DB::whenQueryingForLongerThan(500, function (Connection $connection, QueryExecuted $event) {
    Log::warning('Slow query cycle', [
        'connection' => $connection->getName(),
        'sql' => $event->sql,
        'ms' => $event->time,
    ]);
});
```

The threshold applies to the cumulative query time of a request, and the handler fires once per request. Do not log bindings if they can contain personal data.
