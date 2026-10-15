from django.db import models
from django.conf import settings


class EmpresaConfig(models.Model):
    # ============================================================
    # CHOICES (definidos ANTES de usarse)
    # ============================================================
    CONDICION_IVA_CHOICES = [
        ('RI', 'Responsable Inscripto'),
        ('MO', 'Monotributo'),
        ('EX', 'Exento'),
    ]

    AMBIENTE_ARCA_CHOICES = [
        ('HOMO', 'Homologación (Pruebas)'),
        ('PROD', 'Producción (Real)'),
    ]

    MODO_NEGOCIO_CHOICES = [
        ('LOCAL', 'Solo Local / Mostrador'),
        ('LOCAL_REPARTO', 'Local + Reparto'),
        ('SOLO_REPARTO', 'Solo Reparto / Preventa'),
        ('CUSTOM', 'Personalizado'),
    ]

    # ============================================================
    # DATOS COMERCIALES
    # ============================================================
    logo = models.ImageField('Logo del Comercio', upload_to='logos/', blank=True, null=True)
    razon_social = models.CharField(max_length=200, default='Mi Comercio S.A.')
    nombre_fantasia = models.CharField(max_length=200, blank=True, null=True, default='Mi Negocio')
    cuit = models.CharField(max_length=20, default='20-12345678-9')

    # 🔽 Condición IVA del emisor
    condicion_iva = models.CharField(
        "Condición IVA del Emisor",
        max_length=5,
        choices=CONDICION_IVA_CHOICES,
        default='MO',
        help_text='Determina qué tipos de comprobante puede emitir el sistema.'
    )

    # 🔽 Alícuota de IVA por defecto
    alicuota_iva_default = models.DecimalField(
        "Alícuota IVA por Defecto (%)",
        max_digits=5,
        decimal_places=2,
        default=21.00,
        help_text='Alícuota de IVA por defecto. Ej: 21.00'
    )

    iibb = models.CharField(max_length=50, blank=True, null=True, help_text='Número de Ingresos Brutos')
    inicio_actividades = models.DateField(blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True, default='Av. Principal 123')
    telefono = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # ============================================================
    # CONFIGURACIÓN SMTP
    # ============================================================
    email_smtp_host = models.CharField(max_length=150, default='smtp.gmail.com', help_text='Ej: smtp.gmail.com o smtp.office365.com')
    email_smtp_port = models.IntegerField(default=587, help_text='Puerto SMTP habitual: 587 (TLS) o 465 (SSL)')
    email_smtp_user = models.CharField(max_length=150, blank=True, null=True, help_text='Tu correo emisor')
    email_smtp_password = models.CharField(max_length=150, blank=True, null=True, help_text='Contraseña de aplicación')
    email_smtp_use_tls = models.BooleanField(default=True)

    # ============================================================
    # CONFIGURACIÓN ARCA / AFIP
    # ============================================================
    punto_de_venta = models.IntegerField(default=1, help_text='Número de Punto de Venta habilitado en ARCA (Ej: 1)')
    ambiente_arca = models.CharField(max_length=5, choices=AMBIENTE_ARCA_CHOICES, default='HOMO')
    certificado_crt = models.FileField(upload_to='certificados/', blank=True, null=True, help_text='Archivo .crt obtenido en ARCA')
    clave_privada_key = models.FileField(upload_to='certificados/', blank=True, null=True, help_text='Archivo .key de la clave privada')

    # ============================================================
    # MÓDULOS ACTIVABLES DEL SISTEMA
    # ============================================================
    modo_negocio = models.CharField(
        "Modo de Negocio",
        max_length=20,
        choices=MODO_NEGOCIO_CHOICES,
        default='LOCAL',
        help_text="Preset rápido. Al cambiarlo, se actualizan los módulos automáticamente."
    )

    modulo_punto_venta = models.BooleanField(
        "Módulo Punto de Venta (Salón / Mostrador)",
        default=True,
        help_text="Habilita el POS con caja abierta, cobro inmediato y facturación en el local."
    )
    modulo_preventa = models.BooleanField(
        "Módulo Preventa / Viajante",
        default=False,
        help_text="Habilita la toma de pedidos en la calle, sin caja abierta."
    )
    modulo_reparto = models.BooleanField(
        "Módulo Reparto a Domicilio",
        default=False,
        help_text="Habilita repartidores, remitos y entregas."
    )
    modulo_deposito = models.BooleanField(
        "Módulo Depósito / Almacén",
        default=False,
        help_text="Habilita la gestión de stock por depósito."
    )
    modulo_cuenta_corriente = models.BooleanField(
        "Módulo Cuentas Corrientes",
        default=True,
        help_text="Habilita el manejo de deudas de clientes."
    )
    modulo_multi_sucursal = models.BooleanField(
        "Módulo Multi-Sucursal",
        default=False,
        help_text="Habilita la gestión de múltiples sucursales."
    )

    class Meta:
        verbose_name = 'Configuración de Empresa'
        verbose_name_plural = 'Configuraciones de Empresa'

    def __str__(self):
        return f"{self.razon_social} (CUIT: {self.cuit})"

    # ============================================================
    # PROPIEDADES
    # ============================================================

    @property
    def discrimina_iva(self):
        """True si el emisor debe discriminar IVA (Responsable Inscripto)."""
        return self.condicion_iva == 'RI'

    @property
    def tipo_comprobante_default(self):
        """Tipo de comprobante por defecto según condición del emisor."""
        if self.condicion_iva == 'RI':
            return 6  # Factura B (a Consumidor Final por defecto)
        else:
            return 11  # Factura C (Monotributo o Exento)

    # ============================================================
    # PRESETS DE MÓDULOS
    # ============================================================

    def aplicar_preset(self, modo):
        """
        Aplica los flags de módulos según el modo de negocio elegido.
        Devuelve True si aplicó un preset, False si es CUSTOM.
        """
        if modo == 'LOCAL':
            self.modulo_punto_venta = True
            self.modulo_preventa = False
            self.modulo_reparto = False
            self.modulo_deposito = False
            self.modulo_cuenta_corriente = True
            self.modulo_multi_sucursal = False
        elif modo == 'LOCAL_REPARTO':
            self.modulo_punto_venta = True
            self.modulo_preventa = True
            self.modulo_reparto = True
            self.modulo_deposito = True
            self.modulo_cuenta_corriente = True
            self.modulo_multi_sucursal = False
        elif modo == 'SOLO_REPARTO':
            self.modulo_punto_venta = False
            self.modulo_preventa = True
            self.modulo_reparto = True
            self.modulo_deposito = True
            self.modulo_cuenta_corriente = True
            self.modulo_multi_sucursal = False
        else:
            # CUSTOM → no se toca nada
            return False

        self.modo_negocio = modo
        return True

    def save(self, *args, **kwargs):
        """
        Si el modo_negocio cambió, aplica el preset automáticamente
        ANTES de guardar (excepto si es CUSTOM).
        """
        if self.pk:
            try:
                anterior = EmpresaConfig.objects.get(pk=self.pk)
                if anterior.modo_negocio != self.modo_negocio and self.modo_negocio != 'CUSTOM':
                    self.aplicar_preset(self.modo_negocio)
            except EmpresaConfig.DoesNotExist:
                pass
        else:
            # Es nuevo: aplicar preset inicial
            if self.modo_negocio != 'CUSTOM':
                self.aplicar_preset(self.modo_negocio)

        super().save(*args, **kwargs)


# =========================================================
# SUCURSAL
# =========================================================

class Sucursal(models.Model):
    """Representa una sucursal o local del negocio."""

    TIPO_CHOICES = [
        ("CENTRAL", "Central / Planta"),
        ("SUCURSAL", "Sucursal"),
        ("DEPOSITO", "Depósito"),
    ]

    nombre = models.CharField("Nombre", max_length=100)
    tipo = models.CharField(
        "Tipo", max_length=20, choices=TIPO_CHOICES, default="SUCURSAL"
    )

    lista_precio = models.ForeignKey(
        'productos.ListaPrecio',
        on_delete=models.PROTECT,
        related_name='sucursales',
        verbose_name="Lista de Precios",
        null=True, blank=True,
        help_text="Lista de precios que usa esta sucursal"
    )

    direccion = models.CharField("Dirección", max_length=255, blank=True)
    telefono = models.CharField("Teléfono", max_length=30, blank=True)
    email = models.EmailField("Email", blank=True)

    punto_de_venta_arca = models.IntegerField(
        "Punto de Venta ARCA",
        default=1,
        help_text="Número de punto de venta habilitado en ARCA para esta sucursal"
    )

    activa = models.BooleanField("Activa", default=True)
    es_central = models.BooleanField(
        "Es Central / Depósito Principal",
        default=False,
        help_text="Marcar solo si es la sucursal principal (donde se produce/almacena)"
    )

    fecha_alta = models.DateTimeField("Fecha de Alta", auto_now_add=True, null=True)

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"
        ordering = ['-es_central', 'nombre']

    def __str__(self):
        if self.es_central:
            return f"{self.nombre} (Central)"
        return self.nombre

    @property
    def es_central_bool(self):
        """Alias por compatibilidad."""
        return self.es_central


# =========================================================
# LOG DE AUDITORÍA
# =========================================================

class AuditLog(models.Model):
    """Registra todas las acciones importantes del sistema para auditoría."""

    ACCIONES = [
        ('LOGIN', 'Inicio de sesión'),
        ('LOGIN_FAIL', 'Intento de login fallido'),
        ('LOGOUT', 'Cierre de sesión'),
        ('CREATE', 'Creación'),
        ('UPDATE', 'Modificación'),
        ('DELETE', 'Eliminación'),
        ('BAJA', 'Baja lógica'),
        ('REACTIVAR', 'Reactivación'),
        ('VENTA', 'Venta'),
        ('ANULAR', 'Anulación'),
        ('FACTURAR', 'Facturación'),
        ('CAJA_ABRIR', 'Apertura de caja'),
        ('CAJA_CERRAR', 'Cierre de caja'),
        ('INFO_X', 'Informe X emitido'),
        ('INFO_Z', 'Informe Z emitido'),
        ('CONFIG', 'Cambio de configuración'),
        ('MODULOS', 'Cambio de módulos'),
        ('LIMPIEZA', 'Limpieza de datos'),
        ('ERROR', 'Error del sistema'),
        ('ACCESO_DENEGADO', 'Acceso denegado'),
    ]

    NIVELES = [
        ('INFO', 'Informativo'),
        ('WARNING', 'Advertencia'),
        ('CRITICAL', 'Crítico'),
    ]

    fecha = models.DateTimeField("Fecha", auto_now_add=True, db_index=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name="Usuario",
    )
    rol_snapshot = models.CharField(
        "Rol (snapshot)",
        max_length=20, blank=True,
        help_text="Rol del usuario en el momento del evento",
    )

    accion = models.CharField("Acción", max_length=20, choices=ACCIONES, db_index=True)
    nivel = models.CharField("Nivel", max_length=10, choices=NIVELES, default='INFO', db_index=True)

    modelo = models.CharField("Modelo", max_length=50, blank=True, db_index=True)
    objeto_id = models.PositiveIntegerField("ID del objeto", null=True, blank=True, db_index=True)

    descripcion = models.TextField("Descripción")

    datos_antes = models.JSONField("Datos antes", null=True, blank=True)
    datos_despues = models.JSONField("Datos después", null=True, blank=True)
    metadata = models.JSONField("Metadata", null=True, blank=True)

    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.TextField("User Agent", blank=True)

    class Meta:
        verbose_name = "Log de Auditoría"
        verbose_name_plural = "Logs de Auditoría"
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha', 'accion']),
            models.Index(fields=['usuario', '-fecha']),
            models.Index(fields=['modelo', 'objeto_id']),
        ]

    def __str__(self):
        quien = self.usuario.username if self.usuario else 'Anónimo'
        return f"[{self.fecha:%d/%m/%Y %H:%M}] {quien} - {self.get_accion_display()}"

    @property
    def badge_color(self):
        """Color del badge según el nivel."""
        return {
            'INFO': 'info',
            'WARNING': 'warning text-dark',
            'CRITICAL': 'danger',
        }.get(self.nivel, 'secondary')

    @property
    def icono_accion(self):
        """Ícono FontAwesome según la acción."""
        return {
            'LOGIN': 'fa-sign-in-alt text-success',
            'LOGIN_FAIL': 'fa-exclamation-triangle text-danger',
            'LOGOUT': 'fa-sign-out-alt text-secondary',
            'CREATE': 'fa-plus-circle text-success',
            'UPDATE': 'fa-edit text-primary',
            'DELETE': 'fa-trash text-danger',
            'BAJA': 'fa-user-slash text-warning',
            'REACTIVAR': 'fa-user-check text-success',
            'VENTA': 'fa-shopping-cart text-success',
            'ANULAR': 'fa-ban text-danger',
            'FACTURAR': 'fa-file-invoice text-primary',
            'CAJA_ABRIR': 'fa-lock-open text-success',
            'CAJA_CERRAR': 'fa-lock text-warning',
            'INFO_X': 'fa-file-alt text-info',
            'INFO_Z': 'fa-file-invoice-dollar text-danger',
            'CONFIG': 'fa-cog text-primary',
            'MODULOS': 'fa-sliders-h text-primary',
            'LIMPIEZA': 'fa-broom text-danger',
            'ERROR': 'fa-bug text-danger',
            'ACCESO_DENEGADO': 'fa-shield-alt text-warning',
        }.get(self.accion, 'fa-circle text-secondary')