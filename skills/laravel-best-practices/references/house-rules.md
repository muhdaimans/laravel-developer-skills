# House Rules Reference

Examples for the five House Rules in `SKILL.md`. The examples follow one feature, an applicant registration form, so the pieces can be seen working together.

## Contents

1. [Service classes](#1-service-classes)
2. [Form requests](#2-form-requests)
3. [Database safety](#3-database-safety)
4. [Enums instead of lookup tables](#4-enums-instead-of-lookup-tables)
5. [Blade components](#5-blade-components)

## 1. Service Classes

Create or extend a service when the same task is needed a second time: a second controller, an API endpoint beside a web form, an import command, a job.

```bash
ls app/Services                              # extend an existing service first
php artisan make:class Services/ApplicantService   # Laravel 11+
```

```php
<?php

namespace App\Services;

use App\Models\Applicant;
use Illuminate\Support\Facades\DB;

class ApplicantService
{
    public function __construct(
        private DocumentService $documents,
    ) {
    }

    /** @param array<string, mixed> $data Validated input */
    public function register(array $data): Applicant
    {
        return DB::transaction(function () use ($data) {
            $applicant = Applicant::create($data);
            $applicant->addresses()->create($data['address']);

            return $applicant;
        });
    }

    /** @param array<string, mixed> $data Validated input */
    public function update(Applicant $applicant, array $data): Applicant
    {
        $applicant->update($data);

        return $applicant->refresh();
    }
}
```

The web controller, the API controller and the import command all call the same method:

```php
<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreApplicantRequest;
use App\Services\ApplicantService;
use Illuminate\Http\RedirectResponse;

class ApplicantController extends Controller
{
    public function store(StoreApplicantRequest $request, ApplicantService $applicants): RedirectResponse
    {
        $applicant = $applicants->register($request->validated());

        return to_route('applicants.show', $applicant)->with('status', 'Applicant registered.');
    }
}
```

Rules for a service:

| Do | Do not |
| --- | --- |
| Name it by domain: `ApplicantService`, `DocumentService`, `ReportService` | `Helper`, `Utility`, `CommonService` |
| Accept validated arrays, models and plain values | Accept `Request`, or read `request()` and `auth()` inside |
| Return models or values | Return responses, redirects or views |
| Inject it through the constructor or the method signature | Call it statically, or `new` it in a controller |
| Split it when its methods stop sharing a domain | Let one service grow past one topic |

Typical repeated tasks that belong in a service: file upload and storage paths, reference or running numbers, totals and fee calculation, status changes with their side effects, calls to an external API, building the same report from several screens.

A query condition that repeats is an Eloquent scope, not a service. A one-line `Model::create($data)` used once stays in the controller.

## 2. Form Requests

Every `store` and `update` action that takes user input type-hints a form request. Inline `$request->validate()` is not used for forms.

```bash
php artisan make:request StoreApplicantRequest
php artisan make:request UpdateApplicantRequest
```

```php
<?php

namespace App\Http\Requests;

use App\Enums\Gender;
use App\Enums\NricType;
use App\Enums\Religion;
use App\Models\Applicant;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class StoreApplicantRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()->can('create', Applicant::class);
    }

    /** @return array<string, array<int, mixed>> */
    public function rules(): array
    {
        return [
            'name' => ['required', 'string', 'max:255'],
            'nric_type' => ['required', Rule::enum(NricType::class)],
            'nric_number' => ['required', 'string', 'max:20', Rule::unique('applicants', 'nric_number')],
            'gender' => ['required', Rule::enum(Gender::class)],
            'religion' => ['nullable', Rule::enum(Religion::class)],
            'email' => ['required', 'email', 'max:255'],
            'address' => ['required', 'array'],
            'address.line_1' => ['required', 'string', 'max:255'],
            'address.postcode' => ['required', 'digits:5'],
        ];
    }

    /** @return array<string, string> */
    public function attributes(): array
    {
        return [
            'nric_number' => 'NRIC number',
            'address.line_1' => 'address',
        ];
    }
}
```

The update request ignores the current row in unique rules:

```php
<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class UpdateApplicantRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()->can('update', $this->route('applicant'));
    }

    /** @return array<string, array<int, mixed>> */
    public function rules(): array
    {
        return [
            'name' => ['required', 'string', 'max:255'],
            'nric_number' => [
                'required', 'string', 'max:20',
                Rule::unique('applicants', 'nric_number')->ignore($this->route('applicant')),
            ],
        ];
    }
}
```

Notes:

- One request per action. `Store` and `Update` rules drift apart, so do not share one class through `isMethod()` branches.
- `authorize()` returns a real policy check. If authorization is done elsewhere, return `true` rather than deleting the method on Laravel 10.
- Pass only `$request->validated()` or `$request->safe()->only([...])` to the service.
- Normalize input in `prepareForValidation()`, for example stripping dashes from an NRIC number.
- In a Livewire project the equivalent is a form object (`php artisan livewire:form ApplicantForm`). Rules still live in their own class, never inline in the component.
- A search or filter form that only reads data may validate in a request too. It is required for anything that writes.

## 3. Database Safety

The database is never cleared, on any environment, without the user asking for that exact command in the current conversation.

| Need | Forbidden | Safe |
| --- | --- | --- |
| Change a column or table | Edit the old migration, then `migrate:fresh` | New migration, then `php artisan migrate` |
| Undo a migration just written | `migrate:rollback` (whole batch), `migrate:reset`, `migrate:refresh` | `migrate:rollback --step=1`, only if nothing it drops holds data |
| Fix a failed, half-applied migration | `db:wipe` and start again | Read `migrate:status`, repair by hand or with a new migration |
| Add reference data | Seeder with `truncate()` then `insert()` | Seeder with `updateOrCreate()`, run by class name |
| Remove bad rows | `Model::truncate()`, `delete()` with no `where` | A `where`-scoped delete, after showing the count to the user |
| Preview a migration | Run it to see what happens | `php artisan migrate --pretend` |
| Run tests | `php artisan test` on the `.env` database | Separate test database, checked first |

An idempotent seeder:

```php
<?php

namespace Database\Seeders;

use App\Models\Department;
use Illuminate\Database\Seeder;

class DepartmentSeeder extends Seeder
{
    public function run(): void
    {
        foreach (['HR' => 'Human Resources', 'FIN' => 'Finance'] as $code => $name) {
            Department::updateOrCreate(['code' => $code], ['name' => $name]);
        }
    }
}
```

```bash
php artisan db:seed --class=DepartmentSeeder
```

### Checking the Test Database

`RefreshDatabase` runs `migrate:fresh` on the connection the tests use. `DatabaseMigrations` and `DatabaseTruncation` are destructive in the same way.

```bash
grep -E 'DB_(CONNECTION|DATABASE)' .env phpunit.xml .env.testing 2>/dev/null
```

Tests are safe to run when `phpunit.xml` or `.env.testing` sets an active, uncommented `DB_DATABASE` that differs from `.env`, such as `:memory:` or `app_testing`. Skeletons before Laravel 11 ship those lines commented out, which points the tests at the development database. In that case do not run the suite. Report it and propose the fix:

```xml
<env name="DB_CONNECTION" value="sqlite"/>
<env name="DB_DATABASE" value=":memory:"/>
```

### When a Reset Seems Necessary

Stop and ask. Say which tables and roughly how many rows would be lost, and offer a dump first:

```bash
mysqldump --single-transaction app_db > storage/backups/app_db_$(date +%F_%H%M).sql
pg_dump app_db > storage/backups/app_db_$(date +%F_%H%M).sql
```

## 4. Enums Instead of Lookup Tables

| Use an enum when | Use a table when |
| --- | --- |
| The values are fixed and known at code time | Users or admins add and edit values at runtime |
| A new value would need a code change anyway | Each value carries its own data or relations, such as a state with postcodes |
| The list is short: gender, religion, NRIC type, marital status, race, title, status | The list is long or externally maintained: countries, banks, postcodes |

A shared trait builds dropdown options once (House Rule 1 applied to enums):

```php
<?php

namespace App\Enums\Concerns;

trait HasOptions
{
    /** @return array<string, string> value => label */
    public static function options(): array
    {
        return collect(self::cases())
            ->mapWithKeys(fn (self $case) => [$case->value => $case->label()])
            ->all();
    }
}
```

```php
<?php

namespace App\Enums;

use App\Enums\Concerns\HasOptions;

enum NricType: string
{
    use HasOptions;

    case MyKad = 'mykad';
    case MyPr = 'mypr';
    case MyKas = 'mykas';
    case MyTentera = 'mytentera';
    case Passport = 'passport';

    public function label(): string
    {
        return match ($this) {
            self::MyKad => 'MyKad',
            self::MyPr => 'MyPR',
            self::MyKas => 'MyKAS',
            self::MyTentera => 'MyTentera',
            self::Passport => 'Passport',
        };
    }
}
```

```php
<?php

namespace App\Enums;

use App\Enums\Concerns\HasOptions;

enum Gender: string
{
    use HasOptions;

    case Male = 'male';
    case Female = 'female';

    public function label(): string
    {
        return match ($this) {
            self::Male => 'Male',
            self::Female => 'Female',
        };
    }
}
```

`Religion`, `MaritalStatus` and similar follow the same shape. If the app is translated, return `__('enums.gender.'.$this->value)` from `label()`.

The column is a plain string, so a new case needs no migration:

```php
$table->string('nric_type', 20);
$table->string('gender', 20);
$table->string('religion', 20)->nullable();
```

The model casts it, and everything else uses the enum:

```php
<?php

namespace App\Models;

use App\Enums\Gender;
use App\Enums\NricType;
use App\Enums\Religion;
use Illuminate\Database\Eloquent\Model;

class Applicant extends Model
{
    protected $fillable = ['name', 'nric_type', 'nric_number', 'gender', 'religion', 'email'];

    protected function casts(): array // Laravel 11+. Use the $casts property on 10.
    {
        return [
            'nric_type' => NricType::class,
            'gender' => Gender::class,
            'religion' => Religion::class,
        ];
    }
}
```

| Task | Code |
| --- | --- |
| Validate | `Rule::enum(Gender::class)` |
| Dropdown | `<x-form.select name="gender" label="Gender" :options="Gender::options()" />` |
| Display | `{{ $applicant->gender->label() }}`, or `?->label()` when nullable |
| Query | `Applicant::where('gender', Gender::Female)` |
| Compare | `$applicant->nric_type === NricType::Passport` |
| Factory | `'gender' => fake()->randomElement(Gender::cases())` |

Do not:

- Create a `genders` table, model, seeder and `gender_id` foreign key for a fixed list.
- Use a database `ENUM` column type. Adding a value needs an `ALTER TABLE`.
- Store integers (`1`, `2`) as values. Strings stay readable in the database and in exports.
- Rename a case's value after data exists without a data migration.
- Convert an existing lookup table to an enum unless the user asks. That is a data migration, covered by `laravel-database-management`.

## 5. Blade Components

When the same block of markup is written a second time, it becomes a component. Start with the pieces every screen repeats: button, form field, select, table, card, alert, modal, page header.

```bash
ls resources/views/components                # reuse or extend what exists
php artisan make:component form.input --view # anonymous component
```

Starter kits already ship components such as `<x-primary-button>` and `<x-input-label>`. Use those instead of adding parallel ones. Classes below are Tailwind; write the project's own CSS framework.

`resources/views/components/button.blade.php`:

```blade
@props(['variant' => 'primary', 'type' => 'button'])

@php
    $variants = [
        'primary' => 'bg-indigo-600 text-white hover:bg-indigo-500',
        'secondary' => 'bg-white text-gray-700 ring-1 ring-gray-300 hover:bg-gray-50',
        'danger' => 'bg-red-600 text-white hover:bg-red-500',
    ];
@endphp

<button type="{{ $type }}" {{ $attributes->class([
    'inline-flex items-center rounded-md px-4 py-2 text-sm font-semibold disabled:opacity-50',
    $variants[$variant],
]) }}>
    {{ $slot }}
</button>
```

`resources/views/components/form/input.blade.php`, which owns the label, old input and error message:

```blade
@props(['name', 'label', 'type' => 'text', 'value' => null])

<div>
    <label for="{{ $name }}" class="block text-sm font-medium text-gray-700">{{ $label }}</label>
    <input id="{{ $name }}" name="{{ $name }}" type="{{ $type }}" value="{{ old($name, $value) }}"
        {{ $attributes->class([
            'mt-1 block w-full rounded-md border-gray-300 shadow-sm',
            'border-red-500' => $errors->has($name),
        ]) }}>
    @error($name)
        <p class="mt-1 text-sm text-red-600">{{ $message }}</p>
    @enderror
</div>
```

`resources/views/components/form/select.blade.php`, which takes enum options directly:

```blade
@props(['name', 'label', 'options' => [], 'selected' => null, 'placeholder' => 'Please select'])

<div>
    <label for="{{ $name }}" class="block text-sm font-medium text-gray-700">{{ $label }}</label>
    <select id="{{ $name }}" name="{{ $name }}" {{ $attributes->class([
        'mt-1 block w-full rounded-md border-gray-300 shadow-sm',
        'border-red-500' => $errors->has($name),
    ]) }}>
        <option value="">{{ $placeholder }}</option>
        @foreach ($options as $value => $text)
            <option value="{{ $value }}" @selected((string) old($name, $selected) === (string) $value)>{{ $text }}</option>
        @endforeach
    </select>
    @error($name)
        <p class="mt-1 text-sm text-red-600">{{ $message }}</p>
    @enderror
</div>
```

`resources/views/components/table.blade.php`:

```blade
@props(['headers' => []])

<div class="overflow-x-auto rounded-lg ring-1 ring-gray-200">
    <table {{ $attributes->class(['min-w-full divide-y divide-gray-200 text-sm']) }}>
        <thead class="bg-gray-50">
            <tr>
                @foreach ($headers as $header)
                    <th scope="col" class="px-4 py-3 text-left font-semibold text-gray-700">{{ $header }}</th>
                @endforeach
            </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 bg-white">
            {{ $slot }}
        </tbody>
    </table>
</div>
```

A page is then composed from components, with no repeated wrappers:

```blade
<form method="POST" action="{{ route('applicants.store') }}" class="space-y-4">
    @csrf

    <x-form.input name="name" label="Full name" required />
    <x-form.select name="nric_type" label="NRIC type" :options="App\Enums\NricType::options()" required />
    <x-form.input name="nric_number" label="NRIC number" required />
    <x-form.select name="gender" label="Gender" :options="App\Enums\Gender::options()" required />

    <x-button type="submit">Save</x-button>
    <x-button variant="secondary" onclick="history.back()">Cancel</x-button>
</form>

<x-table :headers="['Name', 'NRIC', 'Gender', '']">
    @foreach ($applicants as $applicant)
        <tr>
            <td class="px-4 py-3">{{ $applicant->name }}</td>
            <td class="px-4 py-3">{{ $applicant->nric_number }}</td>
            <td class="px-4 py-3">{{ $applicant->gender->label() }}</td>
            <td class="px-4 py-3 text-right">
                <x-button variant="secondary" onclick="location.href='{{ route('applicants.edit', $applicant) }}'">Edit</x-button>
            </td>
        </tr>
    @endforeach
</x-table>
```

On an edit form, pass the current value: `:value="$applicant->name"` and `:selected="$applicant->gender?->value"`.

Rules for a component:

| Do | Do not |
| --- | --- |
| Declare inputs with `@props` and give defaults | Read controller variables that were not passed in |
| Forward extra attributes with `$attributes->class()` or `->merge()` | Hard-code `id`, `wire:model` or `x-data` that callers need to set |
| Use slots for content, named slots for regions such as `footer` | Pass HTML through a string prop |
| Keep variants in one prop (`variant="danger"`) | Create `button-red`, `button-blue` components |
| Group by folder: `form/`, `layout/`, `table/` | Query the database inside a component view |

Use an anonymous component for markup. Add a class (`php artisan make:component Alert`) only when it needs logic. Page skeletons belong in a layout component (`<x-layouts.app>`), and repeated structures made of several components, such as a filter bar, become components too.

For Inertia with Vue or React, the same rule holds with `.vue` or `.jsx` components. For Livewire, repeated markup is still a Blade component; a Livewire component is for repeated behaviour.
