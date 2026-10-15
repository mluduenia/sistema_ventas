#!/bin/bash
set -e

echo "=========================================="
echo "  Iniciando POS App..."
echo "  $(date)"
echo "=========================================="

# Esperar a PostgreSQL
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
    echo ""
    echo "Esperando a PostgreSQL en $DB_HOST:$DB_PORT..."
    for i in $(seq 1 30); do
        if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
            echo "  ✓ PostgreSQL está listo."
            break
        fi
        echo "  Intento $i/30... esperando 2s"
        sleep 2
    done
fi

# Migraciones
echo ""
echo "Aplicando migraciones..."
python manage.py migrate --noinput

# Archivos estáticos
echo ""
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Superusuario automático
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && \
   [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && \
   [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    echo ""
    echo "Verificando superusuario..."
    python manage.py createsuperuser --noinput 2>/dev/null || echo "  (ya existe)"
fi

# Iniciar servidor
echo ""
echo "=========================================="
echo "  Servidor listo. Ejecutando: $@"
echo "=========================================="
echo ""

exec "$@"