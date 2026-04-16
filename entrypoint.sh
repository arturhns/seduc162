#!/bin/sh
set -e

if [ "$DATABASE_HOST" = "mysql" ]; then
  echo "Aguardando MySQL..."
  while ! nc -z "$DATABASE_HOST" "$DATABASE_PORT"; do
    sleep 1
  done
  echo "MySQL pronto."
fi

exec "$@"
