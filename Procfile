web: python manage.py migrate --noinput && python manage.py seed_initial_data && gunicorn turboblog.wsgi:application --bind 0.0.0.0:$PORT
