from apps.productos.models import Producto
from django.conf import settings
from django.db import models


class Cliente(models.Model):
    """Modelo para la gestión de clientes dentro del sistema."""

    TIPO_DOC_CHOICES = [
        ("CUIT", "CUIT"),
        ("CUIL", "CUIL"),
        ("DNI", "DNI"),
        ("PASAPORTE", "Pasaporte"),
        ("OTRO", "Otro"),
    ]

    CONDICION_IVA_CHOICES = [
        ("1", "IVA Responsable Inscripto"),
        ("4", "IVA Sujeto Exento"),
        ("5", "Consumidor Final"),
        ("6", "Responsable Monotributo"),
        ("7", "Sujeto No Categorizado"),
        ("8", "Proveedor del Exterior"),
        ("9", "Cliente del Exterior"),
        ("10", "IVA Liberado - Ley Nº 19.640"),
        ("13", "Monotributista Social"),
        ("15", "IVA No Alcanzado"),
        ("16", "Monotributo Trabajador Independiente Promovido"),
    ]

    # ============================================================
    # DATOS PERSONALES
    # ============================================================
    nombre = models.CharField("Nombre / Razón Social", max_length=200)
    tipo_documento = models.CharField(
        "Tipo Doc.", max_length=10, choices=TIPO_DOC_CHOICES, default="CUIT"
    )
    numero_documento = models.CharField(
        "Nº Documento", max_length=20, blank=True, null=True
    )
    condicion_iva = models.CharField(
        "Condición IVA", max_length=5, choices=CONDICION_IVA_CHOICES, default="5"
    )

    email = models.EmailField("Correo Electrónico", blank=True, null=True)
    telefono = models.CharField("Teléfono", max_length=30, blank=True, null=True)
    telefono_alternativo = models.CharField(
        "Teléfono Alternativo", max_length=30, blank=True, null=True
    )
    fecha_nacimiento = models.DateField("Fecha de Nacimiento", null=True, blank=True)

    # ============================================================
    # DIRECCIÓN
    # ============================================================
    direccion = models.CharField(
        "Dirección (legacy)", max_length=255, blank=True, null=True,
        help_text="Dirección en texto libre (compatibilidad con datos viejos)"
    )
    calle = models.CharField("Calle", max_length=200, blank=True, null=True)
    numero = models.CharField("Número", max_length=20, blank=True, null=True)
    piso_dpto = models.CharField("Piso / Dpto", max_length=20, blank=True, null=True)
    barrio = models.CharField("Barrio", max_length=100, blank=True, null=True)
    localidad = models.CharField("Localidad", max_length=100, blank=True, null=True)
    provincia = models.CharField("Provincia", max_length=100, blank=True, null=True)
    codigo_postal = models.CharField("Código Postal", max_length=10, blank=True, null=True)
    entre_calles = models.CharField("Entre Calles", max_length=200, blank=True, null=True)
    referencia = models.CharField(
        "Referencia / Timbre", max_length=200, blank=True, null=True,
        help_text="Ej: Timbre 3B, portón verde"
    )

    # ============================================================
    # OTROS
    # ============================================================
    observaciones = models.TextField("Observaciones", blank=True, null=True)

    # ============================================================
    # AUDITORÍA
    # ============================================================
    fecha_alta = models.DateTimeField("Fecha de Alta", auto_now_add=True, null=True)
    fecha_modificacion = models.DateTimeField(
        "Última Modificación", auto_now=True, null=True
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clientes_creados',
        verbose_name="Creado por"
    )

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    # ============================================================
    # PROPIEDADES
    # ============================================================

    @property
    def direccion_completa(self):
        """Arma la dirección completa para mostrar en el POS o comprobantes."""
        partes = []

        if self.calle:
            linea = self.calle
            if self.numero:
                linea += f" {self.numero}"
            partes.append(linea)

        if self.piso_dpto:
            partes.append(self.piso_dpto)

        if self.barrio:
            partes.append(self.barrio)

        if self.localidad:
            partes.append(self.localidad)

        if self.provincia:
            partes.append(self.provincia)

        if self.codigo_postal:
            partes.append(f"CP {self.codigo_postal}")

        if not partes and self.direccion:
            return self.direccion

        return ", ".join(partes)

    @property
    def saldo_cuenta_corriente(self):
        """Saldo actual del cliente (positivo = debe plata)."""
        from django.db.models import Sum
        resultado = self.ventas.filter(
            es_remito=False,
            es_nota_credito=False,
            estado_cobro__in=['PENDIENTE', 'PARCIAL'],
            estado__in=['COMPLETADO', 'ENTREGADO']
        ).aggregate(total=Sum('saldo_pendiente'))['total']
        return resultado or 0

    @property
    def tiene_cuenta_corriente(self):
        """True si el cliente tiene saldo pendiente."""
        return self.saldo_cuenta_corriente > 0

    @property
    def remitos_pendientes_count(self):
        """Cantidad de remitos pendientes de facturar."""
        return self.ventas.filter(
            es_remito=True,
            estado='COMPLETADO'
        ).count()


class CajaTurno(models.Model):
    """Modelo para controlar aperturas, cierres, arqueos y relevos de caja."""

    ESTADOS = (
        ("ABIERTA", "Abierta"),
        ("CERRADA", "Cerrada"),
    )

    TIPOS_CAJA = (
        ("LOCAL", "Caja POS Local"),
        ("MOVIL", "Caja Móvil Repartidor"),
    )

    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="turnos_caja",
    )

    # 🔽 Sucursal donde se abre el turno
    sucursal = models.ForeignKey(
        'configuracion.Sucursal',
        on_delete=models.PROTECT,
        related_name='turnos',
        verbose_name="Sucursal",
        null=True, blank=True,
        help_text="Sucursal donde se abre esta caja"
    )

    tipo_caja = models.CharField(
        "Tipo de Caja", max_length=10, choices=TIPOS_CAJA, default="LOCAL"
    )
    monto_inicial = models.DecimalField(
        "Fondo Inicial ($)", max_digits=10, decimal_places=2, default=0.0
    )
    fecha_apertura = models.DateTimeField(
        "Fecha de Apertura", auto_now_add=True
    )

    monto_final_efectivo = models.DecimalField(
        "Efectivo Real Contado ($)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    fecha_cierre = models.DateTimeField(
        "Fecha de Cierre", null=True, blank=True
    )

    diferencia = models.DecimalField(
        "Diferencia ($)", max_digits=10, decimal_places=2, default=0.0
    )
    estado = models.CharField(
        max_length=10, choices=ESTADOS, default="ABIERTA"
    )
    observaciones = models.TextField(
        "Observaciones / Notas", blank=True, null=True
    )

    class Meta:
        verbose_name = "Turno de Caja"
        verbose_name_plural = "Turnos de Caja"
        ordering = ["-fecha_apertura"]

    def __str__(self):
        suc = self.sucursal.nombre if self.sucursal else "Sin sucursal"
        return f"Turno #{self.id} ({self.get_tipo_caja_display()}) - {self.vendedor.username} @ {suc} [{self.estado}]"


class InformeCaja(models.Model):
    """
    Registra los informes X (parciales) y Z (cierre) emitidos por turno.
    """
    TIPO_CHOICES = [
        ('X', 'Informe X (Parcial)'),
        ('Z', 'Cierre Z (Final)'),
    ]

    turno = models.ForeignKey(
        CajaTurno,
        on_delete=models.CASCADE,
        related_name='informes',
        verbose_name="Turno de Caja",
    )
    tipo = models.CharField(
        "Tipo",
        max_length=1,
        choices=TIPO_CHOICES,
        default='X',
    )
    numero = models.IntegerField(
        "Número de Informe",
        null=True,
        blank=True,
        help_text="Solo para Z. Numeración consecutiva por sucursal.",
    )
    fecha_emision = models.DateTimeField(
        "Fecha de Emisión",
        auto_now_add=True,
    )
    emitido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='informes_emitidos',
        verbose_name="Emitido por",
    )

    # Totales congelados al momento de emisión
    total_efectivo = models.DecimalField("Efectivo", max_digits=12, decimal_places=2, default=0)
    total_debito = models.DecimalField("Débito", max_digits=12, decimal_places=2, default=0)
    total_credito = models.DecimalField("Crédito", max_digits=12, decimal_places=2, default=0)
    total_transferencia = models.DecimalField("Transferencia", max_digits=12, decimal_places=2, default=0)
    total_general = models.DecimalField("Total General", max_digits=12, decimal_places=2, default=0)
    cantidad_operaciones = models.IntegerField("Cantidad de Operaciones", default=0)

    # Solo aplican al Z
    monto_inicial = models.DecimalField("Fondo Inicial", max_digits=12, decimal_places=2, default=0)
    efectivo_esperado = models.DecimalField("Efectivo Esperado", max_digits=12, decimal_places=2, default=0)
    efectivo_contado = models.DecimalField("Efectivo Contado", max_digits=12, decimal_places=2, default=0)
    diferencia = models.DecimalField("Diferencia", max_digits=12, decimal_places=2, default=0)

    observaciones = models.TextField("Observaciones", blank=True, null=True)

    class Meta:
        verbose_name = "Informe de Caja"
        verbose_name_plural = "Informes de Caja"
        ordering = ['-fecha_emision']
        indexes = [
            models.Index(fields=['turno', 'tipo']),
            models.Index(fields=['tipo', 'numero']),
        ]

    def __str__(self):
        tipo_display = self.get_tipo_display()
        num = f" #{self.numero}" if self.numero else ""
        return f"{tipo_display}{num} - Turno #{self.turno_id} - ${self.total_general}"

    @property
    def es_cierre_z(self):
        """True si es un cierre Z."""
        return self.tipo == 'Z'


class Venta(models.Model):
    """Modelo de Venta con relación a Turno, Cliente, Repartidor y datos fiscales ARCA/AFIP."""

    METODOS_PAGO = (
        ("EFECTIVO", "Efectivo"),
        ("TARJETA_DEBITO", "Tarjeta de Débito"),
        ("TARJETA_CREDITO", "Tarjeta de Crédito"),
        ("TRANSFERENCIA", "Transferencia / Mercado Pago"),
    )

    TIPOS_COMPROBANTE = (
        (6, "Factura B"),
        (1, "Factura A"),
        (11, "Factura C"),
        (3, "Nota de Crédito A"),
        (8, "Nota de Crédito B"),
        (13, "Nota de Crédito C"),
        (0, "Ticket No Fiscal / Remito"),
    )

    ESTADOS_VENTA = (
        ("PRESUPUESTO", "Presupuesto / Cotización"),
        ("PENDIENTE_ENTREGA", "Pendiente de Entrega (En Camino)"),
        ("REMITO_CALLE", "Remito emitido en Calle"),
        ("ENTREGADO", "Entregado (Pendiente de Rendición)"),
        ("POSPUESTO", "Pospuesto / No Entregado"),
        ("COMPLETADO", "Completado y Cobrado"),
        ("CANCELADO", "Cancelado"),
    )

    MOTIVOS_POSPUESTO = (
        ("AUSENTE", "Cliente No Se Encontraba en Domicilio"),
        ("RECHAZADO", "Cliente Ya No Quería el Pedido"),
        ("DIRECCION_ERRONEA", "Dirección Incorrecta / No Ubicado"),
        ("REPROGRAMADO", "Reprogramado para Otra Fecha"),
    )

    ESTADO_COBRO_CHOICES = (
        ('PENDIENTE', 'Pendiente de Cobro'),
        ('PARCIAL', 'Parcialmente Cobrado'),
        ('COBRADO', 'Cobrado Totalmente'),
        ('ANULADO', 'Anulado'),
    )

    turno = models.ForeignKey(
        CajaTurno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventas",
    )

    # 🔽 Sucursal donde se generó la venta
    sucursal = models.ForeignKey(
        'configuracion.Sucursal',
        on_delete=models.PROTECT,
        related_name='ventas',
        verbose_name="Sucursal",
        null=True, blank=True,
        help_text="Sucursal donde se generó esta venta"
    )

    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventas_realizadas",
    )
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventas_asignadas",
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ventas"
    )

    # DIRECCIÓN DE ENTREGA ESPECÍFICA DE LA VENTA / ENVÍO
    direccion_entrega = models.CharField(
        "Dirección de Entrega / Reparto", max_length=255, null=True, blank=True
    )

    fecha = models.DateTimeField(auto_now_add=True)
    fecha_entrega = models.DateTimeField(
        "Fecha de Entrega", null=True, blank=True
    )

    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    metodo_pago = models.CharField(
        max_length=20, choices=METODOS_PAGO, default="EFECTIVO"
    )
    estado = models.CharField(
        "Estado de Venta",
        max_length=25,
        choices=ESTADOS_VENTA,
        default="COMPLETADO",
    )

    motivo_pospuesto = models.CharField(
        "Motivo de Pospuesto",
        max_length=30,
        choices=MOTIVOS_POSPUESTO,
        null=True,
        blank=True,
    )
    observaciones_entrega = models.TextField(
        "Notas de Entrega", null=True, blank=True
    )

    monto_recibido = models.DecimalField(
        "Monto Recibido", max_digits=10, decimal_places=2, default=0.0
    )
    vuelto = models.DecimalField(
        "Vuelto", max_digits=10, decimal_places=2, default=0.0
    )

    # Facturación Electrónica ARCA / AFIP
    tipo_comprobante = models.IntegerField(
        "Tipo de Comprobante", choices=TIPOS_COMPROBANTE, default=6
    )
    numero_comprobante = models.IntegerField(
        "N° Comprobante ARCA", null=True, blank=True
    )
    cae = models.CharField(
        "CAE Autorizado", max_length=20, null=True, blank=True
    )
    vencimiento_cae = models.DateField(
        "Fecha Vencimiento CAE", null=True, blank=True
    )

    # Notas de Crédito
    es_nota_credito = models.BooleanField(
        "Es Nota de Crédito",
        default=False,
        help_text="True si esta venta es una Nota de Crédito que anula otra venta."
    )
    venta_original = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_credito",
        help_text="Venta original que esta Nota de Crédito anula."
    )
    motivo_anulacion = models.CharField(
        "Motivo de Anulación",
        max_length=200,
        null=True,
        blank=True,
    )

    # CUENTA CORRIENTE Y REMITOS
    estado_cobro = models.CharField(
        "Estado de Cobro",
        max_length=15,
        choices=ESTADO_COBRO_CHOICES,
        default='PENDIENTE',
    )

    saldo_pendiente = models.DecimalField(
        "Saldo Pendiente",
        max_digits=12,
        decimal_places=2,
        default=0.0,
    )

    es_remito = models.BooleanField(
        "Es Remito (no fiscal)",
        default=False,
        help_text="True si es un remito pendiente de facturar (no tiene CAE)."
    )

    es_factura_de_remitos = models.BooleanField(
        "Factura generada desde remitos",
        default=False,
    )

    remitos_facturados = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='factura_origen',
        help_text='Remitos que esta factura engloba.',
    )

    fecha_vencimiento = models.DateField(
        "Fecha de Vencimiento",
        null=True, blank=True,
        help_text='Para cuentas corrientes con plazo.',
    )

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-fecha"]

    def __str__(self):
        if self.es_nota_credito:
            return f"NC #{self.id} (anula Venta #{self.venta_original_id}) - ${self.total}"
        if self.es_remito:
            return f"Remito #{self.id} - ${self.total}"
        return f"Venta #{self.id} - ${self.total} [{self.get_estado_display()}]"

    @property
    def badge_color(self):
        if self.estado == "PENDIENTE_ENTREGA":
            return "danger"
        elif self.estado in ["ENTREGADO", "COMPLETADO", "REMITO_CALLE"]:
            return "success"
        elif self.estado == "POSPUESTO":
            return "warning text-dark"
        elif self.estado == "CANCELADO":
            return "dark"
        return "secondary"

    @property
    def badge_cobro_color(self):
        return {
            'PENDIENTE': 'danger',
            'PARCIAL': 'warning text-dark',
            'COBRADO': 'success',
            'ANULADO': 'secondary',
        }.get(self.estado_cobro, 'secondary')

    @property
    def dias_desde_emision(self):
        from django.utils import timezone
        if self.fecha:
            delta = timezone.now() - self.fecha
            return delta.days
        return 0

    # =========================================================
    # HELPERS SEGUROS PARA COMPROBANTES (cliente puede ser None)
    # =========================================================

    @property
    def cliente_nombre(self):
        """Nombre del cliente o 'Consumidor Final' si es anónimo."""
        if self.cliente:
            return self.cliente.nombre
        return "Consumidor Final"

    @property
    def cliente_documento(self):
        """Número de documento o 'S/D' si es anónimo."""
        if self.cliente and self.cliente.numero_documento:
            return self.cliente.numero_documento
        return "S/D"

    @property
    def cliente_tipo_documento(self):
        """Tipo de documento (CUIT, DNI, etc.) o '-' si es anónimo."""
        if self.cliente and self.cliente.tipo_documento:
            return self.cliente.tipo_documento
        return "-"

    @property
    def cliente_direccion(self):
        """Dirección completa o '-' si es anónimo."""
        if self.cliente:
            return self.cliente.direccion_completa or "-"
        return "-"

    @property
    def cliente_condicion_iva_display(self):
        """Condición IVA legible o 'Consumidor Final' por defecto."""
        if self.cliente:
            return self.cliente.get_condicion_iva_display()
        return "Consumidor Final"

    @property
    def cliente_telefono(self):
        """Teléfono o '-' si es anónimo."""
        if self.cliente:
            return self.cliente.telefono or "-"
        return "-"

    @property
    def cliente_email(self):
        """Email o '-' si es anónimo."""
        if self.cliente:
            return self.cliente.email or "-"
        return "-"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(
        Venta, on_delete=models.CASCADE, related_name="detalles"
    )
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre}"


# =========================================================
# PAGOS DE CLIENTES (CUENTA CORRIENTE)
# =========================================================

class Pago(models.Model):
    """Registra pagos de clientes."""

    METODOS_PAGO = (
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('TARJETA', 'Tarjeta'),
        ('CHEQUE', 'Cheque'),
        ('OTRO', 'Otro'),
    )

    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.CASCADE,
        related_name='pagos',
    )
    fecha = models.DateTimeField(auto_now_add=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(
        max_length=20, choices=METODOS_PAGO, default='EFECTIVO'
    )
    observaciones = models.CharField(max_length=255, blank=True, null=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    factura = models.ForeignKey(
        'Venta',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pagos_recibidos',
    )

    class Meta:
        verbose_name = "Pago de Cliente"
        verbose_name_plural = "Pagos de Clientes"
        ordering = ['-fecha']

    def __str__(self):
        return f"Pago #{self.id} - {self.cliente.nombre} - ${self.monto}"


# =========================================================
# CARGA DE VEHÍCULO Y STOCK A BORDO
# =========================================================

class CargaVehiculo(models.Model):
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cargas_realizadas",
    )
    fecha_carga = models.DateTimeField("Fecha de Carga", auto_now_add=True)
    observaciones = models.CharField(
        "Notas / Observaciones", max_length=255, blank=True, null=True
    )

    class Meta:
        verbose_name = "Carga de Vehículo"
        verbose_name_plural = "Cargas de Vehículos"
        ordering = ["-fecha_carga"]

    def __str__(self):
        return f"Carga #{self.id} - {self.repartidor.username} ({self.fecha_carga.strftime('%d/%m/%Y %H:%M')})"


class ItemCarga(models.Model):
    carga = models.ForeignKey(
        CargaVehiculo, on_delete=models.CASCADE, related_name="items"
    )
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField("Cantidad Cargada", default=1)

    def __str__(self):
        return f"{self.cantidad}u. {self.producto.nombre}"


class StockABordo(models.Model):
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stock_vehiculo",
    )
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad_actual = models.IntegerField("Cantidad a Bordo", default=0)

    class Meta:
        verbose_name = "Stock a Bordo"
        verbose_name_plural = "Stock a Bordo"
        unique_together = ("repartidor", "producto")

    def __str__(self):
        return f"{self.repartidor.username} -> {self.producto.nombre}: {self.cantidad_actual}u."


# =========================================================
# PERFIL DE REPARTIDOR
# =========================================================

class PerfilRepartidor(models.Model):
    """Datos extra del repartidor, vinculados 1-a-1 al User.

    No se elimina nunca: se da de baja (activo=False) para conservar
    el historial de ventas, entregas y liquidaciones.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_repartidor',
        verbose_name="Usuario"
    )
    dni = models.CharField("DNI", max_length=15, blank=True)
    telefono = models.CharField("Teléfono", max_length=30, blank=True)
    vehiculo = models.CharField(
        "Vehículo", max_length=100, blank=True,
        help_text="Ej: Moto Honda 150, patente ABC123"
    )
    patente = models.CharField("Patente", max_length=20, blank=True)
    zona = models.CharField(
        "Zona", max_length=100, blank=True,
        help_text="Ej: Centro, Norte, Sur"
    )
    licencia_conducir = models.CharField(
        "Licencia de Conducir", max_length=50, blank=True
    )
    activo = models.BooleanField("Activo", default=True)
    observaciones = models.TextField("Observaciones", blank=True, null=True)

    # 🔽 Fecha en que se dio de baja (soft delete)
    fecha_baja = models.DateTimeField(
        "Fecha de Baja",
        null=True,
        blank=True,
        help_text="Se completa cuando el repartidor se da de baja (no se elimina)."
    )

    class Meta:
        verbose_name = "Repartidor"
        verbose_name_plural = "Repartidores"
        ordering = ['-activo', 'user__first_name', 'user__last_name']

    def __str__(self):
        nombre = self.user.get_full_name() or self.user.username
        estado = "" if self.activo else " (BAJA)"
        return f"{nombre} - {self.vehiculo or 'Sin vehículo'}{estado}"

    @property
    def nombre_completo(self):
        return self.user.get_full_name() or self.user.username

    @property
    def esta_activo(self):
        return self.activo