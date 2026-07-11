from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone

class Usuario(AbstractUser):
    ROLES = (
        ('admin', 'Administrador'),
        ('gerente', 'Gerente'),
        ('vendedor', 'Vendedor'),
        ('almacen', 'Almacenista'),
        ('contador', 'Contador'),
    )
    
    rol = models.CharField(max_length=20, choices=ROLES, default='vendedor')
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    ultimo_acceso = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    
    # Permisos temporales - CORREGIDO
    permisos_temporales = models.ManyToManyField(
        Permission,
        through='PermisoTemporal',
        through_fields=('usuario', 'permission'),
        related_name='usuarios_temporales'
    )
    
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='usuarios_groups',
        related_query_name='usuario_group',
    )
    
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='usuarios_user_permissions',
        related_query_name='usuario_user_permission',
    )
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
    
    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"
    
    def tiene_permiso_temporal(self, permiso_codename):
        """Verifica si el usuario tiene un permiso temporal activo"""
        if self.is_superuser:
            return True
            
        ahora = timezone.now()
        permisos_activos = self.permisos_temporales.filter(
            permisotemporal__fecha_expiracion__gt=ahora,
            permisotemporal__activo=True
        ).filter(codename=permiso_codename)
        
        return permisos_activos.exists()
    
    def get_permisos_activos(self):
        """Retorna todos los permisos activos del usuario"""
        ahora = timezone.now()
        return self.permisos_temporales.filter(
            permisotemporal__fecha_expiracion__gt=ahora,
            permisotemporal__activo=True
        )

class PermisoTemporal(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='permisos_temporales_rel')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='permisos_temporales_rel')
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_expiracion = models.DateTimeField()
    activo = models.BooleanField(default=True)
    motivo = models.TextField(blank=True)
    asignado_por = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='permisos_asignados'
    )
    
    class Meta:
        verbose_name = 'Permiso Temporal'
        verbose_name_plural = 'Permisos Temporales'
        ordering = ['-fecha_asignacion']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.permission.name} - {self.fecha_expiracion}"
    
    def esta_activo(self):
        return self.activo and self.fecha_expiracion > timezone.now()