# apps/usuarios/permisos.py

def es_repartidor(user):
    """True si el usuario es repartidor."""
    return user.is_authenticated and getattr(user, 'rol', '') == 'repartidor'

def es_admin(user):
    """True si el usuario es superuser o tiene rol de administrador."""
    return user.is_authenticated and (
        user.is_superuser or getattr(user, 'rol', '') in ('vendedor', 'gerente')
    )

def puede_vender(user):
    """True si el usuario puede acceder al POS y crear ventas."""
    return user.is_authenticated and getattr(user, 'rol', '') != 'repartidor'

def puede_facturar(user):
    """True si el usuario puede emitir facturas."""
    return user.is_authenticated and getattr(user, 'rol', '') in ('vendedor', 'gerente', 'cajero')

def puede_configurar(user):
    """True si el usuario puede acceder a la configuración del sistema."""
    return user.is_authenticated and (
        user.is_superuser or getattr(user, 'rol', '') in ('vendedor', 'gerente')
    )