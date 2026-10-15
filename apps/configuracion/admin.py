from django.contrib import admin
from .models import EmpresaConfig, Sucursal, AuditLog


@admin.register(EmpresaConfig)
class EmpresaConfigAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'cuit', 'condicion_iva', 'punto_de_venta', 'ambiente_arca')
    list_filter = ('condicion_iva', 'ambiente_arca')
    search_fields = ('razon_social', 'nombre_fantasia', 'cuit')
    fieldsets = (
        ('Datos Comerciales', {
            'fields': (
                'logo', 'razon_social', 'nombre_fantasia', 'cuit',
                'condicion_iva', 'alicuota_iva_default',
                'iibb', 'inicio_actividades',
            )
        }),
        ('Domicilio y Contacto', {
            'fields': ('direccion', 'telefono', 'email')
        }),
        ('Configuración ARCA / AFIP', {
            'fields': (
                'punto_de_venta', 'ambiente_arca',
                'certificado_crt', 'clave_privada_key',
            )
        }),
        ('Configuración SMTP', {
            'fields': (
                'email_smtp_host', 'email_smtp_port',
                'email_smtp_user', 'email_smtp_password',
                'email_smtp_use_tls',
            )
        }),
        ('Módulos del Sistema', {
            'fields': (
                'modo_negocio',
                'modulo_punto_venta', 'modulo_preventa', 'modulo_reparto',
                'modulo_deposito', 'modulo_cuenta_corriente', 'modulo_multi_sucursal',
            )
        }),
    )


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'es_central', 'activa', 'telefono', 'lista_precio')
    list_filter = ('tipo', 'es_central', 'activa')
    search_fields = ('nombre', 'direccion', 'telefono', 'email')
    list_editable = ('activa',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'accion', 'nivel', 'modelo', 'objeto_id', 'descripcion_corta')
    list_filter = ('accion', 'nivel', 'modelo')
    search_fields = ('descripcion', 'usuario__username')
    date_hierarchy = 'fecha'
    readonly_fields = (
        'fecha', 'usuario', 'rol_snapshot', 'accion', 'nivel',
        'modelo', 'objeto_id', 'descripcion',
        'datos_antes', 'datos_despues', 'metadata',
        'ip', 'user_agent',
    )

    def descripcion_corta(self, obj):
        """Muestra solo los primeros 80 caracteres de la descripción."""
        if obj.descripcion:
            return obj.descripcion[:80] + ('...' if len(obj.descripcion) > 80 else '')
        return '-'
    descripcion_corta.short_description = 'Descripción'