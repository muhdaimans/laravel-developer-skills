# Docker Deployment

Build one immutable image and run it as web, worker and scheduler, changing only the command.

## Dockerfile

Multi-stage, with PHP-FPM on Alpine. Adjust the PHP version and database extensions to the project.

```dockerfile
# syntax=docker/dockerfile:1
FROM php:8.4-fpm-alpine AS base
RUN apk add --no-cache icu-libs libpq libzip \
    && apk add --no-cache --virtual .build-deps $PHPIZE_DEPS icu-dev libpq-dev libzip-dev linux-headers \
    && docker-php-ext-install -j"$(nproc)" bcmath intl opcache pcntl pdo_mysql pdo_pgsql zip \
    && pecl install redis \
    && docker-php-ext-enable redis \
    && apk del .build-deps
COPY docker/php.ini /usr/local/etc/php/conf.d/app.ini
WORKDIR /var/www/html

FROM base AS vendor
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-interaction --no-scripts --no-autoloader --prefer-dist

FROM node:22-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json vite.config.* ./
RUN npm ci
COPY resources ./resources
COPY public ./public
RUN npm run build

FROM vendor AS build
COPY . .
RUN composer dump-autoload --no-dev --optimize --no-scripts \
    && rm /usr/bin/composer

FROM base AS production
COPY --chown=www-data:www-data --from=build /var/www/html ./
COPY --chown=www-data:www-data --from=assets /app/public/build ./public/build
RUN php artisan package:discover --ansi || true
USER www-data
ENTRYPOINT ["sh", "/var/www/html/docker/entrypoint.sh"]
CMD ["php-fpm"]
```

Remove `|| true` once the app can boot without environment values at build time.

If Tailwind reads Blade or PHP files for class names, copy those paths into the `assets` stage too.

## .dockerignore

```text
.git
.env
.env.*
!.env.example
node_modules
vendor
storage/logs/*
storage/framework/cache/*
storage/framework/sessions/*
storage/framework/views/*
bootstrap/cache/*.php
tests
```

## docker/php.ini

```ini
memory_limit = 256M
upload_max_filesize = 20M
post_max_size = 25M
expose_php = Off

opcache.enable = 1
opcache.memory_consumption = 192
opcache.interned_strings_buffer = 16
opcache.max_accelerated_files = 20000
opcache.validate_timestamps = 0
```

`validate_timestamps=0` is right for immutable images, since code changes only with a new container.

## docker/entrypoint.sh

Cache at start, when real environment values exist.

```bash
#!/bin/sh
set -e

php artisan optimize

exec "$@"
```

Migrations do **not** run here. With several replicas they'd race, and a failed migration would crash-loop the fleet.

## compose.yaml

For a single host, or as a local production replica:

```yaml
x-app: &app
  image: registry.example.com/acme/app:${TAG:?set TAG}
  env_file: .env.production
  restart: unless-stopped
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy

services:
  app:
    <<: *app
    volumes:
      - public:/var/www/html/public
  web:
    image: nginx:1.28-alpine
    restart: unless-stopped
    ports: ['80:80']
    volumes:
      - ./docker/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - public:/var/www/html/public:ro
    depends_on: [app]
  horizon:
    <<: *app
    command: ['php', 'artisan', 'horizon']
    stop_grace_period: 1h
  scheduler:
    <<: *app
    command: ['php', 'artisan', 'schedule:work']
  migrate:
    <<: *app
    command: ['php', 'artisan', 'migrate', '--force', '--isolated']
    restart: 'no'
    profiles: ['tools']
  db:
    image: mysql:8.4
    environment:
      MYSQL_DATABASE: app
      MYSQL_USER: app
      MYSQL_PASSWORD: ${DB_PASSWORD:?set DB_PASSWORD}
      MYSQL_RANDOM_ROOT_PASSWORD: 'yes'
    volumes: [db:/var/lib/mysql]
    healthcheck:
      test: ['CMD-SHELL', 'mysqladmin ping -h 127.0.0.1 -u app -p"$$MYSQL_PASSWORD"']
      interval: 10s
      retries: 5
  redis:
    image: redis:7-alpine
    command: ['redis-server', '--appendonly', 'yes']
    volumes: [redis:/data]
    healthcheck:
      test: ['CMD', 'redis-cli', 'ping']
      interval: 10s
      retries: 5

volumes:
  db:
  redis:
  public:
```

The shared `public` volume lets Nginx read built assets, but a named volume keeps its first contents across image upgrades, so it must be refreshed each release. In production prefer baking assets into a dedicated Nginx image, or publishing them to a CDN.

Deploy order:

```bash
docker compose run --rm migrate
docker compose up -d --no-deps app horizon scheduler web
```

## Kubernetes and Similar

| Concern | Approach |
| --- | --- |
| Migration | One-off Job, before rollout |
| Liveness | `/up`, or `php-fpm` ping |
| Readiness | Endpoint that checks dependencies |
| Scheduler | One replica with `schedule:work`, or a `CronJob` running `schedule:run` |
| Workers | Separate Deployment with `terminationGracePeriodSeconds` above the longest job |
| Files | S3-compatible disk, not a pod volume |
| Sessions, cache | Redis |
| Logs | `LOG_CHANNEL=stderr` |

## Image Hygiene

- Pin versions; scan with your registry or `trivy`.
- Run as a non-root user.
- Check that image history has no secrets: `docker history --no-trunc <image>`.
- Tag by commit SHA, and deploy a tag, not `latest`.
- For build-time private Composer access, use BuildKit secrets, never `ARG`.

## FrankenPHP and Octane

Octane keeps the app in memory. Static state and singletons persist between requests, so audit them first, and only adopt it if profiling justifies the change.
