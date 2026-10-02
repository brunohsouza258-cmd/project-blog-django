#!/bin/sh

set -e

# DEBUG=1 (desenvolvimento): servidor do Django, que recarrega sozinho ao
# editar o código. DEBUG=0 (produção): gunicorn, feito para aguentar
# visitantes de verdade. "gthread" + threads permite várias respostas do
# chat (que demoram) ao mesmo tempo sem travar o site.
if [ "$DEBUG" = "1" ]; then
  python manage.py runserver 0.0.0.0:8000
else
  exec gunicorn project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --worker-class gthread \
    --threads 4 \
    --timeout 200 \
    --access-logfile -
fi
