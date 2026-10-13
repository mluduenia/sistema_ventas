import logging
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .services import generar_alertas_para_usuario

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def generar_alertas_al_loguearse(sender, request, user, **kwargs):
    try:
        generar_alertas_para_usuario(user)
    except Exception as e:
        logger.exception(f'Error generando alertas para {user.username}: {e}')