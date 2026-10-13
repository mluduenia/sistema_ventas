from django.db.models import F
from django.utils import timezone
from datetime import timedelta

from apps.ventas.models import Venta, CajaTurno
from apps.productos.models import Producto
from .models import Alerta


def generar_alertas_para_usuario(user):
    """Genera alertas según el rol del usuario. Se llama después del login."""
    alertas_creadas = []
    rol = getattr(user, 'rol', '')
    es_admin = user.is_superuser or rol in ('gerente', 'superadmin')

    # ============================================================
    # 🔽 PASO 1: LIMPIAR ALERTAS OBSOLETAS
    # ============================================================
    # Si ya no existe el problema, la alerta desaparece.

    # Cajas abiertas +12h
    hace_12h = timezone.now() - timedelta(hours=12)
    hay_cajas_viejas = CajaTurno.objects.filter(
        estado='ABIERTA',
        fecha_apertura__lt=hace_12h,
    ).exists()
    if not hay_cajas_viejas:
        Alerta.objects.filter(tipo='caja_abierta').delete()

    # Stock bajo mínimo
    hay_productos_bajos = Producto.objects.filter(
        stock_actual__lte=F('stock_minimo'),
        stock_minimo__gt=0,
    ).exists()
    if not hay_productos_bajos:
        Alerta.objects.filter(tipo='stock_minimo').delete()

    # Remitos pendientes de rendición
    hay_remitos = Venta.objects.filter(
        estado__in=['PENDIENTE_ENTREGA', 'ENTREGADO'],
        estado_cobro__in=['PENDIENTE', 'PARCIAL'],
    ).exclude(estado='CANCELADO').exists()
    if not hay_remitos:
        Alerta.objects.filter(tipo='rendicion_pendiente').delete()

    # Comprobantes sin facturar
    hay_sin_facturar = Venta.objects.filter(
        tipo_comprobante=0,
        cae__isnull=True,
        es_remito=False,
        es_nota_credito=False,
    ).exclude(estado__in=['PRESUPUESTO', 'CANCELADO']).exists()
    if not hay_sin_facturar:
        Alerta.objects.filter(tipo='factura_pendiente').delete()

    # Pedidos pendientes del repartidor
    if rol == 'repartidor':
        hay_pedidos = Venta.objects.filter(
            repartidor=user,
            estado='PENDIENTE_ENTREGA',
        ).exclude(estado='CANCELADO').exists()
        if not hay_pedidos:
            Alerta.objects.filter(usuario=user, tipo='pedido_pendiente').delete()

    # ============================================================
    # 🔽 PASO 2: GENERAR NUEVAS ALERTAS
    # ============================================================

    # ---- REPARTIDOR ----
    if rol == 'repartidor':
        pedidos = Venta.objects.filter(
            repartidor=user,
            estado='PENDIENTE_ENTREGA',
        ).exclude(estado='CANCELADO')

        for v in pedidos:
            alerta, created = Alerta.objects.update_or_create(
                usuario=user,
                tipo='pedido_pendiente',
                titulo=f'Pedido #{v.id} pendiente de entrega',
                defaults={
                    'nivel': 'warning',
                    'mensaje': f'Tenés un pedido asignado sin entregar: #{v.id}',
                    'url': '/ventas/mis-pedidos/',
                    'leida': False,  # 🔽 si vuelve a aparecer, se "desmarca"
                }
            )
            if created:
                alertas_creadas.append(alerta)

    # ---- CAJERO / VENDEDOR ----
    if rol in ('cajero', 'vendedor'):
        # Remitos pendientes de rendición
        rendiciones = Venta.objects.filter(
            estado__in=['PENDIENTE_ENTREGA', 'ENTREGADO'],
            estado_cobro__in=['PENDIENTE', 'PARCIAL'],
        ).exclude(estado='CANCELADO')

        if rendiciones.exists():
            alerta, created = Alerta.objects.update_or_create(
                rol=rol,
                tipo='rendicion_pendiente',
                defaults={
                    'nivel': 'warning',
                    'titulo': f'{rendiciones.count()} remitos pendientes de rendición',
                    'mensaje': f'Hay {rendiciones.count()} remitos en la calle sin rendir.',
                    'url': '/ventas/remitos-pendientes/',
                }
            )
            if created:
                alertas_creadas.append(alerta)

        # Comprobantes no fiscales sin facturar
        sin_factura = Venta.objects.filter(
            tipo_comprobante=0,
            cae__isnull=True,
            es_remito=False,
            es_nota_credito=False,
        ).exclude(estado__in=['PRESUPUESTO', 'CANCELADO'])

        if sin_factura.exists():
            alerta, created = Alerta.objects.update_or_create(
                rol=rol,
                tipo='factura_pendiente',
                defaults={
                    'nivel': 'info',
                    'titulo': f'{sin_factura.count()} comprobantes sin facturar',
                    'mensaje': f'Hay {sin_factura.count()} tickets no fiscales pendientes de facturar.',
                    'url': '/ventas/historial/',
                }
            )
            if created:
                alertas_creadas.append(alerta)

    # ---- GERENTE / SUPERADMIN / ADMIN ----
    if es_admin:
        # Stock bajo mínimo
        productos_bajos = Producto.objects.filter(
            stock_actual__lte=F('stock_minimo'),
            stock_minimo__gt=0,
        )

        if productos_bajos.exists():
            alerta, created = Alerta.objects.update_or_create(
                rol='gerente',
                tipo='stock_minimo',
                defaults={
                    'nivel': 'danger',
                    'titulo': f'{productos_bajos.count()} productos con stock bajo mínimo',
                    'mensaje': f'Hay {productos_bajos.count()} productos que necesitan reposición.',
                    'url': '/productos/',
                }
            )
            if created:
                alertas_creadas.append(alerta)

        # Cajas abiertas +12h
        if cajas_viejas := CajaTurno.objects.filter(
            estado='ABIERTA',
            fecha_apertura__lt=hace_12h,
        ):
            alerta, created = Alerta.objects.update_or_create(
                rol='gerente',
                tipo='caja_abierta',
                defaults={
                    'nivel': 'warning',
                    'titulo': f'{cajas_viejas.count()} cajas abiertas hace +12h',
                    'mensaje': f'Hay {cajas_viejas.count()} turnos de caja sin cerrar. Podés cerrarlos desde el listado de informes.',
                    'url': '/ventas/informes/',
                }
            )
            if created:
                alertas_creadas.append(alerta)

    return alertas_creadas