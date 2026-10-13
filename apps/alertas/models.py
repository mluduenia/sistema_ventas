from django.db import models
from django.conf import settings


class Alerta(models.Model):
    TIPOS = (
        ('pedido_pendiente', 'Pedido Pendiente de Entrega'),
        ('rendicion_pendiente', 'Remito Pendiente de Rendición'),
        ('factura_pendiente', 'Comprobante Pendiente de Facturar'),
        ('stock_minimo', 'Stock Bajo Mínimo'),
        ('caja_abierta', 'Caja Abierta sin Cerrar'),
    )

    NIVELES = (
        ('info', 'Info'),
        ('warning', 'Advertencia'),
        ('danger', 'Urgente'),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='alertas',
        null=True, blank=True,
        help_text='Si es NULL, es una alerta para el rol indicado.',
    )
    rol = models.CharField(
        max_length=20,
        blank=True, null=True,
        help_text='Rol destino si no es para un usuario específico.',
    )
    tipo = models.CharField(max_length=30, choices=TIPOS)
    nivel = models.CharField(max_length=10, choices=NIVELES, default='info')
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    leida = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)
    expira = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creada']
        verbose_name = 'Alerta'
        verbose_name_plural = 'Alertas'
        indexes = [
            models.Index(fields=['usuario', 'leida']),
            models.Index(fields=['rol', 'leida']),
        ]

    def __str__(self):
        return f'[{self.get_nivel_display()}] {self.titulo}'