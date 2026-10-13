from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Alerta


@login_required
@require_POST
@csrf_exempt
def marcar_alerta_leida(request, alerta_id):
    """Marca una alerta como leída (la oculta del dashboard)."""
    try:
        alerta = Alerta.objects.get(id=alerta_id)

        # Permisos: solo el usuario destino o rol destino puede marcarla
        rol = getattr(request.user, 'rol', '')
        puede = (
            request.user.is_superuser or
            alerta.usuario == request.user or
            alerta.rol == rol or
            (alerta.rol == 'gerente' and rol == 'superadmin')
        )

        if not puede:
            return JsonResponse({'success': False, 'error': 'No tenés permiso.'}, status=403)

        alerta.leida = True
        alerta.save()

        return JsonResponse({'success': True, 'message': 'Alerta descartada.'})

    except Alerta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Alerta no encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)