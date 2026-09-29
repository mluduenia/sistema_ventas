import json
import logging
import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

# Importaciones de apps locales (Corregido: apps.configuracion)
from apps.configuracion.models import EmpresaConfig
from apps.productos.models import MovimientoStock, Producto
from .models import CajaTurno, Cliente, DetalleVenta, Venta, Pago, PerfilRepartidor

logger = logging.getLogger(__name__)
Usuario = get_user_model()


# =========================================================
# DECORADORES DE PERMISOS
# =========================================================

def solo_no_repartidor(view_func):
    """Bloquea el acceso a usuarios con rol 'repartidor'."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request.user, 'rol', '') == 'repartidor':
            messages.error(request, 'No tenés permiso para acceder a esa sección.')
            return redirect('ventas:mis_pedidos')
        return view_func(request, *args, **kwargs)
    return _wrapped


def solo_admin(view_func):
    """Solo permite superuser, vendedor o gerente."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('usuarios:login')
        es_admin = request.user.is_superuser or getattr(request.user, 'rol', '') in ('vendedor', 'gerente')
        if not es_admin:
            return JsonResponse({'success': False, 'error': 'No tenés permisos.'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped

@login_required
@solo_no_repartidor
def lista_ventas_view(request):
    ventas = Venta.objects.all().order_by('-fecha')

    # Parámetros GET
    query = request.GET.get('q', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    mes = request.GET.get('mes', '')
    anio = request.GET.get('anio', '')
    metodo_pago = request.GET.get('metodo_pago', '')

    # Filtro general (ID, Cliente, Vendedor)
    if query:
        ventas = ventas.filter(
            Q(id__icontains=query) |
            Q(cliente__nombre__icontains=query) |
            Q(vendedor__username__icontains=query)
        )

    # Filtros de Fecha
    if fecha_desde:
        ventas = ventas.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        ventas = ventas.filter(fecha__date__lte=fecha_hasta)
    if mes:
        ventas = ventas.filter(fecha__month=mes)
    if anio:
        ventas = ventas.filter(fecha__year=anio)

    # Filtro por Método de Pago
    if metodo_pago:
        ventas = ventas.filter(metodo_pago=metodo_pago)

    # Paginación
    paginator = Paginator(ventas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'mes': mes,
        'anio': anio,
        'metodo_pago': metodo_pago,
        'anios_disponibles': range(datetime.now().year, 2023, -1),
    }
    return render(request, 'ventas/lista_ventas.html', context)

@login_required
@solo_no_repartidor
def buscar_producto_ajax(request):
    """Búsqueda de productos. Devuelve precio según la lista de la sucursal
    del turno activo, y el stock de esa sucursal."""
    from apps.productos.models import PrecioProducto, StockSucursal

    term = request.GET.get('term', '').strip()
    if not term:
        return JsonResponse([], safe=False)

    # Obtener turno activo
    turno_activo = CajaTurno.objects.filter(
        vendedor=request.user, estado='ABIERTA'
    ).select_related('sucursal').first()

    sucursal = turno_activo.sucursal if turno_activo else None

    # Buscar productos
    productos = Producto.objects.filter(
        nombre__icontains=term
    ) | Producto.objects.filter(
        codigo_barra__exact=term
    )

    resultados = []
    for p in productos[:10]:
        # Precio según la lista de la sucursal
        precio_final = float(p.precio_venta)  # fallback
        if sucursal and sucursal.lista_precio:
            pp = PrecioProducto.objects.filter(
                producto=p,
                lista_precio=sucursal.lista_precio
            ).first()
            if pp:
                precio_final = float(pp.precio)

        # Stock de la sucursal
        stock_final = p.stock_actual  # fallback
        if sucursal:
            ss = StockSucursal.objects.filter(
                producto=p, sucursal=sucursal
            ).first()
            if ss:
                stock_final = ss.cantidad

        resultados.append({
            'id': p.id,
            'nombre': p.nombre,
            'codigo_barra': getattr(p, 'codigo_barra', ''),
            'precio_venta': precio_final,
            'stock_actual': stock_final,
        })

    return JsonResponse(resultados, safe=False)

@login_required
@solo_no_repartidor
def abrir_caja(request):
    """Pantalla para que el cajero entrante declare su Fondo de Caja."""
    turno_existente = CajaTurno.objects.filter(vendedor=request.user, estado='ABIERTA').first()
    if turno_existente:
        return redirect('ventas:pos')

    if request.method == 'POST':
        monto_inicial = float(request.POST.get('monto_inicial', 0.0))
        
        CajaTurno.objects.create(
            vendedor=request.user,
            monto_inicial=monto_inicial,
            estado='ABIERTA'
        )
        return redirect('ventas:pos')

    return render(request, 'ventas/abrir_caja.html')


@login_required
@solo_no_repartidor
def cerrar_caja(request):
    """Pantalla de Arqueo y Relevo para el cajero saliente."""
    turno_activo = CajaTurno.objects.filter(vendedor=request.user, estado='ABIERTA').first()
    
    if not turno_activo:
        return redirect('ventas:abrir_caja')

    ventas_turno = Venta.objects.filter(turno=turno_activo)
    
    total_efectivo = ventas_turno.filter(metodo_pago='EFECTIVO').aggregate(total=Sum('total'))['total'] or 0.0
    total_debito = ventas_turno.filter(metodo_pago='TARJETA_DEBITO').aggregate(total=Sum('total'))['total'] or 0.0
    total_credito = ventas_turno.filter(metodo_pago='TARJETA_CREDITO').aggregate(total=Sum('total'))['total'] or 0.0
    total_mp = ventas_turno.filter(metodo_pago='TRANSFERENCIA').aggregate(total=Sum('total'))['total'] or 0.0

    efectivo_esperado = float(turno_activo.monto_inicial) + float(total_efectivo)

    if request.method == 'POST':
        efectivo_contado = float(request.POST.get('monto_final_efectivo', 0.0))
        observaciones = request.POST.get('observaciones', '')

        diferencia = efectivo_contado - efectivo_esperado

        turno_activo.monto_final_efectivo = efectivo_contado
        turno_activo.fecha_cierre = timezone.now()
        turno_activo.diferencia = diferencia
        turno_activo.observaciones = observaciones
        turno_activo.estado = 'CERRADA'
        turno_activo.save()

        return redirect('usuarios:logout')

    context = {
        'turno': turno_activo,
        'total_efectivo': total_efectivo,
        'total_debito': total_debito,
        'total_credito': total_credito,
        'total_mp': total_mp,
        'efectivo_esperado': efectivo_esperado,
    }
    return render(request, 'ventas/cerrar_caja.html', context)


@login_required
@solo_no_repartidor
@csrf_exempt
@transaction.atomic
def procesar_venta_ajax(request):
    """
    Procesa una venta desde el POS e integra facturación electrónica con ARCA / AFIP.
    Soporta Presupuestos, Remitos con Repartidor asignado y Facturación en ARCA.
    También permite facturar remitos existentes (desde_remitos=True).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)

    try:
        # 1. Parsear datos de la petición
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            items = data.get('items', [])
            metodo_pago = data.get('metodo_pago', 'EFECTIVO')
            cliente_id = data.get('cliente_id')
            monto_recibido = float(data.get('monto_recibido', 0))
            tipo_comprobante = int(data.get('tipo_comprobante', 6))
            repartidor_id = data.get('repartidor_id')
            vendedor_id = data.get('vendedor_id')
            accion_comprobante = data.get('accion_comprobante', 'REMITO')
            desde_remitos = data.get('desde_remitos', False)  # 🔽 NUEVO
            remito_ids = data.get('remito_ids', [])            # 🔽 NUEVO
        else:
            items_str = request.POST.get('items')
            if not items_str:
                return JsonResponse({'status': 'error', 'message': 'No se envió el carrito.'}, status=400)
            try:
                items = json.loads(items_str)
            except json.JSONDecodeError:
                return JsonResponse({'status': 'error', 'message': 'Carrito inválido.'}, status=400)
            metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO')
            cliente_id = request.POST.get('cliente_id')
            monto_recibido = float(request.POST.get('monto_recibido', 0))
            tipo_comprobante = int(request.POST.get('tipo_comprobante', 6))
            repartidor_id = request.POST.get('repartidor_id')
            vendedor_id = request.POST.get('vendedor_id')
            accion_comprobante = request.POST.get('accion_comprobante', 'REMITO')
            desde_remitos = request.POST.get('desde_remitos', 'false').lower() == 'true'
            remito_ids = request.POST.getlist('remito_ids')

        if not items:
            return JsonResponse({'status': 'error', 'message': 'El carrito está vacío.'}, status=400)

        # 2. Validar Turno de Caja Activo
        turno_activo = CajaTurno.objects.filter(vendedor=request.user, estado='ABIERTA').first()
        if not turno_activo:
            return JsonResponse({'status': 'error', 'message': 'No tienes una caja/turno abierto para vender.'}, status=400)

        # 3. Validar Repartidor (si fue enviado)
        repartidor_obj = None
        if repartidor_id:
            repartidor_obj = Usuario.objects.filter(id=repartidor_id, activo=True).first()

        # 3b. Validar Vendedor
        vendedor_obj = request.user
        if vendedor_id:
            try:
                candidato = Usuario.objects.filter(
                    id=int(vendedor_id),
                    rol__in=['vendedor', 'gerente', 'cajero'],
                    activo=True,
                ).first()
                if candidato:
                    vendedor_obj = candidato
                else:
                    logger.warning(f"vendedor_id {vendedor_id} no válido. Usando {request.user.username}.")
            except (ValueError, TypeError):
                logger.warning(f"vendedor_id inválido: {vendedor_id}")

        # 4. Determinar Estado, Tipo y Flags según Acción
        es_remito = False
        saldo_pendiente = Decimal('0.00')

        if accion_comprobante == 'PRESUPUESTO':
            estado_venta = 'PRESUPUESTO'
            tipo_comprobante_final = 0
        elif accion_comprobante == 'REMITO':
            es_remito = True
            tipo_comprobante_final = 0
            estado_venta = 'PENDIENTE_ENTREGA' if repartidor_obj else 'ENTREGADO'
        elif accion_comprobante == 'ENVIAR':
            tipo_comprobante_final = 0
            estado_venta = 'PENDIENTE_ENTREGA' if repartidor_obj else 'ENTREGADO'
        else:
            # TICKET o FACTURA
            estado_venta = 'COMPLETADO'
            tipo_comprobante_final = tipo_comprobante

        # 5. Procesar Ítems y Calcular Totales
        total_venta = Decimal('0.00')
        detalles_a_crear = []

        for item in items:
            prod_id = item.get('id')
            cantidad = int(item.get('cantidad', 1))
            if not prod_id:
                return JsonResponse({'status': 'error', 'message': 'Ítem sin ID de producto.'}, status=400)

            producto = Producto.objects.select_for_update().get(pk=prod_id)

            # 🔽 Si viene desde remitos, NO verificar stock (ya se descontó antes)
            if not desde_remitos:
                if producto.stock_actual < cantidad:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Stock insuficiente para "{producto.nombre}". Disponible: {producto.stock_actual}'
                    }, status=400)

            # 🔽 Si viene desde remitos, usar el precio que viene del remito
            if desde_remitos and 'precio' in item:
                precio = Decimal(str(item['precio']))
            else:
                precio = Decimal(str(producto.precio_venta))

            subtotal = precio * cantidad
            total_venta += subtotal

            detalles_a_crear.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio': precio,
                'subtotal': subtotal,
            })

        # 6. Calcular Vuelto
        monto_recibido = Decimal(str(monto_recibido))
        vuelto = max(Decimal('0.00'), monto_recibido - total_venta)

        # 7. Obtener datos del Cliente
        cliente_obj = None
        if cliente_id:
            cliente_obj = Cliente.objects.filter(id=cliente_id).first()

        # 8. Crear Registro de Venta
        if es_remito:
            saldo_pendiente = total_venta

        # 🔽 Si viene desde remitos, la nueva venta es una FACTURA (no remito)
        es_factura_de_remitos = False
        if desde_remitos and remito_ids:
            es_factura_de_remitos = True
            es_remito = False
            estado_venta = 'COMPLETADO'
            saldo_pendiente = total_venta  # queda pendiente de cobro
            estado_cobro_val = 'PENDIENTE'
        else:
            estado_cobro_val = 'PENDIENTE' if es_remito else 'COBRADO'

        venta = Venta.objects.create(
            turno=turno_activo,
            sucursal=turno_activo.sucursal,   # 🔽 NUEVO
            vendedor=vendedor_obj,
            repartidor=repartidor_obj,
            cliente=cliente_obj,
            metodo_pago=metodo_pago,
            total=total_venta,
            monto_recibido=monto_recibido,
            vuelto=vuelto,
            estado=estado_venta,
            tipo_comprobante=tipo_comprobante_final,
            es_remito=es_remito,
            es_factura_de_remitos=es_factura_de_remitos,
            estado_cobro=estado_cobro_val,
            saldo_pendiente=saldo_pendiente,
        )

        # 9. Crear Detalles de Venta
        for det in detalles_a_crear:
            prod = det['producto']
            cant = det['cantidad']

            DetalleVenta.objects.create(
                venta=venta,
                producto=prod,
                cantidad=cant,
                precio_unitario=det['precio'],
                subtotal=det['subtotal'],
            )

            # 🔽 SOLO descontar stock si NO viene desde remitos
            if not desde_remitos:
                # Descontar stock
                from apps.productos.models import StockSucursal

                # Stock global (compatibilidad)
                prod.stock_actual -= cant
                prod.save()

                # Stock por sucursal
                ss, _ = StockSucursal.objects.get_or_create(
                    producto=prod,
                    sucursal=turno_activo.sucursal,
                    defaults={'cantidad': 0}
                )
                ss.cantidad -= cant
                ss.save()

                motivo_movimiento = f'Venta POS #{venta.id} [{estado_venta}]'
                if repartidor_obj:
                    motivo_movimiento += f' - Asignado a Repartidor: {repartidor_obj.username}'

                MovimientoStock.objects.create(
                    producto=prod,
                    sucursal=turno_activo.sucursal,   # 🔽 NUEVO
                    tipo='VENTA',
                    cantidad=cant,
                    motivo=motivo_movimiento
                )

        # 9b. Vincular remitos originales a la factura
        if desde_remitos and remito_ids:
            remitos_originales = Venta.objects.filter(id__in=remito_ids, es_remito=True)
            if remitos_originales.exists():
                venta.remitos_facturados.set(remitos_originales)
                remitos_originales.update(
                    es_remito=False,
                    es_factura_de_remitos=True,
                )
                logger.info(f"Factura #{venta.id} agrupa {remitos_originales.count()} remitos: {remito_ids}")

        # 10. CONEXIÓN Y SOLICITUD DE CAE A ARCA / AFIP
        config = EmpresaConfig.objects.first()

        if (
            config
            and config.certificado_crt
            and config.clave_privada_key
            and config.cuit
            and tipo_comprobante_final != 0
            and accion_comprobante in ['TICKET', 'FACTURA']
        ):
            try:
                from pyafipws.wsaa import WSAA
                from pyafipws.wsfev1 import WSFEv1

                cert_path = config.certificado_crt.path
                key_path = config.clave_privada_key.path
                cuit = config.cuit.replace("-", "").strip()

                if config.ambiente_arca == 'PROD':
                    wsdl_wsaa = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
                    wsdl_wsfe = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"
                else:
                    wsdl_wsaa = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
                    wsdl_wsfe = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

                wsaa = WSAA()
                ta = wsaa.Autenticar("wsfe", cert_path, key_path, wsdl=wsdl_wsaa)

                wsfev1 = WSFEv1()
                wsfev1.Cuit = cuit
                wsfev1.SetTicketAcceso(ta)

                CACHE_DIR = os.path.join(settings.BASE_DIR, 'afip_cache')
                os.makedirs(CACHE_DIR, exist_ok=True)

                wsfev1.Conectar(wsdl=wsdl_wsfe, cache=CACHE_DIR)

                pto_vta = int(config.punto_de_venta or 1)
                cbte_nro = int(wsfev1.CompUltimoAutorizado(tipo_comprobante_final, pto_vta) or 0) + 1

                doc_tipo = 99
                doc_nro = 0

                if cliente_obj and cliente_obj.numero_documento:
                    doc_nro = cliente_obj.numero_documento.replace("-", "").strip()
                    if len(doc_nro) == 11:
                        doc_tipo = 80
                    elif len(doc_nro) == 8:
                        doc_tipo = 96
                    else:
                        doc_tipo = 99

                fecha_cbte = timezone.now().strftime("%Y%m%d")

                cond_iva_receptor = 5
                if cliente_obj and hasattr(cliente_obj, 'condicion_iva') and cliente_obj.condicion_iva:
                    try:
                        cond_iva_receptor = int(cliente_obj.condicion_iva)
                    except (ValueError, TypeError):
                        cond_iva_receptor = 5

                # ============================================================
                # Cálculo de IVA según tipo de comprobante
                # ============================================================
                # Factura A (1) y B (6): discriminan IVA 21%
                # Factura C (11): NO discrimina IVA (emisor Monotributista)
                # ============================================================

                if tipo_comprobante_final == 11:
                    # Factura C: no discrimina IVA
                    imp_neto = total_venta
                    imp_iva = Decimal('0.00')
                else:
                    # Factura A o B: discrimina IVA 21%
                    imp_neto = (total_venta / Decimal("1.21")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    imp_iva = (total_venta - imp_neto).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )

                wsfev1.CrearFactura(
                    concepto=1,
                    tipo_doc=doc_tipo,
                    nro_doc=doc_nro,
                    tipo_cbte=tipo_comprobante_final,
                    punto_vta=pto_vta,
                    cbt_desde=cbte_nro,
                    cbt_hasta=cbte_nro,
                    imp_total=float(total_venta),
                    imp_tot_conc=0.0,
                    imp_neto=float(imp_neto),
                    imp_iva=float(imp_iva),
                    imp_trib=0.0,
                    imp_op_ex=0.0,
                    fecha_cbte=fecha_cbte,
                )

                try:
                    wsfev1.EstablecerCampoFactura("condicion_iva_receptor_id", str(cond_iva_receptor))
                    wsfev1.EstablecerCampoFactura("cancela_misma_moneda_ext", "N")
                except Exception as e:
                    logger.warning(f"No se pudo establecer condicion_iva_receptor_id: {e}")

                # 🔽 Agregar alícuota de IVA SOLO para Facturas A y B (no para C)
                if tipo_comprobante_final != 11:
                    wsfev1.AgregarIva(5, float(imp_neto), float(imp_iva))
                    logger.info(f"IVA agregado: neto={imp_neto}, iva={imp_iva}")
                else:
                    logger.info(f"Comprobante tipo C (11): NO se agrega IVA")

                wsfev1.CAESolicitar()

                cae_obtenido = getattr(wsfev1, "CAE", None)
                vencimiento_obtenido = getattr(wsfev1, "Vencimiento", None)

                if cae_obtenido:
                    venta.cae = str(cae_obtenido)
                    if vencimiento_obtenido:
                        try:
                            venta.vencimiento_cae = datetime.strptime(str(vencimiento_obtenido), "%Y%m%d").date()
                        except ValueError:
                            logger.warning(f"No se pudo parsear la fecha de vencimiento: {vencimiento_obtenido}")
                    venta.numero_comprobante = cbte_nro
                    venta.tipo_comprobante = tipo_comprobante_final
                    venta.save()
                    logger.info(f"CAE Autorizado para Venta #{venta.id}: {cae_obtenido}")
                else:
                    resultado = getattr(wsfev1, "Resultado", "Desconocido")
                    obs = getattr(wsfev1, "Obs", "Sin observaciones")
                    logger.error(f"Respuesta ARCA sin CAE. Resultado: {resultado}, Obs: {obs}")

            except Exception as afip_err:
                logger.exception(f"Excepción al conectar con ARCA/AFIP: {afip_err}")

        # 11. Respuesta exitosa
        return JsonResponse({
            'status': 'success',
            'message': 'Operación procesada correctamente.',
            'venta_id': venta.id,
            'estado': venta.estado,
            'estado_display': venta.get_estado_display(),
            'total': float(total_venta),
            'vuelto': float(vuelto),
            'cae': venta.cae if venta.cae else None,
            'repartidor': repartidor_obj.username if repartidor_obj else None,
            'desde_remitos': desde_remitos,
        })

    except Exception as e:
        logger.exception("Error inesperado en procesar_venta_ajax")
        return JsonResponse({'status': 'error', 'message': f'Error interno: {str(e)}'}, status=500)


@login_required
@solo_no_repartidor
def crear_cliente(request):
    """Vista para crear un nuevo cliente. Si el CUIT ya existe, actualiza en vez de duplicar."""
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        cuit_dni = request.POST.get('cuit_dni')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email')
        direccion = request.POST.get('direccion')
        condicion_iva = request.POST.get('condicion_iva') or 'Consumidor Final'

        # Buscar cliente existente por CUIT/DNI
        cliente_existente = None
        if cuit_dni:
            cliente_existente = Cliente.objects.filter(numero_documento=cuit_dni).first()

        if cliente_existente:
            cliente_existente.nombre = nombre
            cliente_existente.telefono = telefono
            cliente_existente.email = email
            cliente_existente.direccion = direccion
            cliente_existente.condicion_iva = condicion_iva
            cliente_existente.save()
            messages.success(request, f'Cliente "{nombre}" ya existía. Se actualizaron sus datos.')
        else:
            Cliente.objects.create(
                nombre=nombre,
                numero_documento=cuit_dni,
                condicion_iva=condicion_iva,
                telefono=telefono,
                email=email,
                direccion=direccion
            )
            messages.success(request, 'Cliente registrado correctamente.')

        next_url = request.GET.get('next') or request.POST.get('next') or 'ventas:pos'
        return redirect(next_url)

    return render(request, 'ventas/crear_cliente.html')


@login_required
def comprobante_ticket(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    config = EmpresaConfig.objects.first()
    return render(
        request,
        "ventas/ticket_imprimible.html",
        {"venta": venta, "config": config},
    )


@login_required
def comprobante_factura(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    config = EmpresaConfig.objects.first()
    return render(
        request,
        "ventas/factura_imprimible.html",
        {"venta": venta, "config": config},
    )


@login_required
def enviar_email_comprobante(request, venta_id):
    """Envío de comprobante por correo electrónico."""
    if request.method == 'POST':
        return JsonResponse({'success': True, 'message': 'Comprobante enviado.'})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})


@login_required
@solo_no_repartidor
def reportes_view(request):
    from datetime import datetime, date

    hoy = timezone.now()

    # 🔽 Leer filtros
    mes_sel = request.GET.get('mes', '')
    anio_sel = request.GET.get('anio', '')
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    modo = request.GET.get('modo', 'mes')  # 'mes' o 'rango'

    # Base: todas las ventas
    ventas_periodo = Venta.objects.all()
    detalles_periodo = DetalleVenta.objects.all()

    rango_descripcion = ""

    # 🔽 Modo 1: Por rango de fechas
    if modo == 'rango' and (fecha_desde or fecha_hasta):
        if fecha_desde:
            ventas_periodo = ventas_periodo.filter(fecha__date__gte=fecha_desde)
            detalles_periodo = detalles_periodo.filter(venta__fecha__date__gte=fecha_desde)
        if fecha_hasta:
            ventas_periodo = ventas_periodo.filter(fecha__date__lte=fecha_hasta)
            detalles_periodo = detalles_periodo.filter(venta__fecha__date__lte=fecha_hasta)

        rango_descripcion = f"Desde {fecha_desde or 'inicio'} hasta {fecha_hasta or 'hoy'}"
        mes_sel = ''
        anio_sel = ''

    # 🔽 Modo 2: Por mes y año (comportamiento original)
    else:
        try:
            mes_sel = int(mes_sel) if mes_sel else hoy.month
            anio_sel = int(anio_sel) if anio_sel else hoy.year
        except (ValueError, TypeError):
            mes_sel = hoy.month
            anio_sel = hoy.year

        ventas_periodo = ventas_periodo.filter(fecha__month=mes_sel, fecha__year=anio_sel)
        detalles_periodo = detalles_periodo.filter(
            venta__fecha__month=mes_sel,
            venta__fecha__year=anio_sel,
        )
        rango_descripcion = f"{mes_sel}/{anio_sel}"

    # 1. TOTALES DEL PERÍODO Y GANANCIA REAL
    total_recaudado = ventas_periodo.aggregate(Sum('total'))['total__sum'] or 0
    total_operaciones = ventas_periodo.count()

    ganancia_real = detalles_periodo.aggregate(
        ganancia=Sum(F('cantidad') * (F('precio_unitario') - F('producto__precio_costo')))
    )['ganancia'] or 0

    margen_porcentaje = (ganancia_real / total_recaudado * 100) if total_recaudado > 0 else 0
    ticket_promedio = (total_recaudado / total_operaciones) if total_operaciones > 0 else 0

    # 2. DESGLOSE POR MEDIOS DE PAGO
    medios_pago = ventas_periodo.values('metodo_pago').annotate(
        total=Sum('total'),
        cantidad=Count('id')
    ).order_by('-total')

    # 3. TOP PRODUCTOS
    productos_top = detalles_periodo.values(
        'producto__nombre', 'producto__codigo_barra'
    ).annotate(
        unidades=Sum('cantidad'),
        recaudado=Sum(F('cantidad') * F('precio_unitario'))
    ).order_by('-unidades')[:5]

    # 4. RANKING DE VENDEDORES
    vendedores_top = ventas_periodo.values(
        'vendedor__username'
    ).annotate(
        ventas_count=Count('id'),
        total_monto=Sum('total')
    ).order_by('-total_monto')

    # 5. PROVEEDORES MÁS DEMANDADOS
    proveedores_top = detalles_periodo.filter(
        producto__proveedor__isnull=False
    ).values(
        'producto__proveedor__nombre_o_razon_social'
    ).annotate(
        unidades_vendidas=Sum('cantidad'),
        total_generado=Sum(F('cantidad') * F('precio_unitario'))
    ).order_by('-unidades_vendidas')[:5]

    context = {
        'mes_sel': mes_sel,
        'anio_sel': anio_sel,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'modo': modo,
        'rango_descripcion': rango_descripcion,
        'anios_disponibles': range(hoy.year, 2023, -1),
        'total_recaudado': total_recaudado,
        'total_operaciones': total_operaciones,
        'ganancia_real': ganancia_real,
        'margen_porcentaje': margen_porcentaje,
        'ticket_promedio': ticket_promedio,
        'medios_pago': medios_pago,
        'productos_top': productos_top,
        'vendedores_top': vendedores_top,
        'proveedores_top': proveedores_top,
    }
    return render(request, 'ventas/reportes.html', context)

@login_required
@solo_no_repartidor
def pos_view(request):
    turno_activo = CajaTurno.objects.filter(
        vendedor=request.user, estado='ABIERTA'
    ).select_related('sucursal').first()

    if not turno_activo:
        return redirect('ventas:abrir_caja')

    clientes = Cliente.objects.all()
    repartidores = PerfilRepartidor.objects.filter(activo=True).select_related('user')

    vendedores = Usuario.objects.filter(
        rol__in=['vendedor', 'gerente', 'cajero'],
        activo=True,
    ).order_by('first_name', 'username')

    config = EmpresaConfig.objects.first()
    condicion_iva_emisor = config.condicion_iva if config else 'MO'

    context = {
        'clientes': clientes,
        'repartidores': repartidores,
        'vendedores': vendedores,
        'turno_activo': turno_activo,
        'sucursal_actual': turno_activo.sucursal,   # 🔽 NUEVO
        'condicion_iva_emisor': condicion_iva_emisor,
    }
    return render(request, 'ventas/pos.html', context)

@login_required
def mis_pedidos_view(request):
    """Muestra la lista de entregas y ventas asignadas al repartidor que tiene la sesión iniciada."""
    
    # 🔹 Filtrar solo las ventas asignadas a este repartidor en particular
    pedidos = Venta.objects.filter(
        repartidor=request.user
    ).exclude(
        estado='CANCELADO'
    ).select_related('cliente').prefetch_related('detalles__producto').order_by('-fecha')

    context = {
        'pedidos': pedidos,
    }
    return render(request, 'ventas/mis_pedidos.html', context)


@login_required
@csrf_exempt
def marcar_entregado_ajax(request, venta_id):
    """Marca el pedido como ENTREGADO desde el celular del repartidor."""
    if request.method == 'POST':
        venta = get_object_or_404(Venta, id=venta_id, repartidor=request.user)
        venta.estado = 'ENTREGADO'
        venta.fecha_entrega = timezone.now()
        venta.save()
        return JsonResponse({'status': 'success', 'message': 'Entrega registrada.'})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)

@login_required
def detalle_entrega_view(request, venta_id):
    """Muestra la vista detallada de una entrega específica para el repartidor con geolocalización."""
    venta = get_object_or_404(Venta, id=venta_id)
    
    # Determinar la dirección a mostrar
    direccion = venta.direccion_entrega
    if not direccion and venta.cliente:
        direccion = venta.cliente.direccion
    if not direccion:
        direccion = "Sin dirección registrada"

    return render(request, 'ventas/detalle_entrega.html', {
        'pedido': venta,
        'direccion': direccion,
    })

@login_required
@solo_no_repartidor
def consultar_padron_ajax(request):
    """
    Consulta el padrón de ARCA/AFIP por CUIT y devuelve los datos del contribuyente
    para autocompletar el formulario de nuevo cliente.
    Maneja errores de forma amigable: CUIT no encontrado, problemas de conexión, etc.
    """
    import os
    from django.conf import settings
    from apps.configuracion.models import EmpresaConfig
    from pyafipws.wsaa import WSAA
    from pyafipws.ws_sr_padron import WSSrPadronA5

    # 1. Validar el CUIT entrante
    cuit = request.GET.get('cuit', '').strip().replace('-', '').replace(' ', '')
    if not cuit or len(cuit) != 11 or not cuit.isdigit():
        return JsonResponse({
            'success': False,
            'error': 'CUIT inválido. Debe tener 11 dígitos numéricos.',
            'tipo': 'validacion'
        })

    # 2. Verificar configuración de ARCA
    config = EmpresaConfig.objects.first()
    if not config or not config.certificado_crt or not config.clave_privada_key or not config.cuit:
        return JsonResponse({
            'success': False,
            'error': 'Falta configurar el certificado de ARCA en EmpresaConfig.',
            'tipo': 'configuracion'
        })

    # 3. Elegir URLs según ambiente (PROD / HOMO)
    try:
        cert_path = config.certificado_crt.path
        key_path = config.clave_privada_key.path
        cuit_emisor = config.cuit.replace("-", "").strip()

        if getattr(config, 'ambiente_arca', 'HOMO') == 'PROD':
            wsdl_wsaa = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
            wsdl_padron = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?WSDL"
        else:
            wsdl_wsaa = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
            wsdl_padron = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?WSDL"
    except Exception as e:
        logger.exception("Error leyendo configuración de ARCA")
        return JsonResponse({
            'success': False,
            'error': 'Error leyendo la configuración de ARCA.',
            'tipo': 'configuracion'
        })

    # 4. Autenticación WSAA
    try:
        wsaa = WSAA()
        ta = wsaa.Autenticar(
            "ws_sr_constancia_inscripcion",
            cert_path,
            key_path,
            wsdl=wsdl_wsaa,
        )
    except Exception as e:
        logger.exception(f"Error autenticando con WSAA: {e}")
        return JsonResponse({
            'success': False,
            'error': 'No se pudo autenticar con ARCA. Verificá el certificado.',
            'tipo': 'autenticacion'
        })

    # 5. Inicializar cliente del padrón
    try:
        padron = WSSrPadronA5()
        padron.Cuit = cuit_emisor
        padron.SetTicketAcceso(ta)

        CACHE_DIR = os.path.join(settings.BASE_DIR, 'afip_cache')
        os.makedirs(CACHE_DIR, exist_ok=True)

        # Preferir WSDL local si existe (evita problemas con httplib2)
        wsdl_local = os.path.join(settings.BASE_DIR, 'wsdl_cache', 'personaServiceA5.wsdl')
        wsdl_usar = wsdl_local if os.path.exists(wsdl_local) else wsdl_padron

        padron.Conectar(wsdl=wsdl_usar, cache=CACHE_DIR)
    except Exception as e:
        logger.exception(f"Error conectando al padrón: {e}")
        return JsonResponse({
            'success': False,
            'error': 'No se pudo conectar con el servicio de padrón de ARCA.',
            'tipo': 'conexion'
        })

    # 6. Consultar el CUIT — manejar los errores específicos
    try:
        padron.Consultar(cuit)
    except Exception as soap_err:
        msg = str(soap_err).lower()

        # CUIT no existe en el padrón
        if "no existe persona" in msg or "no existe" in msg:
            return JsonResponse({
                'success': False,
                'error': 'El CUIT no está registrado en el padrón de ARCA. Verificá el número o cargá los datos manualmente.',
                'tipo': 'no_encontrado'
            })

        # Otros errores de SOAP
        logger.exception(f"Error SOAP consultando padrón para CUIT {cuit}: {soap_err}")
        return JsonResponse({
            'success': False,
            'error': 'ARCA rechazó la consulta. Intentá nuevamente en unos minutos.',
            'tipo': 'soap'
        })

    # 7. Verificar que la respuesta traiga datos
    if not getattr(padron, 'denominacion', None):
        return JsonResponse({
            'success': False,
            'error': 'El CUIT no devolvió datos del padrón. Puede estar inactivo o sin información pública.',
            'tipo': 'sin_datos'
        })

    # 8. Determinar Condición IVA según los impuestos devueltos
    # Códigos de impuestos según tabla de ARCA:
    #   30 = IVA (Responsable Inscripto)
    #   32 = IVA Exento
    #   301, 302, 303, etc. = variantes de Monotributo
    impuestos = padron.impuestos or []
    condicion_iva = 'Consumidor Final'  # valor por defecto (coincide con el <option>)

    if 30 in impuestos or 301 in impuestos:
        condicion_iva = 'Responsable Inscripto'
    elif 32 in impuestos:
        condicion_iva = 'Exento'
    elif any(i in impuestos for i in [302, 303, 306, 307, 308, 309, 310, 311]):
        condicion_iva = 'Monotributo'

    # 9. Armar dirección completa
    direccion_partes = [
        getattr(padron, 'direccion', '') or '',
        getattr(padron, 'localidad', '') or '',
        getattr(padron, 'provincia', '') or '',
        getattr(padron, 'cod_postal', '') or '',
    ]
    direccion = ", ".join([p.strip() for p in direccion_partes if p.strip()])

    # 10. Devolver JSON de éxito
    return JsonResponse({
        'success': True,
        'data': {
            'nombre': padron.denominacion or '',
            'numero_documento': cuit,
            'tipo_documento': 'CUIT',
            'direccion': direccion,
            'condicion_iva': condicion_iva,
            'provincia': getattr(padron, 'provincia', '') or '',
            'codigo_postal': getattr(padron, 'cod_postal', '') or '',
            'impuestos': impuestos,
        }
    })

@login_required
@solo_admin
@csrf_exempt
def anular_venta_ajax(request, venta_id):
    """
    Emite una Nota de Crédito que anula una venta existente.
    Solo administradores / superusuarios pueden hacerlo.
    """
    # 1. Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        return JsonResponse({
            'success': False,
            'error': 'No tenés permisos para anular comprobantes.'
        }, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    # 2. Obtener la venta original
    try:
        venta_original = Venta.objects.get(id=venta_id)
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Comprobante no encontrado.'}, status=404)

    # 3. Validaciones
    if venta_original.es_nota_credito:
        return JsonResponse({'success': False, 'error': 'No se puede anular una Nota de Crédito.'})

    if venta_original.notas_credito.exists():
        return JsonResponse({'success': False, 'error': 'Esta venta ya tiene una Nota de Crédito asociada.'})

    if venta_original.estado == 'CANCELADO':
        return JsonResponse({'success': False, 'error': 'Esta venta ya está cancelada.'})

    # 4. Determinar tipo de NC según tipo de factura original
    # 1 (Fact A) → 3 (NC A); 6 (Fact B) → 8 (NC B); 11 (Fact C) → 13 (NC C)
    mapa_nc = {1: 3, 6: 8, 11: 13}
    tipo_nc = mapa_nc.get(venta_original.tipo_comprobante, 13)  # por defecto NC C

    motivo = request.POST.get('motivo', 'Anulación por administrador')

    try:
        with transaction.atomic():
            # Crear la Nota de Crédito
            nc = Venta.objects.create(
                turno=venta_original.turno,
                vendedor=request.user,
                cliente=venta_original.cliente,
                metodo_pago=venta_original.metodo_pago,
                total=venta_original.total,
                estado='COMPLETADO',
                tipo_comprobante=tipo_nc,
                es_nota_credito=True,
                venta_original=venta_original,
                motivo_anulacion=motivo,
            )

            # Marcar la venta original como cancelada
            venta_original.estado = 'CANCELADO'
            venta_original.save()

        return JsonResponse({
            'success': True,
            'message': 'Nota de Crédito emitida correctamente.',
            'nc_id': nc.id,
            'venta_original_id': venta_original.id,
        })

    except Exception as e:
        logger.exception(f"Error al anular venta {venta_id}")
        return JsonResponse({'success': False, 'error': f'Error: {str(e)}'}, status=500)

@login_required
@solo_no_repartidor
def remitos_pendientes_view(request):
    """
    Lista todos los remitos emitidos que aún no fueron facturados.
    Permite filtrar por cliente y rango de fechas, y seleccionar varios
    para facturar en conjunto.
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum, Count

    # Base: remitos pendientes de facturar y cobrar
    remitos = Venta.objects.filter(
        es_remito=True,
        estado__in=['COMPLETADO', 'ENTREGADO', 'PENDIENTE_ENTREGA'],
        estado_cobro__in=['PENDIENTE', 'PARCIAL'],
    ).exclude(
        estado='CANCELADO'
    ).select_related('cliente', 'vendedor', 'repartidor').order_by('-fecha')

    # Filtros
    cliente_id = request.GET.get('cliente', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    solo_vencidos = request.GET.get('solo_vencidos', '') == '1'

    if cliente_id:
        remitos = remitos.filter(cliente_id=cliente_id)
    if fecha_desde:
        remitos = remitos.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        remitos = remitos.filter(fecha__date__lte=fecha_hasta)
    if solo_vencidos:
        hace_7_dias = timezone.now() - timedelta(days=7)
        remitos = remitos.filter(fecha__lt=hace_7_dias)

    # Totales
    total_general = remitos.aggregate(total=Sum('total'))['total'] or 0
    cantidad = remitos.count()

    # Clientes que tienen remitos pendientes (para el filtro)
    clientes_con_remitos = Cliente.objects.filter(
        ventas__es_remito=True,
        ventas__estado__in=['COMPLETADO', 'ENTREGADO', 'PENDIENTE_ENTREGA'],
        ventas__estado_cobro__in=['PENDIENTE', 'PARCIAL'],
    ).distinct().order_by('nombre')

    # Paginación
    paginator = Paginator(remitos, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'total_general': total_general,
        'cantidad': cantidad,
        'clientes_con_remitos': clientes_con_remitos,
        'cliente_id': cliente_id,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'solo_vencidos': solo_vencidos,
    }
    return render(request, 'ventas/remitos_pendientes.html', context)

@login_required
@solo_no_repartidor
def cuentas_corrientes_view(request):
    """
    Lista de clientes con saldo pendiente (cuenta corriente global).
    """
    from django.db.models import Sum, Count, Q

    # Filtro
    solo_con_deuda = request.GET.get('con_deuda', '1') == '1'
    busqueda = request.GET.get('q', '').strip()

    # Base: todos los clientes
    clientes = Cliente.objects.all()

    if busqueda:
        clientes = clientes.filter(
            Q(nombre__icontains=busqueda) |
            Q(numero_documento__icontains=busqueda)
        )

    # Anotar saldo pendiente por cliente
    # (suma de saldo_pendiente de sus facturas/remitos pendientes)
    clientes = clientes.annotate(
        saldo_total=Sum(
            'ventas__saldo_pendiente',
            filter=Q(
                ventas__estado_cobro__in=['PENDIENTE', 'PARCIAL'],
                ventas__es_nota_credito=False,
                ventas__estado__in=['COMPLETADO', 'ENTREGADO', 'PENDIENTE_ENTREGA'],
            )
        ),
        facturas_pendientes=Count(
            'ventas',
            filter=Q(
                ventas__estado_cobro__in=['PENDIENTE', 'PARCIAL'],
                ventas__es_nota_credito=False,
            )
        ),
    )

    # Filtrar solo con deuda
    if solo_con_deuda:
        clientes = clientes.filter(saldo_total__gt=0)

    clientes = clientes.order_by('-saldo_total', 'nombre')

    # KPIs globales
    total_deuda = clientes.aggregate(total=Sum('saldo_total'))['total'] or 0
    cantidad_con_deuda = clientes.filter(saldo_total__gt=0).count()

    context = {
        'clientes': clientes,
        'total_deuda': total_deuda,
        'cantidad_con_deuda': cantidad_con_deuda,
        'solo_con_deuda': solo_con_deuda,
        'busqueda': busqueda,
    }
    return render(request, 'ventas/cuentas_corrientes.html', context)

@login_required
@solo_no_repartidor
def cuenta_corriente_cliente_view(request, cliente_id):
    """Placeholder - Sub-fase 3B."""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    return render(request, 'ventas/cuenta_corriente_cliente.html', {'cliente': cliente})


@login_required
@solo_no_repartidor
def registrar_pago_view(request, cliente_id):
    """
    Registra un pago del cliente.
    - Si viene ?factura=<id>: preselecciona ese comprobante.
    - Si no: muestra todos los comprobantes pendientes para elegir.
    """
    from django.db.models import Sum

    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Comprobantes pendientes (FIFO)
    pendientes = Venta.objects.filter(
        cliente=cliente,
        es_nota_credito=False,
        estado_cobro__in=['PENDIENTE', 'PARCIAL'],
    ).exclude(
        estado='CANCELADO'
    ).order_by('fecha')

    # Comprobante preseleccionado (si viene ?factura=)
        # Comprobante preseleccionado (si viene ?factura=)
    factura_preseleccionada = None
    factura_id = request.GET.get('factura', '').strip()

    logger.info(f"DEBUG registrar_pago: factura_id recibido = '{factura_id}'")

    if factura_id and factura_id.isdigit():
        factura_preseleccionada = pendientes.filter(id=int(factura_id)).first()
        logger.info(f"DEBUG registrar_pago: factura_preseleccionada = {factura_preseleccionada}")
    else:
        logger.info(f"DEBUG registrar_pago: sin factura preseleccionada")

    saldo_total = pendientes.aggregate(t=Sum('saldo_pendiente'))['t'] or Decimal('0.00')

    if request.method == 'POST':
        try:
            monto = Decimal(str(request.POST.get('monto', 0)))
        except (ValueError, TypeError):
            messages.error(request, 'Monto inválido.')
            return redirect('ventas:registrar_pago', cliente_id=cliente_id)

        metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO')
        observaciones = request.POST.get('observaciones', '').strip()

        # 🔽 NUEVO: comprobantes seleccionados
        comprobantes_seleccionados = request.POST.getlist('comprobantes')

        if monto <= 0:
            messages.error(request, 'El monto debe ser mayor a cero.')
            return redirect('ventas:registrar_pago', cliente_id=cliente_id)

        # 🔽 Filtrar qué comprobantes aplicar
        if comprobantes_seleccionados:
            # Solo los seleccionados
            try:
                ids_seleccionados = [int(x) for x in comprobantes_seleccionados]
                pendientes_a_aplicar = pendientes.filter(id__in=ids_seleccionados)
            except (ValueError, TypeError):
                messages.error(request, 'Comprobantes inválidos.')
                return redirect('ventas:registrar_pago', cliente_id=cliente_id)

            saldo_aplicable = pendientes_a_aplicar.aggregate(t=Sum('saldo_pendiente'))['t'] or Decimal('0.00')
        else:
            # Aplicar a todos (FIFO)
            pendientes_a_aplicar = pendientes
            saldo_aplicable = saldo_total

        if monto > saldo_aplicable:
            messages.warning(
                request,
                f'El monto (${monto}) supera el saldo seleccionado (${saldo_aplicable}). '
                f'Se aplicará solo ${saldo_aplicable}.'
            )
            monto = saldo_aplicable

        try:
            with transaction.atomic():
                # 1. Crear el Pago
                pago = Pago.objects.create(
                    cliente=cliente,
                    monto=monto,
                    metodo_pago=metodo_pago,
                    observaciones=observaciones,
                    registrado_por=request.user,
                )

                # 2. Aplicar el pago FIFO a los comprobantes
                restante = monto
                comprobantes_afectados = []

                for comp in pendientes_a_aplicar:
                    if restante <= 0:
                        break

                    saldo_comp = comp.saldo_pendiente

                    if restante >= saldo_comp:
                        comp.saldo_pendiente = Decimal('0.00')
                        comp.estado_cobro = 'COBRADO'
                        restante -= saldo_comp
                    else:
                        comp.saldo_pendiente = saldo_comp - restante
                        comp.estado_cobro = 'PARCIAL'
                        restante = Decimal('0.00')

                    comp.save()
                    comprobantes_afectados.append(comp.id)

                # 3. Asociar el pago al último comprobante afectado
                if comprobantes_afectados:
                    pago.factura_id = comprobantes_afectados[-1]
                    pago.save()

                logger.info(
                    f"Pago #{pago.id} de ${monto} aplicado a cliente {cliente.id}. "
                    f"Comprobantes afectados: {comprobantes_afectados}"
                )

            messages.success(
                request,
                f'Pago de ${monto} registrado correctamente. '
                f'Se aplicó a {len(comprobantes_afectados)} comprobante(s).'
            )
            return redirect('ventas:cuenta_corriente_cliente', cliente_id=cliente_id)

        except Exception as e:
            logger.exception(f"Error registrando pago para cliente {cliente_id}")
            messages.error(request, f'Error al registrar el pago: {str(e)}')

    context = {
        'cliente': cliente,
        'pendientes': pendientes,
        'saldo_total': saldo_total,
        'factura_preseleccionada': factura_preseleccionada,  # 🔽 NUEVO
    }
    return render(request, 'ventas/registrar_pago.html', context)

@login_required
@solo_no_repartidor
def obtener_detalles_remitos_ajax(request):
    """Devuelve los detalles de los remitos para armar un carrito y facturarlos."""
    ids_str = request.GET.get('ids', '').strip()
    if not ids_str:
        return JsonResponse({'success': False, 'error': 'No se enviaron remitos.'})

    try:
        ids = [int(x) for x in ids_str.split(',') if x.strip()]
    except ValueError:
        return JsonResponse({'success': False, 'error': 'IDs inválidos.'})

    remitos = Venta.objects.filter(id__in=ids, es_remito=True).prefetch_related('detalles__producto')
    if not remitos.exists():
        return JsonResponse({'success': False, 'error': 'No se encontraron remitos.'})

    # Validar mismo cliente
    clientes_ids = set(r.cliente_id for r in remitos)
    if len(clientes_ids) > 1:
        return JsonResponse({'success': False, 'error': 'Todos los remitos deben ser del mismo cliente.'})

    # Armar items
    items = []
    for remito in remitos:
        for d in remito.detalles.all():
            items.append({
                'id': d.producto.id,
                'nombre': d.producto.nombre,
                'precio': float(d.precio_unitario),
                'cantidad': d.cantidad,
            })

    primer = remitos.first()

    # Determinar tipo de comprobante según emisor y cliente
    config = EmpresaConfig.objects.first()
    tipo_comprobante = 6  # por defecto Factura B
    if config and config.condicion_iva == 'MO':
        tipo_comprobante = 11  # Monotributo emite C
    elif config and config.condicion_iva == 'RI':
        tipo_comprobante = 6  # RI emite B a consumidor final

    return JsonResponse({
        'success': True,
        'items': items,
        'cliente_id': primer.cliente_id,
        'vendedor_id': primer.vendedor_id,
        'metodo_pago': primer.metodo_pago,
        'tipo_comprobante': tipo_comprobante,
    })

@login_required
@solo_no_repartidor
def cuenta_corriente_cliente_view(request, cliente_id):
    """
    Muestra el detalle completo de la cuenta corriente de un cliente:
    - Resumen: saldo actual, total facturado, total pagado
    - Movimientos: facturas y pagos ordenados cronológicamente
    - Comprobantes pendientes de cobro
    """
    from django.db.models import Sum, Q

    cliente = get_object_or_404(Cliente, id=cliente_id)

    # ---- 1. Resumen general ----
    facturas_pendientes = Venta.objects.filter(
        cliente=cliente,
        es_remito=False,
        es_nota_credito=False,
        estado_cobro__in=['PENDIENTE', 'PARCIAL'],
        estado__in=['COMPLETADO', 'ENTREGADO'],
    )

    remitos_pendientes = Venta.objects.filter(
        cliente=cliente,
        es_remito=True,
        estado_cobro__in=['PENDIENTE', 'PARCIAL'],
        estado__in=['COMPLETADO', 'ENTREGADO', 'PENDIENTE_ENTREGA'],
    )

    total_facturado = Venta.objects.filter(
        cliente=cliente,
        es_nota_credito=False,
        es_remito=False,
    ).aggregate(t=Sum('total'))['t'] or 0

    total_pagado = Pago.objects.filter(
        cliente=cliente,
    ).aggregate(t=Sum('monto'))['t'] or 0

    saldo_pendiente = cliente.saldo_cuenta_corriente

    # ---- 2. Movimientos (facturas + pagos) ----
    movimientos = []

    # Facturas y remitos
    docs = Venta.objects.filter(
        cliente=cliente,
        es_nota_credito=False,
    ).exclude(
        estado='CANCELADO'
    ).select_related('vendedor').order_by('fecha')

    for d in docs:
        movimientos.append({
            'tipo': 'documento',
            'fecha': d.fecha,
            'documento': d,
            'debe': d.total if not d.es_remito else 0,
            'haber': 0,
            'saldo_parcial': d.saldo_pendiente,
            'es_remito': d.es_remito,
            'estado_cobro': d.estado_cobro,
        })

    # Pagos
    pagos = Pago.objects.filter(
        cliente=cliente,
    ).select_related('factura').order_by('fecha')

    for p in pagos:
        movimientos.append({
            'tipo': 'pago',
            'fecha': p.fecha,
            'pago': p,
            'debe': 0,
            'haber': p.monto,
            'saldo_parcial': 0,
        })

    # Ordenar cronológicamente
    movimientos.sort(key=lambda x: x['fecha'], reverse=True)

    # ---- 3. Comprobantes pendientes (para el botón de cobro) ----
    pendientes = Venta.objects.filter(
        Q(cliente=cliente),
        Q(es_remito=True) | Q(es_remito=False),
        estado_cobro__in=['PENDIENTE', 'PARCIAL'],
        es_nota_credito=False,
    ).exclude(
        estado='CANCELADO'
    ).order_by('fecha')

    context = {
        'cliente': cliente,
        'total_facturado': total_facturado,
        'total_pagado': total_pagado,
        'saldo_pendiente': saldo_pendiente,
        'movimientos': movimientos,
        'pendientes': pendientes,
        'cantidad_pendientes': pendientes.count(),
    }
    return render(request, 'ventas/cuenta_corriente_cliente.html', context)


# =========================================================
# GESTIÓN DE REPARTIDORES
# =========================================================

@login_required
@solo_no_repartidor
def lista_repartidores_view(request):
    """Lista todos los repartidores con sus datos."""
    from django.db.models import Q

    busqueda = request.GET.get('q', '').strip()
    filtro_activo = request.GET.get('activo', '1')  # por defecto, solo activos

    perfiles = PerfilRepartidor.objects.select_related('user').all()

    if busqueda:
        perfiles = perfiles.filter(
            Q(user__username__icontains=busqueda) |
            Q(user__first_name__icontains=busqueda) |
            Q(user__last_name__icontains=busqueda) |
            Q(dni__icontains=busqueda) |
            Q(zona__icontains=busqueda) |
            Q(vehiculo__icontains=busqueda)
        )

    if filtro_activo == '1':
        perfiles = perfiles.filter(activo=True)

    perfiles = perfiles.order_by('user__first_name', 'user__last_name', 'user__username')

    context = {
        'repartidores': perfiles,
        'busqueda': busqueda,
        'filtro_activo': filtro_activo,
        'total': perfiles.count(),
    }
    return render(request, 'ventas/lista_repartidores.html', context)


@login_required
@solo_no_repartidor
def crear_repartidor_view(request):
    """Crea un nuevo User con rol='repartidor' + su PerfilRepartidor."""
    from django.contrib.auth.hashers import make_password
    from django.db import transaction

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()

        dni = request.POST.get('dni', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        vehiculo = request.POST.get('vehiculo', '').strip()
        patente = request.POST.get('patente', '').strip()
        zona = request.POST.get('zona', '').strip()
        licencia_conducir = request.POST.get('licencia_conducir', '').strip()
        activo = request.POST.get('activo') == 'on'
        observaciones = request.POST.get('observaciones', '').strip()

        # Validaciones
        errores = []
        if not username:
            errores.append('El nombre de usuario es obligatorio.')
        elif Usuario.objects.filter(username=username).exists():
            errores.append(f'El username "{username}" ya está en uso.')
        if not password:
            errores.append('La contraseña es obligatoria.')
        if not first_name:
            errores.append('El nombre es obligatorio.')
        if not last_name:
            errores.append('El apellido es obligatorio.')

        if errores:
            for err in errores:
                messages.error(request, err)
            return render(request, 'ventas/crear_repartidor.html', {
                'form_data': request.POST,
            })

        try:
            with transaction.atomic():
                user = Usuario.objects.create(
                    username=username,
                    password=make_password(password),
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    rol='repartidor',
                    activo=True,
                    is_active=True,
                )

                PerfilRepartidor.objects.create(
                    user=user,
                    dni=dni,
                    telefono=telefono,
                    vehiculo=vehiculo,
                    patente=patente,
                    zona=zona,
                    licencia_conducir=licencia_conducir,
                    activo=activo,
                    observaciones=observaciones,
                )

            messages.success(request, f'Repartidor "{first_name} {last_name}" creado correctamente.')
            return redirect('ventas:lista_repartidores')

        except Exception as e:
            logger.exception(f"Error creando repartidor: {e}")
            messages.error(request, f'Error al crear repartidor: {str(e)}')
            return render(request, 'ventas/crear_repartidor.html', {
                'form_data': request.POST,
            })

    return render(request, 'ventas/crear_repartidor.html')


@login_required
@solo_no_repartidor
def editar_repartidor_view(request, repartidor_id):
    """Edita un repartidor existente (User + PerfilRepartidor)."""
    perfil = get_object_or_404(PerfilRepartidor, id=repartidor_id)
    user = perfil.user

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()

        # Cambio de contraseña (opcional)
        nueva_pass = request.POST.get('password', '').strip()
        if nueva_pass:
            from django.contrib.auth.hashers import make_password
            user.password = make_password(nueva_pass)

        user.save()

        perfil.dni = request.POST.get('dni', '').strip()
        perfil.telefono = request.POST.get('telefono', '').strip()
        perfil.vehiculo = request.POST.get('vehiculo', '').strip()
        perfil.patente = request.POST.get('patente', '').strip()
        perfil.zona = request.POST.get('zona', '').strip()
        perfil.licencia_conducir = request.POST.get('licencia_conducir', '').strip()
        perfil.activo = request.POST.get('activo') == 'on'
        perfil.observaciones = request.POST.get('observaciones', '').strip()
        perfil.save()

        messages.success(request, f'Repartidor "{user.get_full_name()}" actualizado.')
        return redirect('ventas:lista_repartidores')

    context = {
        'perfil': perfil,
        'user': user,
    }
    return render(request, 'ventas/editar_repartidor.html', context)

@login_required
@solo_no_repartidor
@csrf_exempt
def marcar_entregado_admin_ajax(request, venta_id):
    """Permite a admin/supervisor marcar cualquier remito como ENTREGADO."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)

    try:
        venta = Venta.objects.get(id=venta_id)

        if venta.estado == 'ENTREGADO':
            return JsonResponse({'status': 'error', 'message': 'Ya estaba entregado.'})
        if venta.estado == 'CANCELADO':
            return JsonResponse({'status': 'error', 'message': 'No se puede marcar un comprobante cancelado.'})

        venta.estado = 'ENTREGADO'
        venta.fecha_entrega = timezone.now()
        venta.save()

        logger.info(f"Venta #{venta.id} marcada como ENTREGADO por {request.user.username}")
        return JsonResponse({'status': 'success', 'message': 'Marcado como entregado.'})
    except Venta.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Comprobante no encontrado.'}, status=404)
    except Exception as e:
        logger.exception(f"Error marcando entregado venta {venta_id}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@solo_no_repartidor
@csrf_exempt
def marcar_entregado_admin_ajax(request, venta_id):
    """Permite a admin/supervisor marcar cualquier remito como ENTREGADO."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)

    try:
        venta = Venta.objects.get(id=venta_id)

        if venta.estado == 'ENTREGADO':
            return JsonResponse({'status': 'error', 'message': 'Ya estaba entregado.'})
        if venta.estado == 'CANCELADO':
            return JsonResponse({'status': 'error', 'message': 'No se puede marcar un comprobante cancelado.'})

        venta.estado = 'ENTREGADO'
        venta.fecha_entrega = timezone.now()
        venta.save()

        logger.info(f"Venta #{venta.id} marcada como ENTREGADO por {request.user.username}")
        return JsonResponse({'status': 'success', 'message': 'Marcado como entregado.'})
    except Venta.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Comprobante no encontrado.'}, status=404)
    except Exception as e:
        logger.exception(f"Error marcando entregado venta {venta_id}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)