#!/bin/sh

set -e

echo "Executando collectstatic.sh"
python manage.py collectstatic --noinput
