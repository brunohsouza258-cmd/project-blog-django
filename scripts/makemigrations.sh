#!/bin/sh

set -e

echo "Executando makemigrations.sh"
python manage.py makemigrations --noinput
