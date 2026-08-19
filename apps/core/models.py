from django.db import models

class Auditoria(models.Model):
    usuario = models.CharField(max_length=100, blank=True, null=True)
    accion = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'

    def __str__(self):
        return f"{self.accion} - {self.usuario} ({self.fecha})"