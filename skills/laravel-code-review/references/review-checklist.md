# Review Checklist

Use selectively: pick the sections that match the diff.

## Correctness

- [ ] Null paths handled for optional relations and lookups
- [ ] Off-by-one in dates: `endOfDay()`, inclusive ranges, timezone conversion
- [ ] Money uses integers or decimals, with stated rounding
- [ ] Enum `match` covers every case
- [ ] `$request->boolean()` or `integer()` used rather than truthy strings
- [ ] `update()` return values and `first()` nulls are checked
- [ ] Soft-deleted rows are excluded or included deliberately
- [ ] Collection vs query method: `->where()` on a loaded collection compares loosely

## Concurrency

- [ ] Read-modify-write uses atomic updates or `lockForUpdate()`
- [ ] Uniqueness is enforced by an index
- [ ] Locks are taken in a consistent order
- [ ] Transactions contain no external I/O
- [ ] `Cache::lock()` is released in `finally`

## Authorization and Tenancy

- [ ] Each new route has authentication where needed
- [ ] Each action has authorization
- [ ] Tenant filter survives `orWhere`
- [ ] Global scopes aren't bypassed by `withoutGlobalScopes()` without need
- [ ] Route-model binding is scoped for nested resources
- [ ] Cache and file paths include the tenant

## House Rules

- [ ] Logic that now exists twice was moved to a service class
- [ ] Each form `store` and `update` uses a form request, not inline `validate()`
- [ ] No migration, seeder, command or test setup drops, truncates or resets existing data
- [ ] Fixed option lists (gender, religion, NRIC type, status) are enums, not new lookup tables
- [ ] Repeated markup uses a Blade component; no copy-pasted buttons, tables or form fields

## Validation

- [ ] Only validated data reaches writes
- [ ] Array items have rules (`items.*.sku`)
- [ ] Upload type and size are limited
- [ ] Updates use `Rule::unique()->ignore($model)`
- [ ] `sort` and `filter` inputs are allow-listed

## Database

- [ ] Migration is reversible, or says why not
- [ ] Destructive changes are split across releases
- [ ] New columns have the right nullability and default
- [ ] Foreign keys have explicit delete behaviour
- [ ] Indexes match new queries
- [ ] Data migration is batched and idempotent
- [ ] Factories and seeders are updated

## Performance

- [ ] Lists are paginated
- [ ] Relations used in loops are eager loaded
- [ ] `withCount` replaces loading to count
- [ ] Hot paths don't add synchronous external calls
- [ ] New cache has an invalidation plan and bounded keys
- [ ] New scheduled work has a time and overlap policy

## Queues

- [ ] Handler is idempotent
- [ ] `tries`, `backoff`, `timeout` are explicit for risky jobs
- [ ] The timeout chain holds
- [ ] Dispatch happens after commit
- [ ] Payload is small and contains no secrets in plain text
- [ ] Failure is observable

## Errors and Logging

- [ ] Exceptions aren't swallowed
- [ ] User-facing messages don't leak internals
- [ ] Logs include identifiers, and exclude passwords, tokens and card data
- [ ] External calls set timeouts

## API Compatibility

- [ ] No field removed or retyped in a released version
- [ ] New required input isn't added to a released endpoint
- [ ] Status codes unchanged, or the change is announced
- [ ] Resource output stays an explicit list

## Dependencies and Config

- [ ] New package is maintained, licensed suitably, and really needed
- [ ] `composer.lock` is committed
- [ ] New env keys are in `.env.example`
- [ ] `config:cache` still works, so no closures in config

## Tests

- [ ] Failure paths are covered
- [ ] Authorization has a negative test
- [ ] External services are faked
- [ ] Assertions check results, not only status
- [ ] No `sleep`, `dd`, or `->only()` left behind

## Deployment

- [ ] Old code tolerates the new schema, and vice versa
- [ ] Rollback path exists
- [ ] New queues have workers
- [ ] Required infrastructure and env changes are listed in the PR
- [ ] Feature is behind a flag if rollout needs control
