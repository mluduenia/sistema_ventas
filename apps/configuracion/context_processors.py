from .models import EmpresaConfig

def configuracion_global(request):
    """Hace disponible los datos de la empresa y el logo en todas las plantillas HTML."""
    config = EmpresaConfig.objects.first()
    return {'configuracion': config}