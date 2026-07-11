from django.db import models

class Auditoria(models.Model):
    ACCIONES = (
        ('crear', 'Crear'),
        ('actualizar', 'Actualizar'),
        ('eliminar', 'Eliminar'),
        ('login', 'Login'),
        ('logout', 'Logout'),
    )
    
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    modelo = models.CharField(max_length=100)
    objeto_id = models.IntegerField()
    detalle = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.usuario} - {self.accion} - {self.fecha}"