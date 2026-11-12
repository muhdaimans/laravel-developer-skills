---
name: laravel-eloquent-optimization
description: Use when Laravel pages or endpoints are slow, query counts are high, or Eloquent code needs optimizing, including N+1 problems, eager loading, LazyLoadingViolationException, missing indexes, EXPLAIN plans, memory exhaustion on large datasets, chunking, and slow pagination.
license: MIT
compatibility: Laravel 10 and newer, PHP 8.2 and newer, MySQL or PostgreSQL. Designed for Claude Code.
---

# Laravel Eloquent Optimization

Measure, fix the worst query, measure again. Never optimize from a hunch.

## When to Use

- A page, endpoint or job is slow
- Query counts grow with the number of rows
- `Allowed memory size exhausted` on a large dataset
- Reviewing Eloquent code for performance

Hand off index migrations to `laravel-database-management`, and missing-data bugs to `laravel-debugging`.

## Inspect the Project First

```bash
php artisan --version
php artisan db:show --counts
php artisan db:table orders
php artisan model:show Order
composer show --locked | grep -E 'telescope|debugbar|pulse|nightwatch'
```

Establish the database engine and version, row counts on the involved tables, existing indexes, and any installed profiler. See [version-matrix.md](references/version-matrix.md) for feature availability.

## Workflow

### 1. Capture a baseline

Add a temporary logger locally:

```php
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

DB::listen(function ($query) {
    Log::debug($query->time.'ms '.$query->toRawSql());
});
```

`$query->toRawSql()` on `QueryExecuted` needs Laravel 11+; on 10 log `$query->sql` and `$query->bindings`. Or use Telescope or Debugbar if installed. Record total query count, duplicate shapes, the slowest query and total DB time.

### 2. Classify

| Symptom | Cause | Go to |
| --- | --- | --- |
| Same query shape repeated N times | N+1 | Step 3 |
| One query takes most of the time | Missing or unusable index, or too many rows | Step 4 |
| Few fast queries, high memory or slow response | Too many columns or models hydrated | Step 5 |
| Slow deep pagination | `OFFSET` cost | Step 6 |
| Slow `count(*)` for a list | Length-aware pagination | Step 6 |
| Identical expensive read on every request | Missing cache | Step 7 |

### 3. Fix N+1

```php
// Eager load only what the view or resource actually uses.
$orders = Order::query()
    ->with(['customer:id,name', 'items.product:id,sku,name'])
    ->withCount('items')
    ->withSum('items as total_cents', 'line_total_cents')
    ->latest()
    ->paginate(25);
```

When constraining columns, include the key used to match: `customer:id,name` needs `id`, and the `customer_id` foreign key on `orders` must remain selected.

Use the aggregate helpers instead of loading a relation to count it:

```php
// Bad: loads every comment to count them.
$post->comments->count();

// Good: on one model.
$post->comments()->count();

// Good: on a list, avoids N+1.
Post::withCount('comments')->paginate();
```

Check existence with `exists()`, or `withExists('comments')`, not `count() > 0`.

### 4. Fix a slow query

```php
$plan = Order::query()->where('status', 'paid')->latest()->explain();
dump($plan->all());
```

Then read the plan using [query-recipes.md](references/query-recipes.md). Run `EXPLAIN ANALYZE` directly in the database client when you need actual timings; it executes the statement, so only use it on `SELECT`s.

Common index-defeating patterns:

```php
// Function on column: index unusable.
Order::whereYear('created_at', 2026)->get();

// Range: index usable.
Order::whereBetween('created_at', [
    '2026-01-01 00:00:00',
    '2026-12-31 23:59:59',
])->get();
```

A leading wildcard (`LIKE '%term'`) can't use a B-tree index: use full-text search. `whereRelation()` and `whereHas()` generate `EXISTS` subqueries; on large tables compare with a join.

### 5. Hydrate less

Select only needed columns. For a report, skip models entirely:

```php
use Illuminate\Support\Facades\DB;

$totals = DB::table('orders')
    ->selectRaw('customer_id, SUM(total_cents) AS revenue')
    ->where('status', 'paid')
    ->groupBy('customer_id')
    ->orderByDesc('revenue')
    ->limit(100)
    ->get();
```

Process large sets by streaming:

| Method | Memory | Use for |
| --- | --- | --- |
| `chunkById(1000, $fn)` | Bounded | Batch updates, safest default |
| `lazyById(1000)` | Bounded | Same, with a collection-style pipeline |
| `cursor()` | Low for models, but buffers the result set on MySQL unless unbuffered, and cannot eager load | Read-only streaming |
| `chunk(1000, $fn)` | Bounded | Avoid if the callback changes the filtered column: rows get skipped |

For a bulk change, prefer a single statement:

```php
Order::where('status', 'pending')
    ->where('created_at', '<', now()->subDays(30))
    ->update(['status' => 'abandoned']);
```

This does not fire model events, so confirm no observer depends on them. Eloquent still sets `updated_at`; `DB::table()` does not.

### 6. Fix pagination

| Method | Query cost | Use when |
| --- | --- | --- |
| `paginate()` | `COUNT` + `OFFSET` | Admin tables needing page numbers |
| `simplePaginate()` | `OFFSET` only | Next/previous, no count |
| `cursorPaginate()` | Keyset, stable at any depth | Feeds, infinite scroll, APIs |

`cursorPaginate()` needs a unique, indexed ordering such as `->orderByDesc('id')`, or `orderByDesc('created_at')->orderByDesc('id')`.

### 7. Cache only after the query is sound

```php
$stats = Cache::remember(
    "dashboard:stats:{$team->id}",
    now()->addMinutes(5),
    fn () => $this->calculateStats($team),
);
```

Include tenant or user in the key. Plan invalidation before adding the cache. Cache arrays, not models: on Laravel 13, cached objects also need a `serializable_classes` allow-list.

### 8. Prevent regressions

Add a query-count test as shown in [Verification](#verification).

## Version Notes

- `Model::automaticallyEagerLoadRelationships()` on 12.x can auto-resolve N+1 globally. Treat it as a mitigation, because explicit `with()` still documents intent and permits column selection.
- `withWhereHas()` constrains and eager-loads together, avoiding a duplicated closure.
- `whereVectorSimilarTo()` on Laravel 13 needs PostgreSQL with `pgvector`.
- `Model::preventLazyLoading()` works on every supported version.

## Common Mistakes

| Mistake | Why it bites | Fix |
| --- | --- | --- |
| Adding an index without reading the plan | May go unused, and slows writes | `EXPLAIN` first, and afterwards |
| Indexing every column | Write cost, planner confusion | Composite index shaped to the query |
| Testing on 50 rows | Planner picks a scan, or hides N+1 scale | Seed realistic volume |
| Eager loading everything "to be safe" | Trades N+1 for overfetch | Load what this response uses |
| `->get()->count()`, `->get()->first()` | Fetches all rows to use one | `count()`, `first()` |
| `->get()->filter(...)` for a condition SQL can do | Filters in PHP | `where()` |
| Accessor that runs a query | Hidden N+1 per row | Eager load, compute from loaded data |
| `$with` on a model | Every query pays forever | Explicit `with()` at call sites |
| Caching a slow query to avoid fixing it | Cold starts and stampedes remain | Fix the query first |
| Missing `withCount` in a loop inside an API resource | Query per resource | `whenCounted()` plus `withCount()` |

## Verification

```php
it('lists orders with a constant query count', function () {
    Order::factory()->count(30)->hasItems(3)->create();

    $this->expectsDatabaseQueryCount(5);

    $this->actingAs(User::factory()->create())
        ->getJson('/api/orders')
        ->assertOk();
});
```

Set the number from the measured request, and include auth queries.

```bash
php artisan test --filter='constant query count'
```

- [ ] Before and after numbers recorded (queries, ms, MB)
- [ ] New index appears in the `EXPLAIN` output
- [ ] Temporary `DB::listen` removed
- [ ] `Model::preventLazyLoading()` is on in non-production

## Additional Resources

- [query-recipes.md](references/query-recipes.md): reading EXPLAIN on MySQL and PostgreSQL, composite index rules, latest-per-group, and race-free counters
- [version-matrix.md](references/version-matrix.md): version gates
