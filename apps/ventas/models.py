from django.db import models
from django.conf import settings
from apps.productos.models import Producto

class Cliente(models.Model):
    """Modelo para la gestión de clientes dentro del sistema."""
    nombre = models.CharField(max_length=150)
    numero_documento = models.CharField('DNI / CUIT', max_length=20, blank=True, null=True)
    email = models.EmailField('Correo Electrónico', blank=True, null=True)
    telefono = models.CharField('Teléfono', max_length=30, blank=True, null=True)
    direccion = models.CharField('Dirección', max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.nombre


class CajaTurno(models.Model):
    """Modelo para controlar aperturas, cierres, arqueos y relevos de caja."""
    ESTADOS = (
        ('ABIERTA', 'Abierta'),
        ('CERRADA', 'Cerrada'),
    )

    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='turnos_caja'
    )
    monto_inicial = models.DecimalField('Fondo Inicial ($)', max_digits=10, decimal_places=2, default=0.0)
    fecha_apertura = models.DateTimeField('Fecha de Apertura', auto_now_add=True)
    
    monto_final_efectivo = models.DecimalField('Efectivo Real Contado ($)', max_digits=10, decimal_places=2, null=True, blank=True)
    fecha_cierre = models.DateTimeField('Fecha de Cierre', null=True, blank=True)
    
    diferencia = models.DecimalField('Diferencia ($)', max_digits=10, decimal_places=2, default=0.0)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='ABIERTA')
    observaciones = models.TextField('Observaciones / Notas', blank=True, null=True)

    class Meta:
        verbose_name = 'Turno de Caja'
        verbose_name_plural = 'Turnos de Caja'
        ordering = ['-fecha_apertura']

    def __str__(self):
        return f"Turno #{self.id} - {self.vendedor.username} ({self.estado})"


class Venta(models.Model):
    """Modelo de Venta con relación al Turno de Caja y al Cliente."""
    METODOS_PAGO = (
        ('EFECTIVO', 'Efectivo'),
        ('TARJETA_DEBITO', 'Tarjeta de Débito'),
        ('TARJETA_CREDITO', 'Tarjeta de Crédito'),
        ('TRANSFERENCIA', 'Transferencia / Mercado Pago'),
    )

    turno = models.ForeignKey(
        CajaTurno, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ventas'
    )
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ventas_realizadas'
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='EFECTIVO')

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'

    def __str__(self):
        return f"Venta #{self.id} - ${self.total}"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre}"