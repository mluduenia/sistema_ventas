from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.utils import timezone
from apps.ventas.models import Venta, DetalleVenta


@login_required
def dashboard(request):
    """Dashboard con KPIs, accesos rápidos por rol, alertas y últimas ventas paginadas."""

    user = request.user
    rol = 'superadmin' if user.is_superuser else (getattr(user, 'rol', '') or 'vendedor')

    # ============================================================
    # MÓDULOS ACTIVOS
    # ============================================================
    from apps.configuracion.models import EmpresaConfig
    config = EmpresaConfig.objects.first()
    modulos = {
        'punto_venta': config.modulo_punto_venta if config else True,
        'preventa': config.modulo_preventa if config else False,
        'reparto': config.modulo_reparto if config else False,
        'cuenta_corriente': config.modulo_cuenta_corriente if config else True,
        'multi_sucursal': config.modulo_multi_sucursal if config else False,
    }

    # ============================================================
    # 🔽 ALERTAS POR ROL
    # ============================================================
    from apps.alertas.models import Alerta

    alertas = Alerta.objects.filter(
        leida=False,
    ).filter(
        Q(usuario=user) |
        Q(rol=rol) |
        Q(usuario__isnull=True, rol__isnull=True)
    ).order_by('-creada')[:10]

    # ============================================================
    # ACCESOS RÁPIDOS SEGÚN ROL
    # ============================================================
    accesos = []

    if rol == 'repartidor':
        accesos = [
            {'titulo': 'Mis Pedidos', 'url': 'ventas:mis_pedidos', 'icono': 'fa-shipping-fast', 'color': 'warning', 'desc': 'Pedidos asignados'},
            {'titulo': 'Historial', 'url': 'ventas:lista_ventas', 'icono': 'fa-list-alt', 'color': 'primary', 'desc': 'Ver ventas'},
            {'titulo': 'Clientes', 'url': 'ventas:lista_clientes', 'icono': 'fa-users', 'color': 'info', 'desc': 'Gestionar clientes'},
        ]
        if modulos['cuenta_corriente']:
            accesos.append({'titulo': 'Cuentas Corrientes', 'url': 'ventas:cuentas_corrientes', 'icono': 'fa-hand-holding-usd', 'color': 'danger', 'desc': 'Saldos pendientes'})

    elif rol == 'cajero':
        accesos = [
            {'titulo': 'Punto de Venta', 'url': 'ventas:pos', 'icono': 'fa-cash-register', 'color': 'success', 'desc': 'Cobrar y facturar'} if modulos['punto_venta'] else None,
            {'titulo': 'Historial', 'url': 'ventas:lista_ventas', 'icono': 'fa-list-alt', 'color': 'primary', 'desc': 'Consultar ventas'},
            {'titulo': 'Arqueo / Cierre', 'url': 'ventas:cerrar_caja', 'icono': 'fa-calculator', 'color': 'warning', 'desc': 'Cerrar turno'} if modulos['punto_venta'] else None,
            {'titulo': 'Informes X / Z', 'url': 'ventas:lista_informes', 'icono': 'fa-file-invoice', 'color': 'dark', 'desc': 'Historial de cierres'} if modulos['punto_venta'] else None,
            {'titulo': 'Cuentas Corrientes', 'url': 'ventas:cuentas_corrientes', 'icono': 'fa-hand-holding-usd', 'color': 'danger', 'desc': 'Saldos pendientes'} if modulos['cuenta_corriente'] else None,
        ]
        accesos = [a for a in accesos if a]

    elif rol == 'vendedor':
        accesos = [
            {'titulo': 'Punto de Venta', 'url': 'ventas:pos', 'icono': 'fa-cash-register', 'color': 'success', 'desc': 'Cobrar y facturar'} if modulos['punto_venta'] else None,
            {'titulo': 'Historial', 'url': 'ventas:lista_ventas', 'icono': 'fa-list-alt', 'color': 'primary', 'desc': 'Ver ventas'},
            {'titulo': 'Remitos Pendientes', 'url': 'ventas:remitos_pendientes', 'icono': 'fa-file-invoice', 'color': 'warning', 'desc': 'Por facturar'} if modulos['reparto'] else None,
            {'titulo': 'Cuentas Corrientes', 'url': 'ventas:cuentas_corrientes', 'icono': 'fa-hand-holding-usd', 'color': 'danger', 'desc': 'Saldos pendientes'} if modulos['cuenta_corriente'] else None,
            {'titulo': 'Clientes', 'url': 'ventas:lista_clientes', 'icono': 'fa-users', 'color': 'info', 'desc': 'Gestionar clientes'},
            {'titulo': 'Reportes', 'url': 'ventas:reportes', 'icono': 'fa-chart-bar', 'color': 'secondary', 'desc': 'Estadísticas'},
        ]
        accesos = [a for a in accesos if a]

    else:  # superadmin / gerente
        accesos = [
            {'titulo': 'Punto de Venta', 'url': 'ventas:pos', 'icono': 'fa-cash-register', 'color': 'success', 'desc': 'Cobrar y facturar'} if modulos['punto_venta'] else None,
            {'titulo': 'Historial', 'url': 'ventas:lista_ventas', 'icono': 'fa-list-alt', 'color': 'primary', 'desc': 'Ver ventas'},
            {'titulo': 'Remitos Pendientes', 'url': 'ventas:remitos_pendientes', 'icono': 'fa-file-invoice', 'color': 'warning', 'desc': 'Por facturar'} if modulos['reparto'] else None,
            {'titulo': 'Cuentas Corrientes', 'url': 'ventas:cuentas_corrientes', 'icono': 'fa-hand-holding-usd', 'color': 'danger', 'desc': 'Saldos pendientes'} if modulos['cuenta_corriente'] else None,
            {'titulo': 'Clientes', 'url': 'ventas:lista_clientes', 'icono': 'fa-users', 'color': 'info', 'desc': 'Gestionar clientes'},
            {'titulo': 'Repartidores', 'url': 'ventas:lista_repartidores', 'icono': 'fa-motorcycle', 'color': 'warning', 'desc': 'Personal de reparto'} if modulos['reparto'] else None,
            {'titulo': 'Productos', 'url': 'productos:lista_productos', 'icono': 'fa-box', 'color': 'secondary', 'desc': 'Stock y precios'},
            {'titulo': 'Reportes', 'url': 'ventas:reportes', 'icono': 'fa-chart-bar', 'color': 'secondary', 'desc': 'Estadísticas'},
            {'titulo': 'Auditoría', 'url': 'configuracion:auditoria', 'icono': 'fa-history', 'color': 'dark', 'desc': 'Historial de acciones'},
            {'titulo': 'Configuración', 'url': 'configuracion:configuracion_general', 'icono': 'fa-cog', 'color': 'dark', 'desc': 'Datos de la empresa'},
        ]
        accesos = [a for a in accesos if a]

    # ============================================================
    # KPIs CONTEXTUALES SEGÚN ROL
    # ============================================================
    hoy = timezone.now().date()
    kpis = {}

    if rol == 'repartidor':
        kpis = {
            'pedidos_pendientes': Venta.objects.filter(
                repartidor=user, estado='PENDIENTE_ENTREGA'
            ).count(),
            'entregados_hoy': Venta.objects.filter(
                repartidor=user, estado='ENTREGADO', fecha_entrega__date=hoy
            ).count(),
        }
    else:
        # KPIs del día (ventas + CC)
        ventas_hoy = Venta.objects.filter(
            fecha__date=hoy, es_nota_credito=False
        ).exclude(estado='CANCELADO')

        if rol != 'superadmin' and getattr(user, 'sucursal_id', None):
            ventas_hoy = ventas_hoy.filter(sucursal_id=user.sucursal_id)

        cc_pendiente = Venta.objects.filter(
            estado_cobro__in=['PENDIENTE', 'PARCIAL'],
            es_nota_credito=False,
        ).exclude(estado='CANCELADO')

        if rol != 'superadmin' and getattr(user, 'sucursal_id', None):
            cc_pendiente = cc_pendiente.filter(sucursal_id=user.sucursal_id)

        kpis = {
            'ventas_hoy': ventas_hoy.aggregate(t=Sum('total'))['t'] or 0,
            'operaciones_hoy': ventas_hoy.count(),
            'cc_total': cc_pendiente.aggregate(t=Sum('saldo_pendiente'))['t'] or 0,
            'cc_clientes': cc_pendiente.filter(cliente__isnull=False).values('cliente').distinct().count(),
        }

    # ============================================================
    # TURNO ACTIVO (si aplica)
    # ============================================================
    turno_activo = None
    if modulos['punto_venta']:
        from apps.ventas.models import CajaTurno
        turno_activo = CajaTurno.objects.filter(
            vendedor=user, estado='ABIERTA'
        ).select_related('sucursal').first()

    # ============================================================
    # KPIs GLOBALES
    # ============================================================
    total_recaudado = Venta.objects.aggregate(total=Sum('total'))['total'] or 0.0
    cantidad_ventas = Venta.objects.count()

    vendedor_top = (
        Venta.objects.filter(vendedor__isnull=False)
        .values('vendedor__username', 'vendedor__first_name', 'vendedor__last_name')
        .annotate(total_ventas=Count('id'))
        .order_by('-total_ventas')
        .first()
    )

    nombre_vendedor_top = None
    ventas_vendedor_top = 0
    if vendedor_top:
        nombre = f"{vendedor_top.get('vendedor__first_name', '')} {vendedor_top.get('vendedor__last_name', '')}".strip()
        nombre_vendedor_top = nombre if nombre else vendedor_top.get('vendedor__username')
        ventas_vendedor_top = vendedor_top.get('total_ventas', 0)
    elif cantidad_ventas > 0:
        nombre_vendedor_top = user.first_name if user.first_name else user.username
        ventas_vendedor_top = cantidad_ventas

    producto_top = (
        DetalleVenta.objects.values('producto__nombre')
        .annotate(total_vendido=Sum('cantidad'))
        .order_by('-total_vendido')
        .first()
    )

    # ============================================================
    # ÚLTIMAS VENTAS PAGINADAS
    # ============================================================
    ventas_qs = Venta.objects.select_related('cliente', 'vendedor').order_by('-fecha')
    paginator = Paginator(ventas_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        # Alertas
        'alertas': alertas,

        # Nuevos
        'rol': rol,
        'modulos': modulos,
        'accesos': accesos,
        'kpis': kpis,
        'turno_activo': turno_activo,

        # Existentes
        'total_recaudado': total_recaudado,
        'cantidad_ventas': cantidad_ventas,
        'nombre_vendedor_top': nombre_vendedor_top,
        'ventas_vendedor_top': ventas_vendedor_top,
        'producto_top': producto_top,
        'page_obj': page_obj,
    }

    return render(request, 'dashboard.html', context)