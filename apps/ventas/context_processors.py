from decimal import Decimal
from django.db.models import Sum
from .models import Venta, CajaTurno


def remitos_pendientes_global(request):
    """
    Inyecta en TODOS los templates:
    - cantidad_remitos_pendientes_global
    - total_remitos_pendientes_global
    """
    if not request.user.is_authenticated:
        return {}

    if getattr(request.user, 'rol', '') == 'repartidor':
        return {}

    # Solo contar los del turno activo (o los heredados si hay turno abierto)
    turno_activo = CajaTurno.objects.filter(
        vendedor=request.user, estado='ABIERTA'
    ).first()

    qs = Venta.objects.filter(
        estado__in=['PENDIENTE_ENTREGA', 'ENTREGADO'],
        estado_cobro__in=['PENDIENTE', 'PARCIAL'],
        es_nota_credito=False,
        es_remito=True,
    ).exclude(estado='CANCELADO')

    if turno_activo and turno_activo.sucursal_id:
        qs = qs.filter(sucursal_id=turno_activo.sucursal_id)

    cantidad = qs.count()
    total = qs.aggregate(t=Sum('total'))['t'] or Decimal('0.00')

    return {
        'cantidad_remitos_pendientes_global': cantidad,
        'total_remitos_pendientes_global': total,
    }