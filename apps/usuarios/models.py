from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone


class Usuario(AbstractUser):
    ROLES = (
        # ============================================================
        # ROLES JERÁRQUICOS
        # ============================================================
        ('admin', 'Administrador'),
        ('gerente', 'Gerente'),
        ('supervisor', 'Supervisor'),

        # ============================================================
        # ROLES OPERATIVOS
        # ============================================================
        ('vendedor', 'Vendedor'),
        ('cajero', 'Cajero'),
        ('preventista', 'Preventista / Viajante'),

        # ============================================================
        # ROLES DE LOGÍSTICA
        # ============================================================
        ('repartidor', 'Repartidor'),
        ('deposito', 'Operario de Depósito'),

        # ============================================================
        # ROLES ADMINISTRATIVOS
        # ============================================================
        ('contador', 'Contador'),
    )

    # ============================================================
    # CAMPOS BÁSICOS
    # ============================================================
    rol = models.CharField(max_length=20, choices=ROLES, default='vendedor')
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    ultimo_acceso = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    # Sucursal asignada
    sucursal = models.ForeignKey(
        'configuracion.Sucursal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='usuarios',
        verbose_name="Sucursal Asignada",
        help_text="Sucursal donde trabaja habitualmente este usuario"
    )

    # ============================================================
    # PERMISOS
    # ============================================================
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

    # ============================================================
    # MÉTODOS DE VALIDACIÓN DE ROL (compatibilidad)
    # ============================================================

    def is_repartidor(self):
        return self.rol == 'repartidor'

    def is_vendedor(self):
        return self.rol in ('vendedor', 'admin', 'gerente', 'supervisor', 'cajero', 'preventista')

    def is_cajero(self):
        return self.rol in ('cajero', 'admin', 'gerente', 'supervisor')

    def is_preventista(self):
        return self.rol == 'preventista'

    def is_deposito(self):
        return self.rol in ('deposito', 'admin', 'gerente', 'supervisor')

    # ============================================================
    # PROPIEDADES DE CAPACIDAD (qué puede hacer)
    # ============================================================

    @property
    def puede_vender(self):
        """True si puede emitir ventas en el POS."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente', 'supervisor', 'vendedor', 'cajero')

    @property
    def puede_cobrar(self):
        """True si puede cobrar ventas."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente', 'supervisor', 'cajero')

    @property
    def puede_preventa(self):
        """True si puede tomar pedidos en la calle."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente', 'supervisor', 'preventista', 'vendedor')

    @property
    def puede_repartir(self):
        """True si puede entregar pedidos a domicilio."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente', 'supervisor', 'repartidor')

    @property
    def puede_gestionar_deposito(self):
        """True si puede gestionar stock, cargas y descargas."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente', 'supervisor', 'deposito')

    @property
    def puede_cerrar_caja(self):
        """True si puede abrir/cerrar turno de caja."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente', 'supervisor', 'cajero', 'vendedor')

    @property
    def puede_ver_todo(self):
        """True si puede ver datos de toda la empresa."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente', 'supervisor')

    @property
    def puede_ver_reportes(self):
        """True si puede acceder a reportes."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente', 'supervisor', 'contador')

    @property
    def puede_gestionar_usuarios(self):
        """True si puede crear/editar usuarios."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente')

    @property
    def puede_configurar(self):
        """True si puede acceder a la configuración del sistema."""
        if self.is_superuser:
            return True
        return self.rol in ('admin', 'gerente')

    # ============================================================
    # PERMISOS TEMPORALES
    # ============================================================

    def tiene_permiso_temporal(self, permiso_codename):
        """Verifica si el usuario tiene un permiso temporal activo."""
        if self.is_superuser:
            return True

        ahora = timezone.now()
        permisos_activos = self.permisos_temporales.filter(
            permisotemporal__fecha_expiracion__gt=ahora,
            permisotemporal__activo=True
        ).filter(codename=permiso_codename)

        return permisos_activos.exists()

    def get_permisos_activos(self):
        """Retorna todos los permisos temporales activos del usuario."""
        ahora = timezone.now()
        return self.permisos_temporales.filter(
            permisotemporal__fecha_expiracion__gt=ahora,
            permisotemporal__activo=True
        )


# ============================================================
# PERMISO TEMPORAL
# ============================================================

class PermisoTemporal(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='permisos_temporales_rel'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='permisos_temporales_rel'
    )
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