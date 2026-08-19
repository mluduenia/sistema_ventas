from django.contrib import admin
from .models import Auditoria

@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('accion', 'usuario', 'fecha')
    search_fields = ('accion', 'usuario')
    list_filter = ('fecha',)