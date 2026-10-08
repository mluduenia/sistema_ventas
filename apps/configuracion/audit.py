import logging
from .models import AuditLog

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    """Obtiene la IP real, incluso detrás de proxy."""
    if not request:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def registrar_log(
    request,
    accion,
    descripcion,
    modelo='',
    objeto_id=None,
    datos_antes=None,
    datos_despues=None,
    metadata=None,
    nivel='INFO',
):
    """
    Registra una acción en el log de auditoría.

    Uso:
        registrar_log(request, 'VENTA', 'Venta #123 por $5000', modelo='Venta', objeto_id=123)

    Nunca rompe el flujo principal (todo envuelto en try/except).
    """
    try:
        usuario = None
        rol = ''

        if request and hasattr(request, 'user') and request.user.is_authenticated:
            usuario = request.user
            rol = getattr(usuario, 'rol', '') or ''

        ip = _get_client_ip(request)
        user_agent = (request.META.get('HTTP_USER_AGENT', '')[:500] if request else '')

        AuditLog.objects.create(
            usuario=usuario,
            rol_snapshot=rol,
            accion=accion,
            nivel=nivel,
            modelo=modelo or '',
            objeto_id=objeto_id,
            descripcion=descripcion[:2000] if descripcion else '',
            datos_antes=datos_antes,
            datos_despues=datos_despues,
            metadata=metadata,
            ip=ip,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.error(f"[AUDIT] Error registrando log: {e}", exc_info=True)