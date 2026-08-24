def roles_usuario(request):
    """Banderas de permisos para el menú e interfaz."""
    if not request.user.is_authenticated:
        return {
            'es_admin': False,
            'es_supervisor_o_gerente': False,
            'es_cajero': False,
            'puede_vender': False,
            'puede_editar_stock': False,
            'puede_ver_caja': False,
            'puede_ver_reportes': False,
        }

    # Grupos en minúsculas para evitar errores tipográficos
    grupos = set(request.user.groups.values_list('name', flat=True))
    grupos_lower = {g.lower() for g in grupos}

    is_super = request.user.is_superuser
    is_admin = is_super or 'administrador' in grupos_lower or 'admin' in grupos_lower
    is_supervisor_o_gerente = 'supervisor' in grupos_lower or 'superv' in grupos_lower or 'gerente' in grupos_lower
    is_cajero = 'cajero' in grupos_lower or 'vendedor' in grupos_lower

    # Todos los roles (Cajero, Supervisor, Admin) pueden vender, ver caja y ver reportes
    puede_vender = is_admin or is_supervisor_o_gerente or is_cajero
    puede_ver_caja = is_admin or is_supervisor_o_gerente or is_cajero
    puede_ver_reportes = is_admin or is_supervisor_o_gerente or is_cajero

    # SOLO Supervisor, Gerente y Admin pueden EDITAR productos y stock
    puede_editar_stock = is_admin or is_supervisor_o_gerente

    return {
        'es_admin': is_admin,
        'es_supervisor_o_gerente': is_supervisor_o_gerente,
        'es_cajero': is_cajero,
        'puede_vender': puede_vender,
        'puede_editar_stock': puede_editar_stock,
        'puede_ver_caja': puede_ver_caja,
        'puede_ver_reportes': puede_ver_reportes,
    }