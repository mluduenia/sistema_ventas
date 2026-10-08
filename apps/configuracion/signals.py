from django.contrib.auth.signals import (
    user_logged_in, user_logged_out, user_login_failed,
)
from django.dispatch import receiver
from .models import AuditLog


def _get_client_ip(request):
    if not request:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@receiver(user_logged_in)
def log_user_logged_in(sender, request, user, **kwargs):
    try:
        AuditLog.objects.create(
            usuario=user,
            rol_snapshot=getattr(user, 'rol', '') or '',
            accion='LOGIN',
            nivel='INFO',
            descripcion=f'Inicio de sesión: {user.username}',
            ip=_get_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''),
        )
    except Exception:
        pass


@receiver(user_logged_out)
def log_user_logged_out(sender, request, user, **kwargs):
    if not user:
        return
    try:
        AuditLog.objects.create(
            usuario=user,
            rol_snapshot=getattr(user, 'rol', '') or '',
            accion='LOGOUT',
            nivel='INFO',
            descripcion=f'Cierre de sesión: {user.username}',
            ip=_get_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''),
        )
    except Exception:
        pass


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    try:
        AuditLog.objects.create(
            usuario=None,
            accion='LOGIN_FAIL',
            nivel='WARNING',
            descripcion=f'Intento de login fallido: {credentials.get("username", "?")}',
            ip=_get_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''),
            metadata={'username_intentado': credentials.get('username', '?')},
        )
    except Exception:
        pass