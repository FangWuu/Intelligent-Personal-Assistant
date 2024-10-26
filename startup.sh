#!/bin/bash
python manage.py migrate  # run migrations
gunicorn --bind=0.0.0.0 --timeout 600 Main.Backend.wsgi:application
