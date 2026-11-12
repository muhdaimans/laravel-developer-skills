# Testing Patterns

## Database Traits

| Trait | Mechanism | Use when |
| --- | --- | --- |
| `RefreshDatabase` | Migrates once, wraps each test in a transaction | Default |
| `LazilyRefreshDatabase` | Same, only when a test touches the DB | Mixed suites |
| `DatabaseTransactions` | Transaction only, assumes schema exists | Pre-built test database |
| `DatabaseMigrations` | Full migrate per test | Testing real commits, or Dusk. Slow |
| `DatabaseTruncation` | Truncates between tests | Browser tests, large schemas |

Transactional traits cannot test behaviour that depends on a real commit. `afterCommit` callbacks do run in tests, as Laravel treats the test transaction specially, but multiple connections see separate transactions.

## Factories

```php
<?php

namespace Database\Factories;

use App\Models\Invoice;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/** @extends Factory<Invoice> */
class InvoiceFactory extends Factory
{
    public function definition(): array
    {
        return [
            'user_id' => User::factory(),
            'number' => fake()->unique()->numerify('INV-#####'),
            'total_cents' => fake()->numberBetween(100, 100000),
            'paid_at' => null,
        ];
    }

    public function unpaid(): static
    {
        return $this->state(['paid_at' => null]);
    }

    public function paid(): static
    {
        return $this->state(['paid_at' => now()]);
    }
}
```

- Keep `definition()` minimal and always valid.
- Express meaning through states, so tests read as `Invoice::factory()->paid()`.
- Avoid `fake()->unique()` in huge loops, as it can exhaust and throw.
- `Order::factory()->has(OrderItem::factory()->count(3), 'items')` builds related rows.

## Datasets

```php
<?php

use App\Enums\OrderStatus;

it('validates allowed status transitions', function (OrderStatus $from, OrderStatus $to, bool $allowed) {
    expect($from->canTransitionTo($to))->toBe($allowed);
})->with([
    'pending to paid' => [OrderStatus::Pending, OrderStatus::Paid, true],
    'paid to shipped' => [OrderStatus::Paid, OrderStatus::Shipped, true],
    'shipped to paid' => [OrderStatus::Shipped, OrderStatus::Paid, false],
]);

it('rejects invalid registration payloads', function (array $payload, string $field) {
    $this->postJson('/api/register', $payload)
        ->assertUnprocessable()
        ->assertJsonValidationErrors($field);
})->with([
    'missing email' => [['password' => 'secret-password'], 'email'],
    'bad email' => [['email' => 'nope', 'password' => 'secret-password'], 'email'],
    'short password' => [['email' => 'a@example.com', 'password' => 'x'], 'password'],
]);
```

## HTTP Fakes

```php
<?php

use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;

beforeEach(function () {
    Http::preventStrayRequests();
});

it('retries after a timeout, then reports success', function () {
    Http::fakeSequence('api.example.com/*')
        ->pushFailedConnection()
        ->push(['status' => 'ok'], 200);

    expect(app(WeatherClient::class)->status())->toBe('ok');

    Http::assertSentCount(2);
});

it('sends the signed payload', function () {
    Http::fake(['api.example.com/*' => Http::response(['ok' => true])]);

    app(WeatherClient::class)->send(['a' => 1]);

    Http::assertSent(fn (Request $request) => $request->hasHeader('X-Signature')
        && $request['a'] === 1);
});
```

Exercise timeouts and 5xx responses as well: that's where integrations break.

## Architecture Tests (Pest)

```php
<?php

arch()->preset()->php();
arch()->preset()->laravel();
arch()->preset()->security();

arch('no debugging left behind')
    ->expect(['dd', 'dump', 'ray', 'var_dump'])
    ->not->toBeUsed();

arch('controllers do not use models directly for writes')
    ->expect('App\Http\Controllers')
    ->not->toUse(['Illuminate\Support\Facades\DB']);
```

Presets are opinionated. Add them one at a time, and relax rules that conflict with project conventions.

## Diagnosing Flaky Tests

```bash
for i in $(seq 1 20); do php artisan test --filter=SuspectTest || break; done
./vendor/bin/phpunit --order-by=random
php artisan test --parallel
```

Pest accepts `--order-by=random` too, and `->repeat(20)` on a single test.

| Pattern | Cause | Fix |
| --- | --- | --- |
| Fails near midnight or month end | Real clock | `freezeTime()` |
| Fails only in full suite | Leaked state, static caches | Reset, or find it by bisecting the order |
| Fails only in parallel | Shared file, port, cache key or Redis | Use `ParallelTesting::token()` in names |
| Random order mismatch | Query without `ORDER BY` | Sort, or `assertEqualsCanonicalizing` |
| Occasional uniqueness failure | Faker collision | Sequences or `unique()` |
| Timing-based assertion | Async or `sleep` | Fake the time or the boundary |

## Speeding Up the Suite

1. `php artisan test --profile` to find the slowest tests.
2. Set `BCRYPT_ROUNDS=4` in `phpunit.xml` (the skeleton does this).
3. Run with `--parallel`.
4. Use `RefreshDatabase`, not `DatabaseMigrations`.
5. Run `php artisan schema:dump` so tests load a schema instead of replaying history.
6. Create fewer rows: `count(100)` is rarely necessary.
7. Move pure logic down to unit tests.
8. Set `CACHE_STORE=array`, `SESSION_DRIVER=array`, `QUEUE_CONNECTION=sync` in `phpunit.xml`. On Laravel 10 the cache variable is `CACHE_DRIVER`.

## CI Workflow

Testing on the production engine, with a PHP and Laravel matrix for packages only:

```yaml
name: tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.4
        env:
          MYSQL_DATABASE: testing
          MYSQL_ALLOW_EMPTY_PASSWORD: 'yes'
        ports: ['3306:3306']
        options: >-
          --health-cmd="mysqladmin ping"
          --health-interval=10s
          --health-retries=5
    steps:
      - uses: actions/checkout@v4
      - uses: shivammathur/setup-php@v2
        with:
          php-version: '8.4'
          extensions: pdo_mysql, redis, pcntl
          coverage: none
      - run: composer install --no-interaction --prefer-dist
      - run: cp .env.example .env && php artisan key:generate
      - run: ./vendor/bin/pint --test
      - run: php artisan test --parallel
        env:
          DB_CONNECTION: mysql
          DB_HOST: 127.0.0.1
          DB_DATABASE: testing
          DB_USERNAME: root
          DB_PASSWORD: ''
```

Use the production database image and the PHP version from `composer.json`. Pin third-party actions to a commit SHA if your policy requires it.
