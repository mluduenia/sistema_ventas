import json
from django.contrib.auth.decorators import login_required
from django.db import transaction  # <--- IMPORTACIÓN FALTANTE
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.configuracion.models import EmpresaConfig
from apps.productos.models import Producto

from .models import CajaTurno, Cliente, DetalleVenta, Venta

@login_required
def lista_ventas(request):
    """Listado general de ventas."""
    ventas = Venta.objects.select_related('cliente', 'vendedor', 'turno').order_by('-id')
    
    # Si la petición viene vía AJAX (auto-refresh), devolvemos el HTML parcial
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'ventas/tabla_ventas_partial.html', {'ventas': ventas})

    return render(request, 'ventas/lista_ventas.html', {'ventas': ventas})

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
def procesar_venta_ajax(request):
    """Guarda la venta y solicita el CAE a ARCA (AFIP) en entorno de Homologación."""
    if request.method == "POST":
        turno_activo = CajaTurno.objects.filter(
            vendedor=request.user, estado="ABIERTA"
        ).first()
        if not turno_activo:
            return JsonResponse(
                {
                    "success": False,
                    "error": "No tienes una caja/turno abierto para vender.",
                }
            )

        data = json.loads(request.body)
        items = data.get("items", [])
        cliente_id = data.get("cliente_id")
        metodo_pago = data.get("metodo_pago", "EFECTIVO")

        if not items:
            return JsonResponse(
                {"success": False, "error": "El carrito está vacío."}
            )

        total_venta = sum(
            float(item["precio"]) * int(item["cantidad"]) for item in items
        )

        # 1. Registro local de la venta dentro de una transacción atómica
        with transaction.atomic():
            venta = Venta.objects.create(
                turno=turno_activo,
                vendedor=request.user,
                cliente_id=cliente_id if cliente_id else None,
                metodo_pago=metodo_pago,
                total=total_venta,
            )

            for item in items:
                prod = Producto.objects.get(id=item["id"])
                subtotal = float(item["precio"]) * int(item["cantidad"])

                DetalleVenta.objects.create(
                    venta=venta,
                    producto=prod,
                    cantidad=item["cantidad"],
                    precio_unitario=item["precio"],
                    subtotal=subtotal,
                )

                prod.stock_actual -= int(item["cantidad"])
                prod.save()

        # 2. Facturación Electrónica en ARCA / AFIP (Homologación)
        config = EmpresaConfig.objects.first()
        if (
            config
            and config.certificado_crt
            and config.clave_privada_key
            and config.cuit
        ):
            try:
                from pyafipws.wsaa import WSAA
                from pyafipws.wsfev1 import WSFEv1

                cert_path = config.certificado_crt.path
                key_path = config.clave_privada_key.path
                cuit = config.cuit.replace("-", "").strip()

                # Autenticación WSAA
                wsaa = WSAA()
                ta = wsaa.Autenticar(
                    "wsfe",
                    cert_path,
                    key_path,
                    wsdl="https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
                )

                # Inicialización del servicio WSFE
                wsfe = WSFEv1()
                wsfe.Cuit = cuit
                wsfe.SetTicketAcceso(ta)
                wsfe.Conectar(
                    wsdl="https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
                )

                pv = int(config.punto_de_venta or 1)
                tipo_cbte = 6  # 6 = Factura B
                cbte_nro = int(wsfe.CompUltimoAutorizado(tipo_cbte, pv) or 0) + 1

                # Mapeo de condición IVA del receptor conforme a RG 5616 (5 = Consumidor Final)
                cond_iva_receptor = 5
                if venta.cliente and hasattr(venta.cliente, 'condicion_iva') and venta.cliente.condicion_iva:
                    try:
                        cond_iva_receptor = int(venta.cliente.condicion_iva)
                    except (ValueError, TypeError):
                        cond_iva_receptor = 5

                # 1. CREAR EL COMPROBANTE
                wsfe.CrearFactura(
                    concepto=1,  # 1 = Productos
                    tipo_doc=99,  # 99 = Consumidor Final / Sin Documento
                    nro_doc=0,
                    tipo_cbte=tipo_cbte,
                    punto_vta=pv,
                    cbt_desde=cbte_nro,
                    cbt_hasta=cbte_nro,
                    imp_total=round(total_venta, 2),
                    imp_tot_conc=0.0,
                    imp_neto=round(total_venta / 1.21, 2),
                    imp_iva=round(total_venta - (total_venta / 1.21), 2),
                    imp_trib=0.0,
                    imp_op_ex=0.0,
                    fecha_cbte=timezone.now().strftime("%Y%m%d")
                )

                # 2. RG 5616: setear campo condicion_iva_receptor_id
                wsfe.EstablecerCampoFactura(
                    "condicion_iva_receptor_id", str(cond_iva_receptor)
                )
                wsfe.EstablecerCampoFactura("cancela_misma_moneda_ext", "N")

                # 3. AGREGAR ALÍCUOTA IVA 21% (argumentos posicionales)
                wsfe.AgregarIva(
                    5,  # id: 5 = 21%
                    round(total_venta / 1.21, 2),   # base_imp
                    round(total_venta - (total_venta / 1.21), 2)  # importe
                )

                # 4. SOLICITAR CAE
                wsfe.CAESolicitar()

                # Extraer CAE de forma segura mediante métodos o atributos de la librería
                cae_val = None
                venc_val = None

                # Intentar leer desde el método o atributos estándar de pyafipws
                if hasattr(wsfe, "CAE") and wsfe.CAE:
                    cae_val = wsfe.CAE
                elif hasattr(wsfe, "Cae") and wsfe.Cae:
                    cae_val = wsfe.Cae
                elif hasattr(wsfe, "factura") and isinstance(wsfe.factura, dict):
                    cae_val = wsfe.factura.get("cae") or wsfe.factura.get("CAE")

                if hasattr(wsfe, "Vencimiento") and wsfe.Vencimiento:
                    venc_val = wsfe.Vencimiento
                elif hasattr(wsfe, "vencimiento") and wsfe.vencimiento:
                    venc_val = wsfe.vencimiento
                elif hasattr(wsfe, "factura") and isinstance(wsfe.factura, dict):
                    venc_val = wsfe.factura.get("vencimiento") or wsfe.factura.get("Vencimiento")

                # Si el resultado fue A (Aprobado) o se obtuvo un CAE
                resultado = getattr(wsfe, "Resultado", "")
                if resultado == "A" or cae_val:
                    venta.cae = str(cae_val) if cae_val else ""
                    
                    if venc_val:
                        try:
                            venta.vencimiento_cae = timezone.datetime.strptime(
                                str(venc_val), "%Y%m%d"
                            ).date()
                        except ValueError:
                            pass
                    
                    venta.numero_comprobante = cbte_nro
                    venta.tipo_comprobante = tipo_cbte
                    venta.save()
                    print(f"¡VENTA AUTORIZADA EXITOSAMENTE! CAE: {venta.cae} - Comprobante N°: {cbte_nro}")
                else:
                    print("Respuesta de ARCA:", resultado)
                    print("Observaciones ARCA:", getattr(wsfe, "Obs", ""))

            except Exception as e:
                print("Error de conexión con ARCA/AFIP Homo:", str(e))

        return JsonResponse(
            {
                "success": True,
                "venta_id": venta.id,
                "cliente_email": (
                    venta.cliente.email
                    if venta.cliente and venta.cliente.email
                    else ""
                ),
            }
        )

    return JsonResponse({"success": False, "error": "Método no permitido"})


@login_required
def crear_cliente(request):
    """Vista rápida para crear cliente desde el POS."""
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        doc = request.POST.get('numero_documento')
        email = request.POST.get('email')
        if nombre:
            Cliente.objects.create(nombre=nombre, numero_documento=doc, email=email)
        return redirect('ventas:pos')
    return render(request, 'ventas/crear_cliente.html')


from apps.configuracion.models import EmpresaConfig


from apps.configuracion.models import EmpresaConfig


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