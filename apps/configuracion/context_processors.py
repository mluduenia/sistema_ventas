from .models import EmpresaConfig


def configuracion_global(request):
    """Hace disponible los datos de la empresa y el logo en todas las plantillas HTML."""
    config = EmpresaConfig.objects.first()
    return {'configuracion': config}


def modulos_activos(request):
    """
    Inyecta los módulos activos en el contexto de TODOS los templates.
    Uso en templates: {{ modulos.punto_venta }}, {{ modulos.reparto }}, etc.
    """
    try:
        config = EmpresaConfig.objects.first()
    except Exception:
        config = None

    if not config:
        return {
            'modulos': {
                'punto_venta': True,
                'preventa': False,
                'reparto': False,
                'deposito': False,
                'cuenta_corriente': True,
                'multi_sucursal': False,
            },
            'modo_negocio': 'LOCAL',
        }

    return {
        'modulos': {
            'punto_venta': config.modulo_punto_venta,
            'preventa': config.modulo_preventa,
            'reparto': config.modulo_reparto,
            'deposito': config.modulo_deposito,
            'cuenta_corriente': config.modulo_cuenta_corriente,
            'multi_sucursal': config.modulo_multi_sucursal,
        },
        'modo_negocio': config.modo_negocio,
    }