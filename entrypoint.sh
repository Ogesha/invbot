#!/bin/sh
set -e

echo "Ожидание доступности базы данных..."
while ! nc -z db 5432; do
  sleep 1
done
echo "База данных доступна."

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"