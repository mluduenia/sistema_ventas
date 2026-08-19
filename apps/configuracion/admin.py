from django.contrib import admin
from .models import EmpresaConfig

@admin.register(EmpresaConfig)
class EmpresaConfigAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'cuit', 'condicion_iva', 'punto_de_venta', 'ambiente_arca')