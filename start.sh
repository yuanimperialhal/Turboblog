#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py seed_initial_data

exec gunicorn turboblog.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
