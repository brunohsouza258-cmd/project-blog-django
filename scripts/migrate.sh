#!/bin/sh

set -e

echo "Executando migrate.sh"
python manage.py migrate --noinput
# Tabela usada pelo cache (limites de tentativas por IP).
python manage.py createcachetable
