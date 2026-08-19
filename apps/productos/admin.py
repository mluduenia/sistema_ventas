from django.contrib import admin
from .models import Categoria, Proveedor, Producto, MovimientoStock

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre_o_razon_social', 'cuit', 'telefono', 'email')
    search_fields = ('nombre_o_razon_social', 'cuit')

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('codigo_barra', 'nombre', 'categoria', 'precio_venta', 'stock_actual', 'activo')
    list_filter = ('categoria', 'activo')
    search_fields = ('nombre', 'codigo_barra')

@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tipo', 'cantidad', 'fecha', 'motivo')
    list_filter = ('tipo', 'fecha')
    search_fields = ('producto__nombre', 'motivo')