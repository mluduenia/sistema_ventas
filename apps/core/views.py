from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from apps.ventas.models import Venta, DetalleVenta

@login_required
def dashboard(request):
    """Panel de control principal con métricas clave y últimas ventas."""
    
    # 1. Total Recaudado
    total_recaudado = Venta.objects.aggregate(total=Sum('total'))['total'] or 0.0

    # 2. Cantidad total de ventas realizadas
    cantidad_ventas = Venta.objects.count()

    # 3. Vendedor con más ventas (Buscamos con vendedor y fallback si están sin vendedor)
    vendedor_top = (
        Venta.objects.filter(vendedor__isnull=False)
        .values('vendedor__username', 'vendedor__first_name', 'vendedor__last_name')
        .annotate(total_ventas=Count('id'))
        .order_by('-total_ventas')
        .first()
    )

    # Si las ventas anteriores se registraron sin vendedor, usamos el usuario actual
    nombre_vendedor_top = None
    ventas_vendedor_top = 0

    if vendedor_top:
        nombre = f"{vendedor_top.get('vendedor__first_name', '')} {vendedor_top.get('vendedor__last_name', '')}".strip()
        nombre_vendedor_top = nombre if nombre else vendedor_top.get('vendedor__username')
        ventas_vendedor_top = vendedor_top.get('total_ventas', 0)
    elif cantidad_ventas > 0:
        # Si hay ventas en la BD pero no tenían vendedor asignado
        nombre_vendedor_top = request.user.first_name if request.user.first_name else request.user.username
        ventas_vendedor_top = cantidad_ventas

    # 4. Producto más vendido
    producto_top = (
        DetalleVenta.objects.values('producto__nombre')
        .annotate(total_vendido=Sum('cantidad'))
        .order_by('-total_vendido')
        .first()
    )

    # 5. Últimas 10 ventas registradas
    ultimas_ventas = (
        Venta.objects.select_related('cliente', 'vendedor')
        .order_by('-fecha')[:10]
    )

    context = {
        'total_recaudado': total_recaudado,
        'cantidad_ventas': cantidad_ventas,
        'nombre_vendedor_top': nombre_vendedor_top,
        'ventas_vendedor_top': ventas_vendedor_top,
        'producto_top': producto_top,
        'ultimas_ventas': ultimas_ventas,
    }

    return render(request, 'dashboard.html', context)