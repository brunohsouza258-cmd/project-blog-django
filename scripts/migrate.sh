#!/bin/sh

set -e

echo "Executando migrate.sh"
python manage.py migrate --noinput
