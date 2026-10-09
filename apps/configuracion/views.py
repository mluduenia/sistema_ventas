from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator              # 🔽 AGREGAR ESTA
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.views.decorators.http import require_POST
from .models import EmpresaConfig, Sucursal
from .forms import EmpresaConfigForm
from apps.productos.models import ListaPrecio
from .audit import registrar_log

import logging
logger = logging.getLogger(__name__)

def es_admin_o_super(user):
    """Permite el acceso a Superusuarios o Administradores."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name='Administrador').exists()
    )


# =========================================================
# CONFIGURACIÓN GENERAL DE LA EMPRESA
# =========================================================

@login_required
@user_passes_test(es_admin_o_super)
def configuracion_general(request):
    """Vista única para gestionar la configuración de la empresa y ARCA."""
    config, _ = EmpresaConfig.objects.get_or_create(id=1)

    if request.method == 'POST':
        if not request.user.is_superuser:
            messages.error(
                request,
                'Acceso denegado: Tenés permisos de lectura. '
                'Solo el Superusuario puede modificar la configuración.'
            )
            return redirect('configuracion:configuracion_general')

        form = EmpresaConfigForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'La configuración de la empresa y datos de ARCA se han actualizado correctamente.'
            )
            return redirect('configuracion:configuracion_general')
        else:
            messages.error(request, 'Por favor revisá los errores en el formulario.')
    else:
        form = EmpresaConfigForm(instance=config)

    modo_actual = 'PRODUCCION' if config.ambiente_arca == 'PROD' else 'HOMOLOGACION'

    return render(
        request,
        'configuracion/empresa_config.html',
        {
            'form': form,
            'config': config,
            'es_readonly': not request.user.is_superuser,
            'modo_actual': modo_actual,
        }
    )


# =========================================================
# GESTIÓN DE SUCURSALES (CRUD)
# =========================================================

@login_required
@user_passes_test(es_admin_o_super)
def lista_sucursales_view(request):
    """Lista todas las sucursales con KPIs."""
    from apps.ventas.models import Venta, Cliente
    from apps.productos.models import StockSucursal

    busqueda = request.GET.get('q', '').strip()
    filtro_activa = request.GET.get('activa', '1')

    sucursales = Sucursal.objects.select_related('lista_precio').all()

    if busqueda:
        sucursales = sucursales.filter(
            Q(nombre__icontains=busqueda) |
            Q(direccion__icontains=busqueda) |
            Q(telefono__icontains=busqueda)
        )

    if filtro_activa == '1':
        sucursales = sucursales.filter(activa=True)

    # Enriquecer cada sucursal con KPIs
    sucursales_con_kpis = []
    for s in sucursales:
        total_ventas = Venta.objects.filter(sucursal=s).aggregate(
            t=Sum('total'), c=Count('id')
        )
        cantidad_clientes = Venta.objects.filter(
            sucursal=s, cliente__isnull=False
        ).values('cliente').distinct().count()
        total_stock = StockSucursal.objects.filter(sucursal=s).aggregate(
            t=Sum('cantidad')
        )['t'] or 0

        sucursales_con_kpis.append({
            'sucursal': s,
            'total_ventas': total_ventas['t'] or 0,
            'cantidad_ventas': total_ventas['c'] or 0,
            'cantidad_clientes': cantidad_clientes,
            'total_stock': total_stock,
        })

    context = {
        'sucursales_con_kpis': sucursales_con_kpis,
        'busqueda': busqueda,
        'filtro_activa': filtro_activa,
        'total': len(sucursales_con_kpis),
    }
    return render(request, 'configuracion/lista_sucursales.html', context)


@login_required
@user_passes_test(es_admin_o_super)
def crear_sucursal_view(request):
    """Crea una nueva sucursal."""
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        tipo = request.POST.get('tipo', 'SUCURSAL')
        direccion = request.POST.get('direccion', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        punto_de_venta_arca = int(request.POST.get('punto_de_venta_arca', 1) or 1)
        lista_precio_id = request.POST.get('lista_precio', '').strip()
        activa = request.POST.get('activa') == 'on'
        es_central = request.POST.get('es_central') == 'on'

        if not nombre:
            messages.error(request, 'El nombre es obligatorio.')
            return render(request, 'configuracion/crear_sucursal.html', {
                'form_data': request.POST,
                'listas_precio': ListaPrecio.objects.filter(activa=True),
            })

        # Si es central, desmarcar las otras
        if es_central:
            Sucursal.objects.filter(es_central=True).update(es_central=False)

        try:
            Sucursal.objects.create(
                nombre=nombre,
                tipo=tipo,
                direccion=direccion,
                telefono=telefono,
                email=email,
                punto_de_venta_arca=punto_de_venta_arca,
                lista_precio_id=lista_precio_id if lista_precio_id else None,
                activa=activa,
                es_central=es_central,
            )
            messages.success(request, f'Sucursal "{nombre}" creada correctamente.')
            return redirect('configuracion:lista_sucursales')
        except Exception as e:
            messages.error(request, f'Error al crear sucursal: {str(e)}')

    context = {
        'listas_precio': ListaPrecio.objects.filter(activa=True),
    }
    return render(request, 'configuracion/crear_sucursal.html', context)


@login_required
@user_passes_test(es_admin_o_super)
def editar_sucursal_view(request, sucursal_id):
    """Edita una sucursal existente."""
    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        tipo = request.POST.get('tipo', 'SUCURSAL')
        direccion = request.POST.get('direccion', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        punto_de_venta_arca = int(request.POST.get('punto_de_venta_arca', 1) or 1)
        lista_precio_id = request.POST.get('lista_precio', '').strip()
        activa = request.POST.get('activa') == 'on'
        es_central = request.POST.get('es_central') == 'on'

        if not nombre:
            messages.error(request, 'El nombre es obligatorio.')
            return redirect('configuracion:editar_sucursal', sucursal_id=sucursal.id)

        # Si marca como central, desmarcar las demás
        if es_central and not sucursal.es_central:
            Sucursal.objects.filter(es_central=True).update(es_central=False)

        try:
            sucursal.nombre = nombre
            sucursal.tipo = tipo
            sucursal.direccion = direccion
            sucursal.telefono = telefono
            sucursal.email = email
            sucursal.punto_de_venta_arca = punto_de_venta_arca
            sucursal.lista_precio_id = lista_precio_id if lista_precio_id else None
            sucursal.activa = activa
            sucursal.es_central = es_central
            sucursal.save()

            messages.success(request, f'Sucursal "{nombre}" actualizada correctamente.')
            return redirect('configuracion:lista_sucursales')
        except Exception as e:
            messages.error(request, f'Error al actualizar: {str(e)}')

    context = {
        'sucursal': sucursal,
        'listas_precio': ListaPrecio.objects.filter(activa=True),
    }
    return render(request, 'configuracion/editar_sucursal.html', context)


# =========================================================
# LISTADOS POR SUCURSAL
# =========================================================

@login_required
@user_passes_test(es_admin_o_super)
def stock_por_sucursal_view(request):
    """Muestra el stock de todos los productos en cada sucursal."""
    from apps.productos.models import Producto, StockSucursal

    sucursal_id = request.GET.get('sucursal', '').strip()
    busqueda = request.GET.get('q', '').strip()
    solo_bajo_stock = request.GET.get('bajo_stock', '') == '1'
    solo_sin_stock = request.GET.get('sin_stock', '') == '1'

    sucursales = Sucursal.objects.filter(activa=True).order_by('-es_central', 'nombre')

    # Filtrar por sucursal específica si se pidió
    sucursales_mostrar = sucursales
    if sucursal_id:
        sucursales_mostrar = sucursales.filter(id=sucursal_id)

    productos = Producto.objects.filter(activo=True).select_related('categoria').order_by('nombre')

    if busqueda:
        productos = productos.filter(
            Q(nombre__icontains=busqueda) |
            Q(codigo_barra__icontains=busqueda)
        )

    # Traer todos los stocks de una sola vez (más eficiente)
    stocks_dict = {}
    for ss in StockSucursal.objects.select_related('sucursal').all():
        key = (ss.producto_id, ss.sucursal_id)
        stocks_dict[key] = ss

    resultados = []
    for p in productos[:500]:
        fila = {
            'producto': p,
            'stocks': [],
        }
        total = 0
        for s in sucursales_mostrar:
            ss = stocks_dict.get((p.id, s.id))
            cantidad = ss.cantidad if ss else 0
            stock_minimo = ss.stock_minimo if ss else 5
            total += cantidad
            fila['stocks'].append({
                'sucursal': s,
                'cantidad': cantidad,
                'stock_minimo': stock_minimo,
                'bajo': 0 < cantidad <= stock_minimo,
                'sin_stock': cantidad == 0,
                'ok': cantidad > stock_minimo,
            })
        fila['total'] = total

        # Filtros de fila
        if solo_bajo_stock and not any(x['bajo'] for x in fila['stocks']):
            continue
        if solo_sin_stock and not any(x['sin_stock'] for x in fila['stocks']):
            continue

        resultados.append(fila)

    context = {
        'sucursales': sucursales_mostrar,
        'todas_sucursales': sucursales,
        'resultados': resultados,
        'busqueda': busqueda,
        'sucursal_id': sucursal_id,
        'solo_bajo_stock': solo_bajo_stock,
        'solo_sin_stock': solo_sin_stock,
        'total_productos': len(resultados),
    }
    return render(request, 'configuracion/stock_por_sucursal.html', context)


# =========================================================
# CONFIGURACIÓN DE MÓDULOS DE NEGOCIO
# =========================================================

@login_required
def modulos_negocio_view(request):
    """Configura qué módulos del sistema están activos."""
    if not (request.user.is_superuser or getattr(request.user, 'rol', '') == 'gerente'):
        messages.error(request, 'No tenés permisos.')
        return redirect('core:dashboard')

    config = EmpresaConfig.objects.first()
    if not config:
        config = EmpresaConfig.objects.create()

    if request.method == 'POST':
        modo = request.POST.get('modo_negocio', 'CUSTOM')

        if modo != 'CUSTOM':
            config.modo_negocio = modo
            config.aplicar_preset(modo)
        else:
            config.modo_negocio = 'CUSTOM'
            config.modulo_punto_venta = request.POST.get('modulo_punto_venta') == 'on'
            config.modulo_preventa = request.POST.get('modulo_preventa') == 'on'
            config.modulo_reparto = request.POST.get('modulo_reparto') == 'on'
            config.modulo_deposito = request.POST.get('modulo_deposito') == 'on'
            config.modulo_cuenta_corriente = request.POST.get('modulo_cuenta_corriente') == 'on'
            config.modulo_multi_sucursal = request.POST.get('modulo_multi_sucursal') == 'on'

        config.save()
        registrar_log(
            request,
            accion='MODULOS',
            descripcion=f'Módulos actualizados a modo {config.get_modo_negocio_display()}',
            modelo='EmpresaConfig',
            objeto_id=config.id,
            datos_despues={
                'modo': config.modo_negocio,
                'punto_venta': config.modulo_punto_venta,
                'preventa': config.modulo_preventa,
                'reparto': config.modulo_reparto,
                'cuenta_corriente': config.modulo_cuenta_corriente,
                'multi_sucursal': config.modulo_multi_sucursal,
            },
        )
        messages.success(request, '✅ Configuración de módulos guardada.')
        return redirect('configuracion:modulos_negocio')

    return render(request, 'configuracion/modulos_negocio.html', {'config': config})


# =========================================================
# LIMPIEZA DE DATOS (SOLO ADMIN)
# =========================================================

def es_solo_super_o_gerente(user):
    """Solo superuser o gerente pueden limpiar datos."""
    return user.is_authenticated and (
        user.is_superuser or getattr(user, 'rol', '') == 'gerente'
    )


@login_required
@user_passes_test(es_solo_super_o_gerente)
def limpiar_datos_view(request):
    """
    Muestra un resumen de cuántos registros hay por categoría
    y permite seleccionar qué borrar.
    """
    from apps.ventas.models import (
        DetalleVenta, Pago, StockABordo, ItemCarga, CargaVehiculo,
        Venta, CajaTurno, Cliente
    )
    from apps.productos.models import MovimientoStock

    resumen = {
        'clientes': Cliente.objects.count(),
        'ventas': Venta.objects.count(),
        'detalles': DetalleVenta.objects.count(),
        'pagos': Pago.objects.count(),
        'cajas': CajaTurno.objects.count(),
        'cargas': CargaVehiculo.objects.count(),
        'items_carga': ItemCarga.objects.count(),
        'stock_abordo': StockABordo.objects.count(),
        'movimientos_stock': MovimientoStock.objects.count(),
    }

    total_registros = sum(resumen.values())

    context = {
        'resumen': resumen,
        'total_registros': total_registros,
    }
    return render(request, 'configuracion/limpiar_datos.html', context)


@login_required
@user_passes_test(es_solo_super_o_gerente)
@require_POST
def ejecutar_limpieza_view(request):
    """
    Ejecuta la limpieza de datos seleccionados.
    Requiere confirmación por POST + checkbox de confirmación explícito.
    """
    from apps.ventas.models import (
        DetalleVenta, Pago, StockABordo, ItemCarga, CargaVehiculo,
        Venta, CajaTurno, Cliente
    )
    from apps.productos.models import MovimientoStock

    if request.POST.get('confirmar') != 'SI-BORRAR':
        messages.error(request, 'Confirmación inválida. No se borró nada.')
        return redirect('configuracion:limpiar_datos')

    borrar_clientes = request.POST.get('borrar_clientes') == 'on'
    borrar_ventas = request.POST.get('borrar_ventas') == 'on'
    borrar_cajas = request.POST.get('borrar_cajas') == 'on'
    borrar_cargas = request.POST.get('borrar_cargas') == 'on'
    borrar_movimientos = request.POST.get('borrar_movimientos') == 'on'

    if not any([borrar_clientes, borrar_ventas, borrar_cajas, borrar_cargas, borrar_movimientos]):
        messages.warning(request, 'No seleccionaste ninguna categoría para borrar.')
        return redirect('configuracion:limpiar_datos')

    resultados = {}

    try:
        with transaction.atomic():
            if borrar_ventas:
                _, det = DetalleVenta.objects.all().delete()
                resultados['Detalles de venta'] = det.get('ventas.DetalleVenta', 0)

                _, pag = Pago.objects.all().delete()
                resultados['Pagos de clientes'] = pag.get('ventas.Pago', 0)

                _, vtas = Venta.objects.all().delete()
                resultados['Ventas / Remitos / Facturas'] = vtas.get('ventas.Venta', 0)

            if borrar_cajas:
                _, cj = CajaTurno.objects.all().delete()
                resultados['Turnos de caja'] = cj.get('ventas.CajaTurno', 0)

            if borrar_cargas:
                _, itc = ItemCarga.objects.all().delete()
                resultados['Items de carga'] = itc.get('ventas.ItemCarga', 0)

                _, stk = StockABordo.objects.all().delete()
                resultados['Stock a bordo'] = stk.get('ventas.StockABordo', 0)

                _, crg = CargaVehiculo.objects.all().delete()
                resultados['Cargas de vehículo'] = crg.get('ventas.CargaVehiculo', 0)

            if borrar_movimientos:
                _, mov = MovimientoStock.objects.all().delete()
                resultados['Movimientos de stock'] = mov.get('productos.MovimientoStock', 0)

            if borrar_clientes:
                _, cli = Cliente.objects.all().delete()
                resultados['Clientes'] = cli.get('ventas.Cliente', 0)

        logger.warning(
            f"LIMPIEZA DE DATOS ejecutada por {request.user.username} "
            f"(superuser={request.user.is_superuser}). Resultados: {resultados}"
        )

        total = sum(resultados.values())
        detalle = ', '.join([f"{k}: {v}" for k, v in resultados.items()])
        messages.success(
            request,
            f'✅ Limpieza completada. Se borraron {total} registros. ({detalle})'
        )

    except Exception as e:
        logger.exception(f"Error en limpieza de datos: {e}")
        messages.error(request, f'❌ Error durante la limpieza: {str(e)}')

    return redirect('configuracion:limpiar_datos')


# =========================================================
# RESET TOTAL EN MODO DESARROLLO (solo HOMOLOGACIÓN)
# =========================================================

def _es_superuser(user):
    """Solo superuser puede ejecutar el reset total."""
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(_es_superuser)
def reset_dev_view(request):
    """
    Pantalla de Reset Total - SOLO si ambiente_arca == HOMO.
    Muestra resumen de cuántos registros hay por categoría.
    """
    from apps.ventas.models import (
        DetalleVenta, Pago, StockABordo, ItemCarga, CargaVehiculo,
        Venta, CajaTurno, Cliente, InformeCaja, PerfilRepartidor,
    )
    from apps.productos.models import (
        Producto, Categoria, Proveedor, MovimientoStock,
        StockSucursal, ListaPrecio, PrecioProducto,
    )
    from django.contrib.auth import get_user_model
    Usuario = get_user_model()

    config = EmpresaConfig.objects.first()
    if not config or config.ambiente_arca != 'HOMO':
        messages.error(request, 'Esta función solo está disponible en ambiente HOMOLOGACIÓN (Pruebas).')
        return redirect('configuracion:configuracion_general')

    resumen = {
        'ventas': Venta.objects.count(),
        'detalles_venta': DetalleVenta.objects.count(),
        'pagos': Pago.objects.count(),
        'informes_caja': InformeCaja.objects.count(),
        'cajas': CajaTurno.objects.count(),
        'clientes': Cliente.objects.count(),
        'repartidores': PerfilRepartidor.objects.count(),
        'cargas': CargaVehiculo.objects.count(),
        'items_carga': ItemCarga.objects.count(),
        'stock_abordo': StockABordo.objects.count(),
        'productos': Producto.objects.count(),
        'categorias': Categoria.objects.count(),
        'proveedores': Proveedor.objects.count(),
        'movimientos_stock': MovimientoStock.objects.count(),
        'stock_sucursal': StockSucursal.objects.count(),
        'listas_precio': ListaPrecio.objects.count(),
        'precios_producto': PrecioProducto.objects.count(),
    }

    total_registros = sum(resumen.values())

    return render(request, 'configuracion/reset_dev.html', {
        'resumen': resumen,
        'total_registros': total_registros,
        'config': config,
    })


@login_required
@user_passes_test(_es_superuser)
@require_POST
def ejecutar_reset_dev_view(request):
    """
    Ejecuta el reset total de la base (modo desarrollo / HOMOLOGACIÓN).
    Borra todo lo transaccional y los datos maestros generados en pruebas.
    Conserva: usuarios administradores, EmpresaConfig, sucursales, grupos y permisos.
    """
    from apps.ventas.models import (
        DetalleVenta, Pago, StockABordo, ItemCarga, CargaVehiculo,
        Venta, CajaTurno, Cliente, InformeCaja, PerfilRepartidor,
    )
    from apps.productos.models import (
        Producto, Categoria, Proveedor, MovimientoStock,
        StockSucursal, ListaPrecio, PrecioProducto,
    )
    from django.contrib.auth import get_user_model
    from django.contrib.admin.models import LogEntry
    Usuario = get_user_model()

    config = EmpresaConfig.objects.first()
    if not config or config.ambiente_arca != 'HOMO':
        messages.error(request, 'Esta función solo está disponible en HOMOLOGACIÓN.')
        return redirect('configuracion:configuracion_general')

    # Triple confirmación: palabra exacta
    if request.POST.get('confirmar') != 'BORRAR-TODO-HOMO':
        messages.error(request, 'Confirmación inválida. Escribí exactamente "BORRAR-TODO-HOMO".')
        return redirect('configuracion:reset_dev')

    resultados = {}

    try:
        with transaction.atomic():
            # 1. TRANSACCIONAL (de hijos a padres)
            _, r = DetalleVenta.objects.all().delete()
            resultados['Detalles de venta'] = r.get('ventas.DetalleVenta', 0)

            _, r = Pago.objects.all().delete()
            resultados['Pagos'] = r.get('ventas.Pago', 0)

            _, r = InformeCaja.objects.all().delete()
            resultados['Informes de caja X/Z'] = r.get('ventas.InformeCaja', 0)

            _, r = StockABordo.objects.all().delete()
            resultados['Stock a bordo'] = r.get('ventas.StockABordo', 0)

            _, r = ItemCarga.objects.all().delete()
            resultados['Items de carga'] = r.get('ventas.ItemCarga', 0)

            _, r = CargaVehiculo.objects.all().delete()
            resultados['Cargas de vehículo'] = r.get('ventas.CargaVehiculo', 0)

            _, r = Venta.objects.all().delete()
            resultados['Ventas / Remitos / Facturas'] = r.get('ventas.Venta', 0)

            _, r = CajaTurno.objects.all().delete()
            resultados['Turnos de caja'] = r.get('ventas.CajaTurno', 0)

            # 2. CLIENTES
            _, r = Cliente.objects.all().delete()
            resultados['Clientes'] = r.get('ventas.Cliente', 0)

            # 3. REPARTIDORES (perfil + user)
            _, r = PerfilRepartidor.objects.all().delete()
            resultados['Perfiles de repartidor'] = r.get('ventas.PerfilRepartidor', 0)

            users_repartidores = Usuario.objects.filter(rol='repartidor')
            count_users_rep = users_repartidores.count()
            users_repartidores.delete()
            resultados['Usuarios repartidores'] = count_users_rep

            # 4. STOCK Y MOVIMIENTOS
            _, r = MovimientoStock.objects.all().delete()
            resultados['Movimientos de stock'] = r.get('productos.MovimientoStock', 0)

            _, r = StockSucursal.objects.all().delete()
            resultados['Stock por sucursal'] = r.get('productos.StockSucursal', 0)

            # 5. PRODUCTOS Y CATÁLOGOS
            _, r = PrecioProducto.objects.all().delete()
            resultados['Precios por lista'] = r.get('productos.PrecioProducto', 0)

            _, r = Producto.objects.all().delete()
            resultados['Productos'] = r.get('productos.Producto', 0)

            _, r = Categoria.objects.all().delete()
            resultados['Categorías / Rubros'] = r.get('productos.Categoria', 0)

            _, r = Proveedor.objects.all().delete()
            resultados['Proveedores'] = r.get('productos.Proveedor', 0)

            _, r = ListaPrecio.objects.all().delete()
            resultados['Listas de precios'] = r.get('productos.ListaPrecio', 0)

            # 6. LOG DE ADMIN
            _, r = LogEntry.objects.all().delete()
            resultados['Log de administración'] = r.get('admin.LogEntry', 0)

        logger.warning(
            f"RESET TOTAL ejecutado por {request.user.username} "
            f"(superuser={request.user.is_superuser}). Resultados: {resultados}"
        )

        total = sum(resultados.values())
        messages.success(
            request,
            f'✅ Reset completado. Se borraron {total} registros en total.'
        )

        request.session['reset_dev_resultados'] = resultados

        return redirect('configuracion:reset_dev')

    except Exception as e:
        logger.exception(f"Error en reset total: {e}")
        messages.error(request, f'❌ Error durante el reset: {str(e)}')
        return redirect('configuracion:reset_dev')

# =========================================================
# AUDITORÍA / LOG DE ACTIVIDAD
# =========================================================

def es_admin_o_gerente_o_super(user):
    """Superuser, gerente o vendedor pueden ver el log."""
    return user.is_authenticated and (
        user.is_superuser or getattr(user, 'rol', '') in ('gerente', 'vendedor')
    )


@login_required
@user_passes_test(es_admin_o_gerente_o_super)
def auditoria_view(request):
    """Listado de todos los eventos de auditoría con filtros."""
    from .models import AuditLog
    from django.contrib.auth import get_user_model
    Usuario = get_user_model()

    qs = AuditLog.objects.select_related('usuario').all()

    # --- Filtros ---
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    usuario_id = request.GET.get('usuario', '').strip()
    accion = request.GET.get('accion', '').strip()
    nivel = request.GET.get('nivel', '').strip()
    modelo = request.GET.get('modelo', '').strip()
    busqueda = request.GET.get('q', '').strip()

    if fecha_desde:
        qs = qs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__date__lte=fecha_hasta)
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if accion:
        qs = qs.filter(accion=accion)
    if nivel:
        qs = qs.filter(nivel=nivel)
    if modelo:
        qs = qs.filter(modelo__icontains=modelo)
    if busqueda:
        qs = qs.filter(descripcion__icontains=busqueda)

    # --- KPIs ---
    total = qs.count()
    criticos = qs.filter(nivel='CRITICAL').count()
    warnings = qs.filter(nivel='WARNING').count()

    # --- Paginación ---
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    # --- Listas para los selects ---
    usuarios = Usuario.objects.filter(
        audit_logs__isnull=False
    ).distinct().order_by('username')

    acciones_disponibles = AuditLog.ACCIONES
    niveles_disponibles = AuditLog.NIVELES

    modelos_disponibles = AuditLog.objects.exclude(modelo='').values_list(
        'modelo', flat=True
    ).distinct().order_by('modelo')

    context = {
        'page_obj': page_obj,
        'total': total,
        'criticos': criticos,
        'warnings': warnings,
        'usuarios': usuarios,
        'acciones_disponibles': acciones_disponibles,
        'niveles_disponibles': niveles_disponibles,
        'modelos_disponibles': modelos_disponibles,
        'filtros': {
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'usuario': usuario_id,
            'accion': accion,
            'nivel': nivel,
            'modelo': modelo,
            'q': busqueda,
        },
    }
    return render(request, 'configuracion/auditoria.html', context)


@login_required
@user_passes_test(es_admin_o_gerente_o_super)
def auditoria_detalle_view(request, log_id):
    """Ver el detalle completo de un evento."""
    from .models import AuditLog
    log = get_object_or_404(AuditLog, id=log_id)
    return render(request, 'configuracion/auditoria_detalle.html', {'log': log})