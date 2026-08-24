import json
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os


from apps.configuracion.models import EmpresaConfig
from apps.productos.models import MovimientoStock, Producto
from .models import CajaTurno, Cliente, DetalleVenta, Venta

logger = logging.getLogger(__name__)


@login_required
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
def pos_view(request):
    """Pantalla Principal del POS con bloqueo por Caja Cerrada."""
    turno_activo = CajaTurno.objects.filter(vendedor=request.user, estado='ABIERTA').first()
    
    if not turno_activo:
        return redirect('ventas:abrir_caja')

    clientes = Cliente.objects.all()
    context = {
        'clientes': clientes,
        'turno_activo': turno_activo,
    }
    return render(request, 'ventas/pos.html', context)


@login_required
def buscar_producto_ajax(request):
    """Búsqueda de productos por código de barras o nombre."""
    term = request.GET.get('term', '').strip()
    if not term:
        return JsonResponse([], safe=False)

    productos = Producto.objects.filter(
        nombre__icontains=term
    ) | Producto.objects.filter(
        codigo_barra__exact=term
    )

    resultados = []
    for p in productos[:10]:
        resultados.append({
            'id': p.id,
            'nombre': p.nombre,
            'codigo_barra': getattr(p, 'codigo_barra', ''),
            'precio_venta': float(p.precio_venta),
            'stock_actual': getattr(p, 'stock_actual', 0)
        })

    return JsonResponse(resultados, safe=False)


@login_required
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
@csrf_exempt
@transaction.atomic
def procesar_venta_ajax(request):
    """
    Procesa una venta desde el POS e integra facturación electrónica con ARCA / AFIP.
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

        if not items:
            return JsonResponse({'status': 'error', 'message': 'El carrito está vacío.'}, status=400)

        # 2. Validar Turno de Caja Activo
        turno_activo = CajaTurno.objects.filter(vendedor=request.user, estado='ABIERTA').first()
        if not turno_activo:
            return JsonResponse({'status': 'error', 'message': 'No tienes una caja/turno abierto para vender.'}, status=400)

        # 3. Procesar Ítems y Calcular Totales
        total_venta = Decimal('0.00')
        detalles_a_crear = []

        for item in items:
            prod_id = item.get('id')
            cantidad = int(item.get('cantidad', 1))
            if not prod_id:
                return JsonResponse({'status': 'error', 'message': 'Ítem sin ID de producto.'}, status=400)

            producto = Producto.objects.select_for_update().get(pk=prod_id)

            if producto.stock_actual < cantidad:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Stock insuficiente para "{producto.nombre}". Disponible: {producto.stock_actual}'
                }, status=400)

            precio = Decimal(str(producto.precio_venta))
            subtotal = precio * cantidad
            total_venta += subtotal

            detalles_a_crear.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio': precio,
                'subtotal': subtotal,
            })

        # 4. Calcular Vuelto
        monto_recibido = Decimal(str(monto_recibido))
        vuelto = max(Decimal('0.00'), monto_recibido - total_venta)

        # 5. Obtener datos del Cliente
        cliente_obj = None
        if cliente_id:
            cliente_obj = Cliente.objects.filter(id=cliente_id).first()

        # 6. Crear Registro de Venta Local
        venta = Venta.objects.create(
            turno=turno_activo,
            vendedor=request.user,
            cliente=cliente_obj,
            metodo_pago=metodo_pago,
            total=total_venta,
            monto_recibido=monto_recibido,
            vuelto=vuelto,
            tipo_comprobante=tipo_comprobante,
        )

        # 7. Crear Detalles de Venta y Descontar Stock
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

            prod.stock_actual -= cant
            prod.save()

            MovimientoStock.objects.create(
                producto=prod,
                tipo='VENTA',
                cantidad=cant,
                motivo=f'Venta POS Ticket #{venta.id}'
            )

        # 8. CONEXIÓN Y SOLICITUD DE CAE A ARCA / AFIP (pyafipws)
        config = EmpresaConfig.objects.first()

        if config and config.certificado_crt and config.clave_privada_key and config.cuit and tipo_comprobante != 0:
            try:
                from pyafipws.wsaa import WSAA
                from pyafipws.wsfev1 import WSFEv1

                cert_path = config.certificado_crt.path
                key_path = config.clave_privada_key.path
                cuit = config.cuit.replace("-", "").strip()

                # Selección de ambiente según configuración (Homologación vs Producción)
                if config.ambiente_arca == 'PROD':
                    wsdl_wsaa = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
                    wsdl_wsfe = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"
                else:
                    wsdl_wsaa = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
                    wsdl_wsfe = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

                # A. Autenticación con WSAA
                wsaa = WSAA()
                ta = wsaa.Autenticar(
                    "wsfe",
                    cert_path,
                    key_path,
                    wsdl=wsdl_wsaa,
                )

                # B. Inicializar WSFEv1
                wsfev1 = WSFEv1()
                wsfev1.Cuit = cuit
                wsfev1.SetTicketAcceso(ta)

                # C. Conectar
                CACHE_DIR = os.path.join(settings.BASE_DIR, 'afip_cache')
                os.makedirs(CACHE_DIR, exist_ok=True)

                wsfev1.Conectar(
                    wsdl=wsdl_wsfe,
                    cache=CACHE_DIR,
                )

                # D. Obtener Último Comprobante e Incrementar
                pto_vta = int(config.punto_de_venta or 1)
                cbte_nro = int(wsfev1.CompUltimoAutorizado(tipo_comprobante, pto_vta) or 0) + 1

                # E. Datos del Cliente / Comprobante
                doc_tipo = 99  # Consumidor Final
                doc_nro = 0

                if cliente_obj and cliente_obj.numero_documento:
                    doc_nro = cliente_obj.numero_documento.replace("-", "").strip()
                    if len(doc_nro) == 11:
                        doc_tipo = 80  # CUIT
                    elif len(doc_nro) == 8:
                        doc_tipo = 96  # DNI
                    else:
                        doc_tipo = 99  # Consumidor Final

                fecha_cbte = timezone.now().strftime("%Y%m%d")

                # F. Mapeo de condición IVA del receptor (RG 5616)
                cond_iva_receptor = 5  # 5 = Consumidor Final
                if cliente_obj and hasattr(cliente_obj, 'condicion_iva') and cliente_obj.condicion_iva:
                    try:
                        cond_iva_receptor = int(cliente_obj.condicion_iva)
                    except (ValueError, TypeError):
                        cond_iva_receptor = 5

                # G. Calcular Neto e IVA redondeados a 2 decimales
                imp_neto = (total_venta / Decimal("1.21")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                imp_iva = (total_venta - imp_neto).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                # H. Crear Factura en AFIP
                wsfev1.CrearFactura(
                    concepto=1,
                    tipo_doc=doc_tipo,
                    nro_doc=doc_nro,
                    tipo_cbte=tipo_comprobante,
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

                # I. RG 5616: setear campo condicion_iva_receptor_id
                try:
                    wsfev1.EstablecerCampoFactura("condicion_iva_receptor_id", str(cond_iva_receptor))
                    wsfev1.EstablecerCampoFactura("cancela_misma_moneda_ext", "N")
                except Exception as e:
                    logger.warning(f"No se pudo establecer condicion_iva_receptor_id: {e}")

                # J. Agregar Alicuota de IVA 21%
                wsfev1.AgregarIva(
                    5,
                    float(imp_neto),
                    float(imp_iva)
                )

                # K. Solicitar CAE
                wsfev1.CAESolicitar()

                # L. Procesar respuesta
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
                    venta.tipo_comprobante = tipo_comprobante
                    venta.save()
                    logger.info(f"CAE Autorizado para Venta #{venta.id}: {cae_obtenido}")
                else:
                    resultado = getattr(wsfev1, "Resultado", "Desconocido")
                    obs = getattr(wsfev1, "Obs", "Sin observaciones")
                    logger.error(f"Respuesta ARCA sin CAE. Resultado: {resultado}, Obs: {obs}")

            except Exception as afip_err:
                logger.exception(f"Excepción al conectar con ARCA/AFIP: {afip_err}")

        # 9. Respuesta exitosa para el POS
        return JsonResponse({
            'status': 'success',
            'message': 'Venta realizada correctamente.',
            'venta_id': venta.id,
            'total': float(total_venta),
            'vuelto': float(vuelto),
            'cae': venta.cae if venta.cae else None
        })

    except Exception as e:
        logger.exception("Error inesperado en procesar_venta_ajax")
        return JsonResponse({'status': 'error', 'message': f'Error interno: {str(e)}'}, status=500)


@login_required
def crear_cliente(request):
    """Vista para crear un nuevo cliente."""
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        cuit_dni = request.POST.get('cuit_dni')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email')
        direccion = request.POST.get('direccion')

        Cliente.objects.create(
            nombre=nombre,
            numero_documento=cuit_dni,
            telefono=telefono,
            email=email,
            direccion=direccion
        )
        messages.success(request, 'Cliente registrado correctamente.')
        return redirect('ventas:pos')

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
def reportes_view(request):
    hoy = timezone.now()
    mes_sel = int(request.GET.get('mes', hoy.month))
    anio_sel = int(request.GET.get('anio', hoy.year))

    ventas_periodo = Venta.objects.filter(fecha__month=mes_sel, fecha__year=anio_sel)
    detalles_periodo = DetalleVenta.objects.filter(
        venta__fecha__month=mes_sel, 
        venta__fecha__year=anio_sel
    )

    # 1. TOTALES DEL PERÍODO Y GANANCIA REAL
    total_recaudado = ventas_periodo.aggregate(Sum('total'))['total__sum'] or 0
    total_operaciones = ventas_periodo.count()

    # Cálculo de Ganancia Real: (Precio Venta - Precio Costo) * Cantidad
    ganancia_real = detalles_periodo.aggregate(
        ganancia=Sum(F('cantidad') * (F('precio_unitario') - F('producto__precio_costo')))
    )['ganancia'] or 0

    # Margen Porcentual de Ganancia
    margen_porcentaje = (ganancia_real / total_recaudado * 100) if total_recaudado > 0 else 0

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
        'anios_disponibles': range(hoy.year, 2023, -1),
        'total_recaudado': total_recaudado,
        'total_operaciones': total_operaciones,
        'ganancia_real': ganancia_real,
        'margen_porcentaje': margen_porcentaje,
        'medios_pago': medios_pago,
        'productos_top': productos_top,
        'vendedores_top': vendedores_top,
        'proveedores_top': proveedores_top,
    }
    return render(request, 'ventas/reportes.html', context)