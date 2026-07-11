from django.contrib import admin
from .models import Auditoria

@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'accion', 'modelo', 'fecha')
    list_filter = ('accion', 'fecha')
    search_fields = ('usuario__username', 'modelo')
    readonly_fields = ('fecha',)