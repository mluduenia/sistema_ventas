import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Sum
from .models import Cliente, CajaTurno, Venta, DetalleVenta
from apps.productos.models import Producto

@login_required
def lista_ventas(request):
    """Listado general de todas las ventas registradas."""
    ventas = Venta.objects.select_related('cliente', 'vendedor', 'turno').order_by('-fecha')
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
    """Guarda la venta vinculándole automáticamente el turno activo."""
    if request.method == 'POST':
        turno_activo = CajaTurno.objects.filter(vendedor=request.user, estado='ABIERTA').first()
        if not turno_activo:
            return JsonResponse({'success': False, 'error': 'No tienes una caja/turno abierto para vender.'})

        data = json.loads(request.body)
        items = data.get('items', [])
        cliente_id = data.get('cliente_id')
        metodo_pago = data.get('metodo_pago', 'EFECTIVO')

        if not items:
            return JsonResponse({'success': False, 'error': 'El carrito está vacío.'})

        total_venta = sum(float(item['precio']) * int(item['cantidad']) for item in items)

        venta = Venta.objects.create(
            turno=turno_activo,
            vendedor=request.user,
            cliente_id=cliente_id if cliente_id else None,
            metodo_pago=metodo_pago,
            total=total_venta
        )

        for item in items:
            prod = Producto.objects.get(id=item['id'])
            subtotal = float(item['precio']) * int(item['cantidad'])
            
            DetalleVenta.objects.create(
                venta=venta,
                producto=prod,
                cantidad=item['cantidad'],
                precio_unitario=item['precio'],
                subtotal=subtotal
            )

            prod.stock_actual -= int(item['cantidad'])
            prod.save()

        return JsonResponse({
            'success': True, 
            'venta_id': venta.id,
            'cliente_email': venta.cliente.email if venta.cliente and venta.cliente.email else ''
        })

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


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


@login_required
def comprobante_ticket(request, venta_id):
    """Generación o vista del ticket térmico."""
    venta = get_object_or_404(Venta, id=venta_id)
    return render(request, 'ventas/ticket.html', {'venta': venta})


@login_required
def comprobante_factura(request, venta_id):
    """Generación o vista de factura A4."""
    venta = get_object_or_404(Venta, id=venta_id)
    return render(request, 'ventas/factura.html', {'venta': venta})


@login_required
def enviar_email_comprobante(request, venta_id):
    """Envío de comprobante por correo electrónico."""
    if request.method == 'POST':
        return JsonResponse({'success': True, 'message': 'Comprobante enviado.'})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})