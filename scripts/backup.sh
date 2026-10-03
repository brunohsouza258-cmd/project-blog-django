#!/bin/sh
# Backup automático do banco: roda no container "backup" (docker-compose.yml).
#
# Uma vez por dia:
#   1. Copia o banco inteiro para /backups/blog-AAAA-MM-DD_HHMM.dump
#      (formato "custom" do pg_dump: já vem comprimido).
#   2. Apaga cópias com mais de BACKUP_KEEP_DAYS dias (padrão: 14).
#   3. Apaga do cache os contadores de tentativas que já expiraram
#      (prometido na Política de Privacidade).
#
# Restaurar uma cópia: veja a seção "Backups" do README.

set -u

KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
export PGPASSWORD="$POSTGRES_PASSWORD"

log() {
  echo "[backup $(date '+%Y-%m-%d %H:%M:%S')] $*"
}

while true; do
  file="/backups/blog-$(date '+%Y-%m-%d_%H%M').dump"

  # Grava num arquivo temporário e só renomeia se deu certo: um backup pela
  # metade nunca fica com cara de backup válido.
  if pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
       -d "$POSTGRES_DB" -Fc -f "$file.tmp" && [ -s "$file.tmp" ]; then
    mv "$file.tmp" "$file"
    log "ok: $file ($(du -h "$file" | cut -f1))"
  else
    rm -f "$file.tmp"
    log "ERRO: o backup falhou; tento de novo no próximo ciclo"
  fi

  find /backups -name 'blog-*.dump' -mtime "+$KEEP_DAYS" -print -delete \
    | sed 's/^/[backup] apagado (antigo): /'

  psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" -q -c "DELETE FROM django_cache WHERE expires < now();" \
    && log "contadores de tentativas expirados apagados"

  sleep "$INTERVAL"
done
