from django.contrib import admin
from .models import Cliente, Venta, DetalleVenta, CajaTurno

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'numero_documento', 'telefono', 'email')
    search_fields = ('nombre', 'numero_documento', 'email')


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0
    readonly_fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal')


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'vendedor', 'cliente', 'metodo_pago', 'total', 'turno')
    list_filter = ('metodo_pago', 'fecha', 'vendedor')
    search_fields = ('id', 'vendedor__username', 'cliente__nombre')
    inlines = [DetalleVentaInline]


@admin.register(CajaTurno)
class CajaTurnoAdmin(admin.ModelAdmin):
    list_display = ('id', 'vendedor', 'estado', 'monto_inicial', 'monto_final_efectivo', 'diferencia', 'fecha_apertura', 'fecha_cierre')
    list_filter = ('estado', 'vendedor', 'fecha_apertura')
    search_fields = ('vendedor__username', 'observaciones')