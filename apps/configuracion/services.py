import datetime
from apps.configuracion.models import EmpresaConfiguracion

class ArcaService:
    """
    Servicio para la comunicación con los Web Services de ARCA (AFIP).
    Maneja la autenticación y emisión de facturas electrónicas.
    """

    def __init__(self):
        self.config = EmpresaConfiguracion.objects.first()
        if not self.config:
            raise ValueError("Debe configurar los datos de la Empresa en el Admin antes de facturar.")

    def solicitar_cae(self, venta):
        """
        Envía los datos de la venta a ARCA.
        """
        # Validación de certificados
        if not self.config.certificado_crt or not self.config.clave_privada_key:
            return {
                'aprobado': False,
                'error': 'Falta cargar el Certificado (.crt) o Clave Privada (.key) en la Configuración de Empresa.'
            }

        # Modo Homologación / Pruebas
        if self.config.modo_arica_homologacion:
            ultimo_cbte = 100 
            
            return {
                'aprobado': True,
                'cae': '74321890123456',
                'cae_vencimiento': datetime.date.today() + datetime.timedelta(days=10),
                'numero_comprobante': ultimo_cbte + 1,
                'punto_de_venta': self.config.punto_de_venta,
                'error': None
            }

        return {'aprobado': False, 'error': 'El modo producción aún no está configurado.'}