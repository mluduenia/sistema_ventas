from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, PermisoTemporal

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'rol', 'activo', 'fecha_registro')
    list_filter = ('rol', 'activo', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'telefono')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Información Adicional', {
            'fields': ('rol', 'telefono', 'direccion', 'activo')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Adicional', {
            'fields': ('rol', 'telefono', 'direccion', 'activo')
        }),
    )

@admin.register(PermisoTemporal)
class PermisoTemporalAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'permission', 'fecha_expiracion', 'activo')
    list_filter = ('activo', 'fecha_expiracion')
    search_fields = ('usuario__username', 'permission__name')