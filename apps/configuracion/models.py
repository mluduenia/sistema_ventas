from django.db import models

class EmpresaConfig(models.Model):
    CONDICION_IVA_CHOICES = [
        ('RI', 'Responsable Inscripto'),
        ('MO', 'Monotributo'),
        ('EX', 'Exento'),
    ]

    AMBIENTE_ARCA_CHOICES = [
        ('HOMO', 'Homologación (Pruebas)'),
        ('PROD', 'Producción (Real)'),
    ]

    # Datos Comerciales
    logo = models.ImageField('Logo del Comercio', upload_to='logos/', blank=True, null=True)
    razon_social = models.CharField(max_length=200, default='Mi Comercio S.A.')
    nombre_fantasia = models.CharField(max_length=200, blank=True, null=True, default='Mi Negocio')
    cuit = models.CharField(max_length=20, default='20-12345678-9')
    condicion_iva = models.CharField(max_length=5, choices=CONDICION_IVA_CHOICES, default='MO')
    iibb = models.CharField(max_length=50, blank=True, null=True, help_text='Número de Ingresos Brutos')
    inicio_actividades = models.DateField(blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True, default='Av. Principal 123')
    telefono = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # Configuración de Servidor de Correo (SMTP para enviar comprobantes)
    email_smtp_host = models.CharField(max_length=150, default='smtp.gmail.com', help_text='Ej: smtp.gmail.com o smtp.office365.com')
    email_smtp_port = models.IntegerField(default=587, help_text='Puerto SMTP habitual: 587 (TLS) o 465 (SSL)')
    email_smtp_user = models.CharField(max_length=150, blank=True, null=True, help_text='Tu correo emisor')
    email_smtp_password = models.CharField(max_length=150, blank=True, null=True, help_text='Contraseña de aplicación')
    email_smtp_use_tls = models.BooleanField(default=True)

    # Configuración de Facturación ARCA / AFIP
    punto_de_venta = models.IntegerField(default=1, help_text='Número de Punto de Venta habilitado en ARCA (Ej: 1)')
    ambiente_arca = models.CharField(max_length=5, choices=AMBIENTE_ARCA_CHOICES, default='HOMO')
    certificado_crt = models.FileField(upload_to='certificados/', blank=True, null=True, help_text='Archivo .crt obtenido en ARCA')
    clave_privada_key = models.FileField(upload_to='certificados/', blank=True, null=True, help_text='Archivo .key de la clave privada')

    class Meta:
        verbose_name = 'Configuración de Empresa'
        verbose_name_plural = 'Configuraciones de Empresa'

    def __str__(self):
        return f"{self.razon_social} (CUIT: {self.cuit})"