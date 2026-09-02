#!/bin/sh
# Container startup: wait for the database, then bring the schema up to date.
set -e

if [ "$DB_HOST" != "" ]; then
  echo "Waiting for database at $DB_HOST:${DB_PORT:-3306}..."
  # MySQL accepts TCP connections a few seconds before it is ready to serve, so
  # the application would crash-loop without this gate.
  while ! nc -z "$DB_HOST" "${DB_PORT:-3306}"; do
    sleep 1
  done
  echo "Database is up."
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
