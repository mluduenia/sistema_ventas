from django.contrib import admin
from .models import Alerta


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'nivel', 'usuario', 'rol', 'leida', 'creada')
    list_filter = ('tipo', 'nivel', 'leida', 'rol')
    search_fields = ('titulo', 'mensaje')
    readonly_fields = ('creada',)