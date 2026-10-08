from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from .models import EmpresaConfig


def requiere_modulo(modulo):
    """
    Bloquea el acceso a una vista si el módulo no está activo.
    Uso: @requiere_modulo('reparto')
    Módulos válidos: punto_venta, preventa, reparto, deposito, cuenta_corriente, multi_sucursal
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            # Superuser siempre pasa (para poder activar/desactivar sin quedar bloqueado)
            if request.user.is_authenticated and request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            config = EmpresaConfig.objects.first()
            if not config:
                return view_func(request, *args, **kwargs)

            activo = getattr(config, f'modulo_{modulo}', True)

            if not activo:
                messages.error(request, 'Esta funcionalidad no está habilitada en tu sistema.')
                return redirect('core:dashboard')

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator